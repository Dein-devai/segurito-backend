"use strict";

const StateManager = require('./stateManager');
const ApiClient = require('./apiClient');
const TemplateEngine = require('./templateEngine');
const { formatForWhatsApp } = require('./utils/whatsappFormatter');
const { chunkResponse } = require('./utils/chunker');
const { validate } = require('./utils/validators');

const stateManager = new StateManager();
const apiClient = new ApiClient();
const templateEngine = new TemplateEngine();

// ---------------------------------------------------------------------------
// Copy reusable
// ---------------------------------------------------------------------------
const WELCOME_MESSAGE = (
  '🛡️ *Hola, soy Segurito.* Tu asistente para organismos del Estado de Chile.\n\n' +
  '¿En qué puedo ayudarte hoy? Responde con el *número* de la opción:\n\n' +
  '1️⃣  Problema con un *banco, AFP o seguro* (entidad financiera)\n' +
  '2️⃣  *Trámite o servicio* del Estado\n' +
  '3️⃣  *Reclamo de consumo* (algo defectuoso, cobro doble, etc.)\n' +
  '4️⃣  Consulta sobre *impuestos* (SII)\n' +
  '5️⃣  Otro tema\n\n' +
  '_En cualquier momento puedes escribir *menú* para volver, *salir* para terminar o *humano* para hablar con una persona._'
);

const HUMAN_HANDOFF = (
  '👤 Anotado. Esta es una versión piloto y aún no tengo derivación directa con un agente humano. ' +
  'Mientras tanto:\n\n' +
  '• Si es urgente, *Carabineros 133* / *PDI 134*.\n' +
  '• Para consumo: *SERNAC 800-700-100*.\n' +
  '• Para banca: *CMF 600-831-0000*.\n\n' +
  'Si quieres seguir conmigo, escribe *menú*.'
);

const RESET_MESSAGE = '🔄 Listo, partimos de cero.\n\n';

// Comandos globales aceptados en cualquier estado.
const CMD_MENU = new Set(['menu', 'menú', '/menu', '/menú', 'inicio', 'volver']);
const CMD_RESET = new Set(['reset', '/reset', 'reiniciar', 'empezar de nuevo']);
const CMD_EXIT = new Set(['salir', '/salir', 'cancelar', 'fin', 'terminar']);
const CMD_HUMAN = new Set(['humano', '/humano', 'agente', 'persona', 'operador']);
const CMD_HELP = new Set(['ayuda', '/ayuda', '/help', 'help', '?']);

const HELP_MESSAGE = (
  '🆘 *Comandos disponibles*\n\n' +
  '• *menú* — vuelve al menú principal\n' +
  '• *salir* — termina la conversación\n' +
  '• *humano* — solicita un agente humano\n' +
  '• *ayuda* — muestra este mensaje\n\n' +
  'En preguntas con opciones, responde con el *número* o el *texto* de la opción.'
);

const GREETINGS = [
  'hola', 'hi', 'hello', 'hey', 'buenas', 'buenos dias', 'buenos días',
  'buenas tardes', 'buenas noches', 'ola',
];

// ---------------------------------------------------------------------------
// Helpers: normalización y matching de inputs
// ---------------------------------------------------------------------------
function normalizeText(s) {
  return (s || '')
    .toString()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

function isGreeting(s) {
  const n = normalizeText(s);
  return GREETINGS.some((g) => n === g || n.startsWith(g + ' ') || n.startsWith(g + ','));
}

function isCommand(text, set) {
  const n = normalizeText(text).replace(/\s+/g, ' ');
  return set.has(n);
}

const WORD_NUMBERS = {
  uno: 1, una: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5,
  seis: 6, siete: 7, ocho: 8, nueve: 9, diez: 10,
};
const KEYCAPS = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'];

function parseChoiceNumber(input, max) {
  const raw = (input || '').trim();
  for (let i = 0; i < KEYCAPS.length; i++) {
    if (raw.includes(KEYCAPS[i]) && i >= 1 && i <= max) return i;
  }
  const stripped = raw.replace(/[.\)\-:•]/g, ' ').trim();
  const tokens = normalizeText(stripped).split(/\s+/);
  for (const t of tokens) {
    const n = parseInt(t, 10);
    if (!isNaN(n) && n >= 1 && n <= max) return n;
    if (t in WORD_NUMBERS) {
      const w = WORD_NUMBERS[t];
      if (w >= 1 && w <= max) return w;
    }
  }
  return null;
}

