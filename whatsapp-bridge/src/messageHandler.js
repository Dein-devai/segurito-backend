const StateManager = require('./stateManager');
const ApiClient = require('./apiClient');
const TemplateEngine = require('./templateEngine');

const stateManager = new StateManager();
const apiClient = new ApiClient();
const templateEngine = new TemplateEngine();

/**
 * Maneja un mensaje entrante de WhatsApp.
 * @param {import('whatsapp-web.js').Message} message
 * @param {import('whatsapp-web.js').Client} client
 */
async function handleMessage(message, client) {
  if (message.fromMe) return;
  const chatId = message.from;
  const body = message.body?.trim();

  if (!body) {
    await client.sendMessage(chatId, 'Por favor cuéntame tu consulta y te ayudaré.');
    return;
  }

  // Verificar si tiene adjuntos
  let attachmentText = '';
  if (message.hasMedia) {
    const mediaProcessor = require('./utils/mediaProcessor');
    const result = await mediaProcessor.processMedia(message);
    if (result.error) {
      await client.sendMessage(chatId, result.error);
      return;
    }
    attachmentText = result.description || `[Archivo adjunto: ${result.filename}]`;
  }

  const fullMessage = attachmentText ? `${body}\n${attachmentText}` : body;

  // Buscar estado existente
  let state = stateManager.get(chatId);

  if (!state || state.topic === 'default') {
    // Consulta libre → enviar al backend directamente
    try {
      const response = await apiClient.chat({
        message: fullMessage,
        ...(state?.conversationId ? { conversation_id: state.conversationId } : {}),
      });

      if (!state) {
        state = stateManager.set(chatId, {
          topic: 'default',
          stepId: null,
          data: {},
        });
      }
      state.conversationId = response.conversation_id;
      stateManager.updateActivity(chatId);

      // Verificar si el backend detectó un reclamo CMF
      const intencion = (response.intencion || '').toUpperCase();
      const organismo = (response.organismo_detectado || '').toLowerCase();

      if (intencion.includes('RECLAMO') && organismo === 'cmf') {
        // Iniciar template de reclamo CMF
        state.topic = 'reclamo-cmf';
        state.stepId = 'bienvenida';
        stateManager.set(chatId, state);

        const question = templateEngine.getQuestion('reclamo-cmf', 'bienvenida', state.data);
        const choices = templateEngine.getChoices('reclamo-cmf', 'bienvenida');
        await client.sendMessage(chatId, formatMessage(question, choices));
        return;
      }

      await client.sendMessage(chatId, response.response);
    } catch (err) {
      console.error('[MessageHandler] Error contacting backend:', err.message);
      await client.sendMessage(
        chatId,
        'Lo siento, hubo un problema procesando tu consulta. Intenta nuevamente en unos segundos.'
      );
    }
    return;
  }

  // Estamos dentro de un template
  const result = templateEngine.processStep(chatId, fullMessage, state);

  if (result.exitToDefault) {
    // El usuario quiere salir del template → consultar al backend
    state.topic = 'default';
    state.stepId = null;
    stateManager.set(chatId, state);

    try {
      const response = await apiClient.chat({
        message: fullMessage,
        conversation_id: state.conversationId,
      });
      await client.sendMessage(chatId, response.response);
    } catch (err) {
      console.error('[MessageHandler] Error:', err.message);
      await client.sendMessage(chatId, 'Error al procesar. Intenta de nuevo.');
    }
    return;
  }

  if (result.action === 'complete') {
    // Template completado → enviar resumen al backend
    const summary = buildSummary(state.topic, result.data);
    try {
      const response = await apiClient.chat({
        message: summary,
        conversation_id: state.conversationId,
      });
      await client.sendMessage(chatId, response.response);

      // Resetear a default
      state.topic = 'default';
      state.stepId = null;
      state.data = {};
      stateManager.set(chatId, state);
    } catch (err) {
      console.error('[MessageHandler] Error sending summary:', err.message);
      await client.sendMessage(chatId, 'Error al procesar tu reclamo. Intenta de nuevo.');
    }
    return;
  }

  if (result.action === 'ask') {
    // Mostrar la siguiente pregunta
    stateManager.set(chatId, state);
    const question = templateEngine.getQuestion(state.topic, result.step.id, state.data);
    const choices = templateEngine.getChoices(state.topic, result.step.id);
    await client.sendMessage(chatId, formatMessage(question, choices));
  }
}

/**
 * Formatea un mensaje con opciones si las hay.
 */
function formatMessage(text, choices) {
  if (!choices || choices.length === 0) return text;

  const lines = [text, ''];
  choices.forEach((c, i) => {
    lines.push(`${i + 1}. ${c.label}`);
  });
  return lines.join('\n');
}

/**
 * Construye el resumen final para enviar al backend.
 */
function buildSummary(topic, data) {
  if (topic === 'reclamo-cmf') {
    return (
      `Resumen del caso del usuario:\n` +
      `- Tipo de entidad: ${data.tipo_entidad || 'No especificado'}\n` +
      `- Nombre entidad: ${data.nombre_entidad || 'No especificado'}\n` +
      `- Descripción: ${data.descripcion || 'No especificada'}\n` +
      `- Plazo: ${data.plazo || 'No especificado'}\n` +
      `- Reclamo previo: ${data.reclamo_previo || 'No especificado'}\n` +
      `- Evidencia: ${data.evidencia || 'No adjuntada'}\n\n` +
      `Analiza este caso según la normativa CMF e indica los pasos a seguir.`
    );
  }
  return JSON.stringify(data);
}

module.exports = { handleMessage };