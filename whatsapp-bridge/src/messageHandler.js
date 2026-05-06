const StateManager = require('./stateManager');
const ApiClient = require('./apiClient');
const TemplateEngine = require('./templateEngine');
const { formatForWhatsApp } = require('./utils/whatsappFormatter');

const stateManager = new StateManager();
const apiClient = new ApiClient();
const templateEngine = new TemplateEngine();

const WELCOME_MESSAGE = (
  '🛡️ *Hola, soy Segurito!* Asistente de organismos del Estado de Chile.\n\n' +
  '¿En qué puedo ayudarte? Responde con el número:\n\n' +
  '1️⃣ Tengo un problema con un banco, AFP, seguro o entidad financiera\n' +
  '2️⃣ Tengo una consulta sobre trámites o servicios\n' +
  '3️⃣ Me vendieron algo defectuoso o tengo un problema de consumo\n' +
  '4️⃣ Tengo una consulta sobre impuestos\n' +
  '5️⃣ Otro tema'
);

/**
 * Mapea la respuesta del usuario (número o texto) al valor de una opción.
 */
function mapChoice(userInput, choices) {
  if (!choices || choices.length === 0) return userInput;

  const num = parseInt(userInput, 10);
  if (!isNaN(num) && num >= 1 && num <= choices.length) {
    return choices[num - 1].value;
  }

  const lower = userInput.toLowerCase().trim();
  for (const choice of choices) {
    if (choice.value.toLowerCase() === lower) return choice.value;
    if (choice.label.toLowerCase().includes(lower)) return choice.value;
  }

  return userInput;
}

/**
 * Formatea un mensaje con opciones numeradas.
 */
function formatMessage(text, choices) {
  if (!choices || choices.length === 0) return text;

  const lines = [text, ''];
  choices.forEach((c, i) => {
    lines.push(`${i + 1}️⃣ ${c.label}`);
  });
  lines.push('', '_Responde con el número o la opción._');
  return lines.join('\n');
}

/**
 * Construye el resumen final para enviar al backend.
 */
function buildSummary(data) {
  const plazoMap = {
    '1': 'menos_1_mes', '2': '1_3_meses', '3': '3_6_meses', '4': 'mas_6_meses',
    'menos_1_mes': 'menos_1_mes', '1_3_meses': '1_3_meses',
    '3_6_meses': '3_6_meses', 'mas_6_meses': 'mas_6_meses',
  };
  const reclamoMap = {
    '1': 'si_respondieron', '2': 'si_no_respondieron', '3': 'no',
    'si_respondieron': 'si_respondieron', 'si_no_respondieron': 'si_no_respondieron',
    'no': 'no', 'no he reclamado': 'no',
  };

  const plazo = plazoMap[data.plazo] || data.plazo || 'No especificado';
  const reclamo = reclamoMap[data.reclamo_previo] || data.reclamo_previo || 'No especificado';

  return (
    `Resumen del caso del usuario:\n` +
    `- Tipo de entidad: ${data.tipo_entidad || 'No especificado'}\n` +
    `- Nombre entidad: ${data.nombre_entidad || 'No especificado'}\n` +
    `- Descripción: ${data.descripcion || 'No especificada'}\n` +
    `- Plazo: ${plazo}\n` +
    `- Reclamo previo: ${reclamo}\n` +
    `- Evidencia: ${data.evidencia || 'No adjuntada'}\n\n` +
    `Analiza este caso según la normativa CMF e indica los pasos a seguir.`
  );
}

/**
 * Maneja un mensaje entrante de WhatsApp.
 */