/**
 * Mapea respuesta libre del usuario al `value` de una choice.
 *   1) número (1..N), keycap, palabra ("uno","dos"...)
 *   2) match exacto contra value/label (normalizado)
 *   3) sinónimos opcionales en `synonyms`
 *   4) match parcial label⊂input o input⊂label
 *   5) fallback: input original
 */
function mapChoice(userInput, choices) {
  if (!choices || choices.length === 0) return userInput;

  const num = parseChoiceNumber(userInput, choices.length);
  if (num != null) return choices[num - 1].value;

  const n = normalizeText(userInput);
  if (!n) return userInput;

  for (const c of choices) {
    if (normalizeText(c.value) === n) return c.value;
    if (normalizeText(c.label) === n) return c.value;
  }
  for (const c of choices) {
    const syns = (c.synonyms || []).map(normalizeText);
    if (syns.includes(n)) return c.value;
  }
  for (const c of choices) {
    const labelN = normalizeText(c.label);
    if (labelN.includes(n) || n.includes(labelN)) return c.value;
  }
  return userInput;
}

function formatMessage(text, choices) {
  if (!choices || choices.length === 0) return text;
  const lines = [text, ''];
  choices.forEach((c, i) => {
    lines.push(`${i + 1}️⃣  ${c.label}`);
  });
  lines.push('', '_Responde con el *número* o el texto de la opción._');
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Typing indicator + ack >2s + chunking
// ---------------------------------------------------------------------------
async function getChat(client, chatId) {
  try {
    return await client.getChatById(chatId);
  } catch {
    return null;
  }
}

async function withTyping(client, chatId, fn, opts = {}) {
  const ackMs = opts.ackMs ?? 2000;
  const ackText = opts.ackText ?? '🔎 Estoy revisando esto…';

  const chat = await getChat(client, chatId);
  let typingTimer = null;
  let ackTimer = null;
  try {
    if (chat) {
      await chat.sendStateTyping().catch(() => {});
      typingTimer = setInterval(() => {
        chat.sendStateTyping().catch(() => {});
      }, 15000);
    }
    ackTimer = setTimeout(() => {
      client.sendMessage(chatId, ackText).catch(() => {});
    }, ackMs);

    return await fn();
  } finally {
    if (ackTimer) clearTimeout(ackTimer);
    if (typingTimer) clearInterval(typingTimer);
    if (chat) chat.clearState().catch(() => {});
  }
}

async function sendChunked(client, chatId, text, opts = {}) {
  const delayMs = opts.delayMs ?? 350;
  const chunks = chunkResponse(text, 900);
  for (let i = 0; i < chunks.length; i++) {
    await client.sendMessage(chatId, chunks[i]);
    if (i < chunks.length - 1) {
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
}

// ---------------------------------------------------------------------------
// Resumen para reclamo CMF
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Comandos globales
// ---------------------------------------------------------------------------
async function handleGlobalCommand(chatId, body, client) {
  if (isCommand(body, CMD_HELP)) {
    await client.sendMessage(chatId, HELP_MESSAGE);
    return true;
  }
  if (isCommand(body, CMD_HUMAN)) {
    await client.sendMessage(chatId, HUMAN_HANDOFF);
    return true;
  }
  if (isCommand(body, CMD_EXIT)) {
    stateManager.delete(chatId);
    await client.sendMessage(
      chatId,
      '👋 Conversación cerrada. Escríbeme *hola* cuando quieras retomar.'
    );
    return true;
  }
  if (isCommand(body, CMD_RESET)) {
    stateManager.delete(chatId);
    await client.sendMessage(chatId, RESET_MESSAGE + WELCOME_MESSAGE);
    stateManager.set(chatId, { topic: 'welcome', stepId: 'menu', data: {} });
    return true;
  }
  if (isCommand(body, CMD_MENU)) {
    const state = stateManager.get(chatId) || {};
    state.topic = 'welcome';
    state.stepId = 'menu';
    state.data = {};
    stateManager.set(chatId, state);
    await client.sendMessage(chatId, WELCOME_MESSAGE);
    return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Handler principal
// ---------------------------------------------------------------------------
async function handleMessage(message, client) {
  if (message.fromMe) return;

  const chatId = message.from;
  const body = (message.body || '').trim();
  console.log(`[MessageHandler] Received: chatId=${chatId}, body="${body.substring(0, 50)}"`);

  if (!body && !message.hasMedia) {
    await client.sendMessage(chatId, 'Por favor escríbeme tu consulta o selecciona una opción. 😊');
    return;
  }

  // 1) Comandos globales
  if (await handleGlobalCommand(chatId, body, client)) return;

  // 2) Adjuntos
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

  // 3) Estado
  let state = stateManager.get(chatId);
  console.log(`[MessageHandler] State: ${state ? `topic=${state.topic}, step=${state.stepId}` : 'null'}`);

  if (!state) {
    if (isGreeting(body)) {
      await client.sendMessage(chatId, WELCOME_MESSAGE);
      stateManager.set(chatId, { topic: 'welcome', stepId: 'menu', data: {} });
      return;
    }
    await handleBackendQuery(chatId, fullMessage, null, client);
    return;
  }

  if (state.topic === 'welcome') {
    const selection = parseChoiceNumber(body, 5);
    if (selection === 1) {
      state.topic = 'reclamo-cmf';
      state.stepId = 'bienvenida';
      stateManager.set(chatId, state);
      const question = templateEngine.getQuestion('reclamo-cmf', 'bienvenida', {});
      const choices = templateEngine.getChoices('reclamo-cmf', 'bienvenida');
      await client.sendMessage(chatId, formatMessage(question, choices));
      return;
    }
    if (selection === 2 || selection === 3 || selection === 4 || selection === 5) {
      state.topic = 'default';
      stateManager.set(chatId, state);
      await client.sendMessage(chatId, 'Cuéntame tu consulta en detalle y te ayudaré. 👇');
      return;
    }
    state.topic = 'default';
    stateManager.set(chatId, state);
    await handleBackendQuery(chatId, fullMessage, state.conversationId, client);
    return;
  }

  if (state.topic === 'default') {
    if (isGreeting(body)) {
      state.topic = 'welcome';
      state.stepId = 'menu';
      state.data = {};
      stateManager.set(chatId, state);
      await client.sendMessage(chatId, WELCOME_MESSAGE);
      return;
    }
    await handleBackendQuery(chatId, fullMessage, state.conversationId, client);
    return;
  }

  await handleTemplateStep(chatId, body, state, client);
}

// ---------------------------------------------------------------------------
// Backend con typing/ack/chunking
// ---------------------------------------------------------------------------
async function handleBackendQuery(chatId, message, conversationId, client) {
  let state = stateManager.get(chatId);
  if (!state) {
    state = stateManager.set(chatId, { topic: 'default', stepId: null, data: {} });
  }

  let response;
  try {
    response = await withTyping(client, chatId, async () => {
      const payload = { message };
      if (conversationId) payload.conversation_id = conversationId;
      return await apiClient.chat(payload);
    });
  } catch (err) {
    console.error('[MessageHandler] Backend error:', err.message);
    await client.sendMessage(
      chatId,
      '⚠️ Hubo un problema procesando tu consulta. Intenta nuevamente en unos segundos.\n' +
      '_Si persiste, escribe *humano* para que te derive._'
    );
    return;
  }

  state.conversationId = response.conversation_id;
  stateManager.updateActivity(chatId);

  const intencion = (response.intencion || '').toUpperCase();
  const organismo = (response.organismo_detectado || '').toLowerCase();
  console.log(`[MessageHandler] Backend response: intencion=${intencion}, organismo=${organismo}`);

  if (intencion.includes('RECLAMO') && organismo === 'cmf') {
    state.topic = 'reclamo-cmf';
    state.stepId = 'bienvenida';
    stateManager.set(chatId, state);
    await sendChunked(client, chatId, formatForWhatsApp(response.response));
    const question = templateEngine.getQuestion('reclamo-cmf', 'bienvenida', {});
    const choices = templateEngine.getChoices('reclamo-cmf', 'bienvenida');
    await client.sendMessage(chatId, formatMessage(question, choices));
    return;
  }

  if (intencion === 'ALERTA') {
    await sendChunked(client, chatId, formatForWhatsApp(response.response));
    state.topic = 'welcome';
    state.stepId = 'menu';
    stateManager.set(chatId, state);
    await client.sendMessage(chatId, WELCOME_MESSAGE);
    return;
  }

  await sendChunked(client, chatId, formatForWhatsApp(response.response));
}

// ---------------------------------------------------------------------------
// Template step (con validadores opcionales)
// ---------------------------------------------------------------------------
async function handleTemplateStep(chatId, userInput, state, client) {
  const currentStep = templateEngine.getStep(state.topic, state.stepId);
  if (!currentStep) {
    state.topic = 'default';
    state.stepId = null;
    stateManager.set(chatId, state);
    await client.sendMessage(chatId, 'Parece que hubo un problema. Empecemos de nuevo:\n\n' + WELCOME_MESSAGE);
    return;
  }

  const choices = templateEngine.getChoices(state.topic, state.stepId);
  let mappedInput = mapChoice(userInput, choices);

  if (currentStep.validate) {
    const result = validate(currentStep.validate, mappedInput);
    if (!result.ok) {
      await client.sendMessage(
        chatId,
        `❌ ${result.error}\n\n${templateEngine.getQuestion(state.topic, state.stepId, state.data)}`
      );
      return;
    }
    mappedInput = result.value;
  }

  const stepResult = templateEngine.processStep(chatId, mappedInput, state);

  if (stepResult.exitToDefault) {
    state.topic = 'default';
    state.stepId = null;
    stateManager.set(chatId, state);
    await handleBackendQuery(chatId, userInput, state.conversationId, client);
    return;
  }

  if (stepResult.action === 'complete') {
    const summary = buildSummary(stepResult.data);
    try {
      const response = await withTyping(client, chatId, async () =>
        apiClient.chat({ message: summary, conversation_id: state.conversationId })
      );
      await sendChunked(client, chatId, formatForWhatsApp(response.response));
    } catch (err) {
      console.error('[MessageHandler] Error sending summary:', err.message);
      await client.sendMessage(
        chatId,
        '⚠️ Hubo un problema enviando tu caso al análisis. Tu información fue guardada. ' +
        'Escribe *menú* para volver a empezar.'
      );
      return;
    }
    state.topic = 'welcome';
    state.stepId = 'menu';
    state.data = {};
    stateManager.set(chatId, state);
    await client.sendMessage(
      chatId,
      '\n¿Necesitas algo más? Escribe *menú* para ver las opciones o *salir* para terminar.'
    );
    return;
  }

  if (stepResult.action === 'ask') {
    stateManager.set(chatId, state);
    const question = templateEngine.getQuestion(state.topic, stepResult.step.id, state.data);
    const nextChoices = templateEngine.getChoices(state.topic, stepResult.step.id);
    await client.sendMessage(chatId, formatMessage(question, nextChoices));
    return;
  }

  state.topic = 'default';
  stateManager.set(chatId, state);
  await handleBackendQuery(chatId, userInput, state.conversationId, client);
}

module.exports = { handleMessage };
