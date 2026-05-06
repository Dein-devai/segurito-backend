/**
 * Mock Backend para probar el WhatsApp Bridge sin depender del backend real.
 *
 * Levantar: node tests-whatsapp/mock-backend.js
 * Puerto por defecto: 9000
 * Configurable: PORT=9001 node tests-whatsapp/mock-backend.js
 */

const http = require('http');
const url = require('url');

const PORT = process.env.PORT || 9000;

function detectOrganismo(message) {
  const m = message.toLowerCase();
  if (m.includes('banco') || m.includes('afp') || m.includes('seguro') || m.includes('mutuaria') || m.includes('corredora') || m.includes('tarjeta')) return 'cmf';
  if (m.includes('celular') || m.includes('tienda') || m.includes('retail') || m.includes('producto defectuoso')) return 'sernac';
  if (m.includes('iva') || m.includes('sii') || m.includes('impuesto') || m.includes('boleta')) return 'sii';
  if (m.includes('pizza') || m.includes('comida') || m.includes('restaurante')) return null;
  if (m.includes('premio') || m.includes('deposit') || m.includes('fraude') || m.includes('estafa') || m.includes('llamaron')) return 'ALERTA';
  return 'cmf'; // default por MVP
}

function detectIntencion(message, organismo) {
  const m = message.toLowerCase();
  if (organismo === 'ALERTA') return 'ALERTA';
  if (m.includes('quiero pedir') || m.includes('pizza')) return 'OUT_OF_SCOPE';
  if (m.includes('cómo') || m.includes('consulta') || m.includes('duda')) return 'CONSULTA';
  if (m.includes('reclamo') || m.includes('problema') || m.includes('cobro') || m.includes('no me quiere')) return 'RECLAMO';
  return 'CONSULTA';
}

function buildResponse(message, conversationId) {
  const organismo = detectOrganismo(message);
  const intencion = detectIntencion(message, organismo);

  let response = '';
  let organismo_detectado = organismo;

  if (intencion === 'ALERTA') {
    response = '⚠️ ALERTA: No entregues datos personales ni realices depósitos. Esto es una estafa conocida. Denuncia en PDI (134) o en www.fiscalia.gob.cl.';
    organismo_detectado = null;
  } else if (intencion === 'OUT_OF_SCOPE') {
    response = 'Soy Segurito, asistente de organismos del Estado de Chile (CMF, SERNAC, SII). No puedo ayudarte con pedidos de comida ni temas fuera de servicios públicos chilenos. ¿Tienes alguna consulta sobre productos o servicios financieros?';
    organismo_detectado = null;
  } else if (organismo === 'sernac') {
    response = 'Según el análisis de tu consulta, este caso corresponde a SERNAC (Servicio Nacional del Consumidor). Te recomiendo contactarlos:\n\nWeb: www.sernac.cl\nFono: 800 700 100\nApp: SERNAC Chile\n\nLey aplicable: Ley 19.496 sobre Protección al Consumidor.';
  } else if (organismo === 'sii') {
    response = 'Según el análisis de tu consulta, este caso corresponde al SII (Servicio de Impuestos Internos).\n\nWeb: www.sii.cl\nFono: 600 363 363\n\nRecuerda que para devoluciones de IVA necesitas boleta electrónica.';
  } else if (intencion === 'RECLAMO') {
    response = 'Detecté un posible reclamo ante la CMF. Para orientarte mejor, necesito hacerte algunas preguntas. ¿Confirmas que quieres continuar con un reclamo formal?';
  } else {
    response = 'Entiendo tu consulta. Según la normativa vigente, te recomiendo revisar los canales oficiales de la CMF en cmfchile.cl. ¿Necesitas que busque un servicio específico?';
  }

  return {
    interaction_id: `mock-${Date.now()}`,
    conversation_id: conversationId || `mock-conv-${Date.now()}`,
    response,
    organismo_detectado,
    intencion,
    servicio_id: null,
    servicios_encontrados: [],
    requiere_confirmacion: intencion === 'RECLAMO',
    tools_used: [],
    iterations: 1,
    elapsed_ms: 150,
    reasoning: [
      {
        model: 'mock',
        phase: 'mock',
        reason: 'keyword matching',
        thinking: null,
        elapsed_ms: 150,
        input_tokens: 50,
        output_tokens: 100,
        cache_read_tokens: 0,
        cache_creation_tokens: 0,
        cost_usd: 0.0
      }
    ],
    model_used_final: 'mock',
    total_input_tokens: 50,
    total_output_tokens: 100,
    total_cache_read_tokens: 0,
    total_cache_creation_tokens: 0,
    total_cost_usd: 0.0
  };
}

const server = http.createServer((req, res) => {
  const parsed = url.parse(req.url, true);
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (req.method === 'GET' && parsed.pathname === '/health') {
    res.writeHead(200);
    res.end(JSON.stringify({ status: 'ok', model: 'mock', organismos: ['cmf', 'sernac', 'sii', 'legal'], prompt_version: 'mock-v1' }));
    return;
  }

  if (req.method === 'POST' && parsed.pathname === '/chat') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const payload = JSON.parse(body);
        const result = buildResponse(payload.message || '', payload.conversation_id);
        res.writeHead(200);
        res.end(JSON.stringify(result));
      } catch (e) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, () => {
  console.log(`Mock backend listening on http://localhost:${PORT}`);
  console.log('Endpoints:');
  console.log(`  GET  http://localhost:${PORT}/health`);
  console.log(`  POST http://localhost:${PORT}/chat`);
});
