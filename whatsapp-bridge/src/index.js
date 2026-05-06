require('dotenv').config();

const { createClient } = require('./client');
const { handleMessage } = require('./messageHandler');
const ApiClient = require('./apiClient');

async function main() {
  console.log('[Bridge] Segurito WhatsApp Bridge starting...');

  // Verificar que el backend está disponible
  const api = new ApiClient();
  const health = await api.health();
  if (!health) {
    console.warn('[Bridge] WARNING: Backend not reachable. Messages will fail until backend is up.');
    console.warn('[Bridge] Make sure the backend is running: uvicorn main:app --reload');
  } else {
    console.log('[Bridge] Backend is healthy:', health.status);
  }

  // Crear cliente WhatsApp
  const client = createClient();

  // Registrar handler de mensajes
  client.on('message', async (message) => {
    try {
      await handleMessage(message, client);
    } catch (err) {
      console.error('[Bridge] Unhandled error in message handler:', err);
    }
  });

  // Inicializar
  await client.initialize();
  console.log('[Bridge] WhatsApp client initialized. Waiting for messages...');

  // Graceful shutdown
  const shutdown = async (signal) => {
    console.log(`\n[Bridge] Received ${signal}. Shutting down gracefully...`);
    await client.destroy();
    process.exit(0);
  };

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
}

main().catch((err) => {
  console.error('[Bridge] Fatal error:', err);
  process.exit(1);
});