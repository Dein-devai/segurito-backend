'use strict';
/**
 * index.js — Punto de entrada del WhatsApp Bridge.
 *
 * Orden de arranque:
 * 1. Cargar variables de entorno (.env).
 * 2. Verificar que el backend responde /health.
 * 3. Crear e inicializar el cliente WhatsApp.
 * 4. Registrar el handler de mensajes.
 * 5. Graceful shutdown en SIGINT.
 */

require('dotenv').config();

const { createClient } = require('./client');
const { handleMessage } = require('./messageHandler');
const apiClient = require('./apiClient');

const HEALTH_RETRY_INTERVAL_MS = 3000;
const HEALTH_MAX_RETRIES = 10;

/**
 * Espera hasta que el backend responda /health (con reintentos).
 */
async function waitForBackend() {
  console.log(`[bridge] Verificando backend en ${process.env.BACKEND_URL || 'http://localhost:8000'}…`);
  for (let i = 1; i <= HEALTH_MAX_RETRIES; i++) {
    try {
      const h = await apiClient.health();
      console.log(`[bridge] Backend disponible. Status: ${h.status}`);
      return;
    } catch (err) {
      console.warn(`[bridge] Intento ${i}/${HEALTH_MAX_RETRIES} fallido: ${err.message}`);
      if (i < HEALTH_MAX_RETRIES) {
        await new Promise((r) => setTimeout(r, HEALTH_RETRY_INTERVAL_MS));
      }
    }
  }
  console.error('[bridge] El backend no respondió después de varios intentos. Abortando.');
  process.exit(1);
}

async function main() {
  await waitForBackend();

  const client = createClient();

  client.on('message', (message) => {
    handleMessage(message, client).catch((err) => {
      console.error('[bridge] Error no capturado en handleMessage:', err.message);
    });
  });

  // Graceful shutdown
  process.on('SIGINT', async () => {
    console.log('\n[bridge] Cerrando conexión WhatsApp…');
    try {
      await client.destroy();
    } catch {
      // ignorar errores al cerrar
    }
    process.exit(0);
  });

  console.log('[bridge] Inicializando cliente WhatsApp…');
  await client.initialize();
}

main().catch((err) => {
  console.error('[bridge] Error fatal:', err.message);
  process.exit(1);
});
