const http = require('http');
const { v4: uuidv4 } = require('crypto');

const PORT = parseInt(process.env.MOCK_PORT, 10) || 9000;

/**
 * Mock backend para probar el bridge sin depender del backend real.
 */
const server = http.createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200);
    res.end(JSON.stringify({ status: 'ok' }));
    return;
  }

  if (req.method === 'POST' && req.url === '/chat') {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      try {
        const payload = JSON.parse(body);
        const message = (payload.message || '').toLowerCase();
        const response = generateMockResponse(message, payload.conversation_id);
        res.writeHead(200);
        res.end(JSON.stringify(response));
      } catch {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Not found' }));
});

function generateMockResponse(message, conversationId) {
  const convId = conversationId || (crypto.randomUUID ? crypto.randomUUID() : `mock-${Date.now()}`);
  const interactionId = crypto.randomUUID ? crypto.randomUUID() : `int-${Date.now()}`;

  // Detectar intención basándose en keywords
  if (message.includes('pizza') || message.includes('comida') || message.includes('receta')) {
    return {
      interaction_id: interactionId,
      conversation_id: convId,
      response: 'Soy Segurito, asistente de organismos del Estado de Chile. No puedo ayudarte con pedidos de comida. ¿Tienes alguna consulta sobre servicios financieros o de organismos del Estado?',
      organismo_detectado: null,
      intencion: 'OUT_OF_SCOPE',
    };
  }

  if (message.includes('fraude') || message.includes('estafa') || message.includes('ganador') || message.includes('premio') || message.includes('deposite')) {
    return {
      interaction_id: interactionId,
      conversation_id: convId,
      response: 'ALERTA: No entregues datos personales ni deposites dinero. Esto parece ser un intento de fraude. Contacta a la PDI al 134 o a Fiscalía si ya entregaste información.',
      organismo_detectado: null,
      intencion: 'ALERTA',
    };
  }

  if (message.includes('celular') || message.includes('retail') || message.includes('tienda') || message.includes('producto defectuoso')) {
    return {
      interaction_id: interactionId,
      conversation_id: convId,
      response: 'Este caso corresponde a SERNAC (Servicio Nacional del Consumidor). Tienes derecho a garantía legal de 3 meses. Contacta a SERNAC: www.sernac.cl o al 800 700 100.',
      organismo_detectado: 'sernac',
      intencion: 'CONSULTA',
    };
  }

  if (message.includes('impuesto') || message.includes('iva') || message.includes('renta') || message.includes('sii')) {
    return {
      interaction_id: interactionId,
      conversation_id: convId,
      response: 'Este caso corresponde al SII (Servicio de Impuestos Internos). Contacta al SII: www.sii.cl o al 600 363 363.',
      organismo_detectado: 'sii',
      intencion: 'CONSULTA',
    };
  }

  if (message.includes('banco') || message.includes('tarjeta') || message.includes('afp') || message.includes('seguro') || message.includes('cobro') || message.includes('mutuaria') || message.includes('reclamo')) {
    return {
      interaction_id: interactionId,
      conversation_id: convId,
      response: 'He identificado que tu caso es un reclamo relacionado con la CMF. Te guiaré paso a paso para formalizar tu reclamo.',
      organismo_detectado: 'cmf',
      intencion: 'RECLAMO',
    };
  }

  // Default: consulta CMF
  return {
    interaction_id: interactionId,
    conversation_id: convId,
    response: 'Hola, soy Segurito, asistente de organismos del Estado de Chile. ¿En qué puedo ayudarte? Cuéntame tu consulta sobre servicios financieros.',
    organismo_detectado: null,
    intencion: 'CONSULTA',
  };
}

server.listen(PORT, () => {
  console.log(`[MockBackend] Running on port ${PORT}`);
  console.log(`[MockBackend] Health: http://localhost:${PORT}/health`);
  console.log(`[MockBackend] Chat: POST http://localhost:${PORT}/chat`);
});