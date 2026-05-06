'use strict';
/**
 * messageHandler.js — Routea mensajes entrantes de WhatsApp.
 *
 * Lógica:
 * 1. Si hay media → procesar con mediaProcessor.
 * 2. Buscar/crear estado en stateManager.
 * 3. Si topic == "default" → llamar al backend y evaluar intención.
 * 4. Si topic != "default" → avanzar en el template activo.
 */

const stateManager = require('./stateManager');
const apiClient = require('./apiClient');
const templateEngine = require('./templateEngine');
const { processMedia } = require('./utils/mediaProcessor');
const TEMPLATES = require('./templates/index');

const MSG_SERVICE_BUSY =
  'El servicio está ocupado en este momento. Por favor intenta en unos segundos.';

/**
 * Formatea las opciones de un paso tipo "choice" como texto para WhatsApp.
 * @param {Array<{label: string, value: string}>} choices
 * @returns {string}
 */
function _formatChoices(choices) {
  if (!choices || choices.length === 0) return '';
  return '\n\n' + choices.map((c, i) => `${i + 1}. ${c.label}`).join('\n');
}

/**
 * Construye el resumen final de un reclamo para enviarlo al backend.
 * @param {object} data — datos acumulados del template
 * @returns {string}
 */
function _buildReclamoSummary(data) {
  const lines = [
    'Analiza el siguiente caso de reclamo CMF:',
    `- Entidad: ${data.nombre_entidad || data.tipo_entidad || '—'}`,
    `- Tipo de entidad: ${data.tipo_entidad || '—'}`,
    `- Descripción del problema: ${data.descripcion || '—'}`,
    `- Plazo: ${data.plazo || '—'}`,
    `- Reclamo previo: ${data.reclamo_previo || '—'}`,
  ];
  if (data.evidencia) {
    lines.push(`- Evidencia adjuntada: sí`);
  }
  lines.push(
    'Por favor orienta al ciudadano sobre los pasos a seguir, la normativa aplicable ' +
    '(Ley 19.496, circulares CMF, DFL 3) y el canal correcto (entidad → CMF → SERNAC → tribunales).'
  );
  return lines.join('\n');
}

/**
 * Handler principal. Llamar con el objeto message de whatsapp-web.js.
 * @param {object} message
 * @param {object} client — instancia del cliente (para enviar respuestas)
 */
async function handleMessage(message, client) {
  // Ignorar mensajes propios y de grupos (MVP: solo chats privados)
  if (message.fromMe) return;
  const chat = await message.getChat();
  if (chat.isGroup) return;

  const chatId = message.from;
  const body = (message.body || '').trim();

  let attachments = [];

  // Procesar media si existe
  if (message.hasMedia) {
    const result = await processMedia(message);
    if (!result.ok) {
      await client.sendMessage(chatId, result.reason);
      return;
    }
    // Solo incluir en payload si tiene base64 (imagen) o description (doc)
    if (result.attachment.base64_data || result.attachment.description) {
      attachments.push(result.attachment);
    }
  }

  // Si no hay texto y tampoco adjunto con descripción, ignorar silenciosamente
  if (!body && attachments.length === 0) return;

  let state = stateManager.get(chatId);

  // ─── Flujo: topic == "default" ──────────────────────────────────────────
  if (!state || state.topic === 'default') {
    if (!state) {
      stateManager.set(chatId, { topic: 'default' });
      state = stateManager.get(chatId);
    }

    let backendResp;
    try {
      const payload = {
        message: body || '[adjunto sin texto]',
        conversation_id: state.conversationId || undefined,
      };
      if (attachments.length > 0) payload.attachments = attachments;
      backendResp = await apiClient.chat(payload);
    } catch (err) {
      await client.sendMessage(chatId, MSG_SERVICE_BUSY);
      return;
    }

    // Persistir conversation_id que devuelve el backend
    if (backendResp.conversation_id) {
      state.conversationId = backendResp.conversation_id;
      stateManager.set(chatId, state);
    }
    stateManager.updateActivity(chatId);

    const intencion = (backendResp.intencion || '').toUpperCase();
    const organismo = (backendResp.organismo_detectado || '').toLowerCase();

    // Si detectamos reclamo CMF → activar template
    if (intencion.startsWith('RECLAMO') && organismo === 'cmf') {
      const topic = 'reclamo-cmf';
      const template = TEMPLATES[topic];
      const firstStep = template ? template.FIRST_STEP : 'bienvenida';

      stateManager.set(chatId, {
        ...state,
        topic,
        stepId: firstStep,
        data: {},
      });
      const updatedState = stateManager.get(chatId);
      const question = templateEngine.getQuestion(topic, firstStep, updatedState.data);
      const choices = templateEngine.getChoices(topic, firstStep);
      await client.sendMessage(chatId, question + _formatChoices(choices));
      return;
    }

    // Respuesta directa del backend
    await client.sendMessage(chatId, backendResp.response);
    return;
  }

  // ─── Flujo: dentro de un template ──────────────────────────────────────
  stateManager.updateActivity(chatId);

  // Si hay adjunto y el paso es "adjuntar_evidencia", guardar en data
  if (attachments.length > 0 && state.stepId === 'adjuntar_evidencia') {
    state.data.evidencia = attachments[0].description || attachments[0].filename || 'adjunto recibido';
    stateManager.set(chatId, state);
  }

  const userInput = body || (attachments.length > 0 ? 'adjunto' : '');
  const result = templateEngine.processStep(chatId, userInput, state);

  if (result.action === 'exit_to_default') {
    stateManager.set(chatId, { ...state, topic: 'default', stepId: null });
    // Re-enviar al backend como consulta libre
    let backendResp;
    try {
      backendResp = await apiClient.chat({
        message: body,
        conversation_id: state.conversationId || undefined,
      });
    } catch {
      await client.sendMessage(chatId, MSG_SERVICE_BUSY);
      return;
    }
    await client.sendMessage(chatId, backendResp.response);
    return;
  }

  if (result.action === 'ask') {
    // Actualizar stepId en el estado
    stateManager.set(chatId, { ...state, stepId: result.stepId });
    const updatedState = stateManager.get(chatId);
    const question = templateEngine.getQuestion(state.topic, result.stepId, updatedState.data);
    const choices = templateEngine.getChoices(state.topic, result.stepId);
    await client.sendMessage(chatId, question + _formatChoices(choices));
    return;
  }

  if (result.action === 'complete') {
    // Armar resumen y enviar al backend
    let summary;
    if (state.topic === 'reclamo-cmf') {
      summary = _buildReclamoSummary(result.data);
    } else {
      summary = body;
    }

    let backendResp;
    try {
      const payload = {
        message: summary,
        conversation_id: state.conversationId || undefined,
      };
      if (attachments.length > 0) payload.attachments = attachments;
      backendResp = await apiClient.chat(payload);
    } catch {
      await client.sendMessage(chatId, MSG_SERVICE_BUSY);
      return;
    }

    // Limpiar estado (volver a default)
    stateManager.set(chatId, {
      chatId,
      conversationId: backendResp.conversation_id || state.conversationId,
      topic: 'default',
      stepId: null,
      data: {},
    });

    await client.sendMessage(chatId, backendResp.response);
  }
}

module.exports = { handleMessage };