async function handleMessage(message, client) {
  if (message.fromMe) return;

  const chatId = message.from;
  const body = (message.body || '').trim();
  console.log(`[MessageHandler] Received: chatId=${chatId}, body="${body.substring(0, 50)}"`);

  if (!body) {
    await client.sendMessage(chatId, 'Por favor escríbeme tu consulta o selecciona una opción. 😊');
    return;
  }

  // Procesar adjuntos si los hay
  let attachmentText = '';
  if (message.hasMedia) {
    try {
      const mediaProcessor = require('./utils/mediaProcessor');
      const result = await mediaProcessor.processMedia(message);
      if (result.error) {
        await client.sendMessage(chatId, result.error);
        return;
      }
      attachmentText = result.description || `[Archivo: ${result.filename}]`;
    } catch (err) {
      console.error('[MessageHandler] Media error:', err.message);
    }
  }

  const fullMessage = attachmentText ? `${body}\n${attachmentText}` : body;

  // Buscar estado existente
  let state = stateManager.get(chatId);
  console.log(`[MessageHandler] State: ${state ? `topic=${state.topic}, step=${state.stepId}` : 'null'}`);

  // --- SIN ESTADO: Primera interacción → mostrar bienvenida ---
  if (!state) {
    // Si es un saludo genérico, mostrar bienvenida
    const greetings = ['hola', 'hi', 'hello', 'hey', 'buenas', 'buenos días', 'buenas tardes', 'buenas noches', 'ola'];
    const isGreeting = greetings.some(g => body.toLowerCase().includes(g));
    console.log(`[MessageHandler] isGreeting=${isGreeting}, bodyLower="${body.toLowerCase()}"`);
    if (isGreeting) {
      console.log('[MessageHandler] Sending WELCOME_MESSAGE');
      await client.sendMessage(chatId, WELCOME_MESSAGE);
      stateManager.set(chatId, { topic: 'welcome', stepId: 'menu', data: {} });
      return;
    }

    // Si es un mensaje directo sobre un problema, enviar al backend primero
    console.log('[MessageHandler] No state, no greeting → sending to backend');
    await handleBackendQuery(chatId, fullMessage, null, client);
    return;
  }

  // --- ESTADO: WELCOME → redirigir según selección ---
  if (state.topic === 'welcome') {
    const selection = body.trim();
    console.log(`[MessageHandler] Welcome state, selection="${selection}"`);
    if (selection === '1') {
      // Iniciar template de reclamo CMF
      state.topic = 'reclamo-cmf';
      state.stepId = 'bienvenida';
      stateManager.set(chatId, state);

      const question = templateEngine.getQuestion('reclamo-cmf', 'bienvenida', {});
      const choices = templateEngine.getChoices('reclamo-cmf', 'bienvenida');
      await client.sendMessage(chatId, formatMessage(question, choices));
      return;
    }
    if (selection === '2' || selection === '3' || selection === '4' || selection === '5') {
      // Consulta libre → enviar al backend
      state.topic = 'default';
      stateManager.set(chatId, state);
      await client.sendMessage(chatId, 'Cuéntame tu consulta en detalle y te ayudaré. 👇');
      return;
    }

    // Texto libre → enviar al backend
    state.topic = 'default';
    stateManager.set(chatId, state);
    await handleBackendQuery(chatId, fullMessage, state.conversationId, client);
    return;
  }

  // --- ESTADO: DEFAULT → consulta libre al backend ---
  if (state.topic === 'default') {
    // Permitir salir del modo default con comandos de menú
    const lower = body.toLowerCase().trim();
    const greetings = ['hola', 'hi', 'hello', 'hey', 'buenas', 'buenos días', 'buenas tardes', 'buenas noches', 'ola'];
    const isReset = lower === 'menú' || lower === 'menu' || lower === 'salir' || lower === 'cancelar' || lower === 'restart';
    const isGreeting = greetings.some(g => lower.includes(g));

    if (isReset || isGreeting) {
      console.log(`[MessageHandler] Reset from default → showing WELCOME_MESSAGE (trigger="${lower}")`);
      state.topic = 'welcome';
      state.stepId = 'menu';
      state.data = {};
      stateManager.set(chatId, state);
      await client.sendMessage(chatId, WELCOME_MESSAGE);
      return;
    }

    console.log(`[MessageHandler] Default state → sending to backend with convId=${state.conversationId}`);
    await handleBackendQuery(chatId, fullMessage, state.conversationId, client);
    return;
  }

  // --- ESTADO: TEMPLATE ACTIVO → procesar paso del template ---
  console.log(`[MessageHandler] Template state: topic=${state.topic}, step=${state.stepId}`);
  await handleTemplateStep(chatId, body, state, client);
}

/**
 * Envía un mensaje al backend y responde al usuario.
 */
