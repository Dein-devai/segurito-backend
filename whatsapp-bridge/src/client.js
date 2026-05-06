const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

/**
 * Crea y configura el cliente de whatsapp-web.js.
 */
function createClient() {
  const clientId = process.env.WA_CLIENT_ID || 'segurito-hackathon';
  const dataPath = process.env.WA_DATA_PATH || './.wwebjs_auth';

  const client = new Client({
    authStrategy: new LocalAuth({ clientId, dataPath }),
    puppeteer: {
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
      ],
    },
  });

  client.on('qr', (qr) => {
    console.log('[WhatsApp] Escanea este QR con tu teléfono:');
    qrcode.generate(qr, { small: true });
  });

  client.on('ready', () => {
    console.log('[WhatsApp] Client is ready!');
  });

  client.on('authenticated', () => {
    console.log('[WhatsApp] Autenticado exitosamente.');
  });

  client.on('auth_failure', (msg) => {
    console.error('[WhatsApp] Error de autenticación:', msg);
  });

  client.on('disconnected', (reason) => {
    console.warn('[WhatsApp] Desconectado:', reason);
    console.log('[WhatsApp] Intentando reconectar...');
    setTimeout(() => {
      client.initialize();
    }, 5000);
  });

  return client;
}

module.exports = { createClient };