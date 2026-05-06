'use strict';
/**
 * client.js — Factory de whatsapp-web.js Client.
 *
 * Crea y configura el cliente con LocalAuth. Registra los eventos de ciclo de
 * vida y maneja un único reintento de reconexión en caso de desconexión.
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const WA_CLIENT_ID = process.env.WA_CLIENT_ID || 'segurito-hackathon';
const WA_DATA_PATH = process.env.WA_DATA_PATH || './.wwebjs_auth';

let _reconnecting = false;

/**
 * Crea e inicializa un cliente WhatsApp.
 * @returns {Client} instancia configurada (aún no inicializada).
 */
function createClient() {
  const client = new Client({
    authStrategy: new LocalAuth({
      clientId: WA_CLIENT_ID,
      dataPath: WA_DATA_PATH,
    }),
    puppeteer: {
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    },
  });

  client.on('qr', (qr) => {
    console.log('[bridge] Escanea el código QR para conectar WhatsApp:');
    qrcode.generate(qr, { small: true });
  });

  client.on('authenticated', () => {
    console.log('[bridge] Autenticación exitosa.');
    _reconnecting = false;
  });

  client.on('auth_failure', (msg) => {
    console.error('[bridge] Error de autenticación:', msg);
  });

  client.on('ready', () => {
    console.log('[bridge] Client is ready!');
    _reconnecting = false;
  });

  client.on('disconnected', (reason) => {
    console.warn('[bridge] Desconectado:', reason);
    if (!_reconnecting) {
      _reconnecting = true;
      console.log('[bridge] Intentando reconectar en 5 s…');
      setTimeout(() => {
        client.initialize().catch((err) => {
          console.error('[bridge] Reconexión falló:', err.message);
          _reconnecting = false;
        });
      }, 5000);
    }
  });

  return client;
}

module.exports = { createClient };