async function handleBackendQuery(chatId, message, conversationId, client) {
  try {
    const payload = { message };
    if (conversationId) payload.conversation_id = conversationId;

    const response = await apiClient.chat(payload);

    let state = stateManager.get(chatId);
    if (!state) {
      state = stateManager.set(chatId, { topic: 'default', stepId: null, data: {} });
    }
    state.conversationId = response.conversation_id;
    stateManager.updateActivity(chatId);

    // Verificar si el backend detectó un reclamo CMF
    const intencion = (response.intencion || '').toUpperCase();
    const organismo = (response.organismo_detectado || '').toLowerCase();
    console.log(`[MessageHandler] Backend response: intencion=${intencion}, organismo=${organismo}`);

    if (intencion.includes('RECLAMO') && organismo === 'cmf') {
      state.topic = 'reclamo-cmf';
      state.stepId = 'bienvenida';
      stateManager.set(chatId, state);

      await client.sendMessage(chatId, formatForWhatsApp(response.response));
      const question = templateEngine.getQuestion('reclamo-cmf', 'bienvenida', {});
      const choices = templateEngine.getChoices('reclamo-cmf', 'bienvenida');
      await client.sendMessage(chatId, formatMessage(question, choices));
      return;
    }

    // Verificar si es alerta de fraude
    if (intencion === 'ALERTA') {
      await client.sendMessage(chatId, formatForWhatsApp(response.response));
      await client.sendMessage(chatId, WELCOME_MESSAGE);
      state.topic = 'welcome';
      state.stepId = 'menu';
      stateManager.set(chatId, state);
      return;
    }

    await client.sendMessage(chatId, formatForWhatsApp(response.response));
  } catch (err) {
    console.error('[MessageHandler] Backend error:', err.message);
    await client.sendMessage(chatId, '⚠️ Hubo un problema procesando tu consulta. Intenta nuevamente en unos segundos.');
  }
}

/**
 * Procesa un paso dentro de un template.
 */
async function handleTemplateStep(chatId, userInput, state, client) {
  const currentStep = templateEngine.getStep(state.topic, state.stepId);

  if (!currentStep) {
    // Paso no encontrado → resetear
    state.topic = 'default';
    state.stepId = null;
    stateManager.set(chatId, state);
    await client.sendMessage(chatId, 'Parece que hubo un problema. Empecemos de nuevo:\n\n' + WELCOME_MESSAGE);
    return;
  }

  // Mapear respuesta del usuario a valor de opción si es choice
  const choices = templateEngine.getChoices(state.topic, state.stepId);
  const mappedInput = mapChoice(userInput, choices);

  // Verificar si quiere salir o reiniciar
  const lowerInput = userInput.toLowerCase().trim();
  if (lowerInput === 'salir' || lowerInput === 'cancelar' || lowerInput === 'restart' || lowerInput === 'menú' || lowerInput === 'menu') {
    state.topic = 'welcome';
    state.stepId = 'menu';
    state.data = {};
    stateManager.set(chatId, state);
    await client.sendMessage(chatId, WELCOME_MESSAGE);
    return;
  }

  // Procesar el paso
  const result = templateEngine.processStep(chatId, mappedInput, state);

  if (result.exitToDefault) {
    state.topic = 'default';
    state.stepId = null;
    stateManager.set(chatId, state);
    await handleBackendQuery(chatId, userInput, state.conversationId, client);
    return;
  }

  if (result.action === 'complete') {
    // Template completado → enviar resumen al backend
    const summary = buildSummary(result.data);
    try {
      const response = await apiClient.chat({
        message: summary,
        conversation_id: state.conversationId,
      });
      await client.sendMessage(chatId, formatForWhatsApp(response.response));
    } catch (err) {
      console.error('[MessageHandler] Error sending summary:', err.message);
      await client.sendMessage(chatId, '⚠️ Hubo un problema enviando tu caso al análisis. Tu información fue guardada. Intenta escribir "menú" para volver a empezar.');
      return;
    }

    // Resetear estado
    state.topic = 'welcome';
    state.stepId = 'menu';
    state.data = {};
    stateManager.set(chatId, state);
    await client.sendMessage(chatId, '\n\n¿Necesitas algo más? Responde con el número:\n1️⃣ Otro reclamo\n2️⃣ Consulta\n3️⃣ Salir');
    return;
  }

  if (result.action === 'ask') {
    stateManager.set(chatId, state);
    const question = templateEngine.getQuestion(state.topic, result.step.id, state.data);
    const nextChoices = templateEngine.getChoices(state.topic, result.step.id);
    await client.sendMessage(chatId, formatMessage(question, nextChoices));
    return;
  }

  // Fallback
  state.topic = 'default';
  stateManager.set(chatId, state);
  await handleBackendQuery(chatId, userInput, state.conversationId, client);
}

module.exports = { handleMessage };