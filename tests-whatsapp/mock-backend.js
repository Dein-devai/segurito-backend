'use strict';
/**
 * mock-backend.js — Mock HTTP server que simula el backend Python.
 *
 * Uso:
 *   node mock-backend.js
 *   PORT=9000 node mock-backend.js
 *
 * Endpoints:
 *   POST /chat  → ChatResponse de ejemplo según keywords en el mensaje.
 *   GET  /health → { status: "ok" }
 */

const http = require('http');

const PORT = parseInt(process.env.PORT || '9000', 10);

let _interactionCounter = 0;

function _uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

/**
 * Genera una ChatResponse simulada según el contenido del mensaje.
 * @param {string} message
 * @param {string|null} conversationId
 * @returns {object}
 */
function buildChatResponse(message, conversationId) {
  _interactionCounter++;
  const msg = (message || '').toLowerCase();
  const id = conversationId || _uuid();

  let organismo = null;
  let intencion = 'CONSULTA';
  let response = 'Hola, soy Segurito. ¿En qué puedo ayudarte?';

  if (msg.includes('banco') || msg.includes('cobro') || msg.includes('tarjeta') || msg.includes('afp') || msg.includes('aseguradora')) {
    organismo = 'cmf';
    intencion = 'RECLAMO_PRODUCTO';
    response =
      'Entiendo que tienes un problema con un producto financiero. ' +
      'El primer paso es reclamar directamente a la entidad. Si no responden en 10 días hábiles, ' +
      'puedes acudir a CMF Online (cmfchile.cl). Ley 19.496 y DFL 3 protegen tus derechos.';
  } else if (msg.includes('celular') || msg.includes('producto defectuoso') || msg.includes('garantía')) {
    organismo = 'sernac';
    intencion = 'RECLAMO';
    response =
      'Este caso corresponde a SERNAC. Puedes presentar tu reclamo en sernac.cl o llamar al 800 700 100.';
  } else if (msg.includes('iva') || msg.includes('renta') || msg.includes('impuesto') || msg.includes('sii')) {
    organismo = 'sii';
    intencion = 'TRAMITE';
    response =
      'Este tema corresponde al SII. Puedes realizar tu trámite en sii.cl o llamar al 22 395 1115.';
  } else if (msg.includes('pizza') || msg.includes('comida') || msg.includes('delivery')) {
    organismo = null;
    intencion = 'OUT_OF_SCOPE';
    response =
      'Lo siento, solo puedo orientarte sobre servicios de organismos del Estado de Chile. ' +
      'No puedo ayudarte con ese tipo de solicitud.';
  } else if (msg.includes('ganador') || msg.includes('premio') || msg.includes('fraude') || msg.includes('estafa')) {
    organismo = null;
    intencion = 'ALERTA';
    response =
      '⚠️ ALERTA: Esta situación tiene características de un posible fraude. ' +
      'No entregues datos personales, claves ni dinero. ' +
      'Si fuiste víctima, denuncia a la PDI (www.pdichile.cl) o llama al 134.';
  } else if (msg.includes('analiza') || msg.includes('reclamo cmf') || msg.includes('normativa')) {
    organismo = 'cmf';
    intencion = 'RECLAMO';
    response =
      'He analizado tu caso. Según la Ley 19.496 y las circulares CMF:\n' +
      '1. Primero debes reclamar directamente a la entidad por escrito.\n' +
      '2. Si no responden en 10 días hábiles, presenta tu reclamo en CMF Online.\n' +
      '3. Adjunta tu estado de cuenta y la comunicación con la entidad.\n' +
      'Canal oficial: cmfchile.cl → "Reclamos"';
  }

  return {
    interaction_id: `mock-${_interactionCounter}-${_uuid()}`,
    conversation_id: id,
    response,
    organismo_detectado: organismo,
    intencion,
    servicio_id: null,
    servicios_encontrados: [],
    requiere_confirmacion: intencion === 'CONSULTA',
    tools_used: [],
    iterations: 1,
    elapsed_ms: Math.floor(Math.random() * 500) + 100,
    reasoning: [],
    model_used_final: 'mock-haiku',
    total_input_tokens: 50,
    total_output_tokens: 80,
    total_cache_read_tokens: 0,
    total_cache_creation_tokens: 0,
    total_cost_usd: 0.0001,
  };
}

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];

  // GET /health
  if (req.method === 'GET' && url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', model: 'mock', organismos: ['cmf', 'sernac', 'sii', 'legal'], prompt_version: 'mock-v1' }));
    return;
  }

  // POST /chat
  if (req.method === 'POST' && url === '/chat') {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      let payload;
      try {
        payload = JSON.parse(body);
      } catch {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ detail: 'Invalid JSON' }));
        return;
      }

      const chatResp = buildChatResponse(payload.message, payload.conversation_id);
      console.log(`[mock] POST /chat msg="${(payload.message || '').slice(0, 60)}" → organismo=${chatResp.organismo_detectado} intencion=${chatResp.intencion}`);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(chatResp));
    });
    return;
  }

  // POST /feedback (stub)
  if (req.method === 'POST' && url === '/feedback') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, interaction_id: 'mock' }));
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ detail: 'Not found' }));
});

server.listen(PORT, () => {
  console.log(`[mock-backend] Escuchando en http://localhost:${PORT}`);
  console.log('[mock-backend] Endpoints: POST /chat  GET /health');
});
