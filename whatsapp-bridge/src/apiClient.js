'use strict';
/**
 * apiClient.js — Cliente HTTP hacia el backend Python (FastAPI).
 *
 * Maneja:
 * - POST /chat con payload { message, conversation_id, attachments? }.
 * - GET /health para verificar disponibilidad.
 * - Rate-limit 429: espera Retry-After y reintenta una vez.
 */

const axios = require('axios');

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const TIMEOUT_MS = parseInt(process.env.BACKEND_TIMEOUT_MS, 10) || 35000;

const _http = axios.create({
  baseURL: BACKEND_URL,
  timeout: TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

/**
 * Espera ms milisegundos.
 * @param {number} ms
 */
function _sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * POST /chat
 * @param {{ message: string, conversation_id?: string, attachments?: object[] }} payload
 * @returns {Promise<object>} ChatResponse del backend
 */
async function chat(payload) {
  let attempt = 0;
  while (attempt < 2) {
    try {
      console.log(`[apiClient] POST /chat attempt=${attempt + 1} msg="${payload.message.slice(0, 60)}"`);
      const { data } = await _http.post('/chat', payload);
      return data;
    } catch (err) {
      if (err.response && err.response.status === 429 && attempt === 0) {
        const retryAfter = parseInt(err.response.headers['retry-after'] || '5', 10);
        console.warn(`[apiClient] 429 recibido. Esperando ${retryAfter}s antes de reintentar…`);
        await _sleep(retryAfter * 1000);
        attempt++;
        continue;
      }
      // Log del error y re-lanzar
      const status = err.response ? err.response.status : 'red';
      console.error(`[apiClient] Error ${status} en POST /chat:`, err.message);
      throw err;
    }
  }
}

/**
 * GET /health
 * @returns {Promise<object>}
 */
async function health() {
  const { data } = await _http.get('/health');
  return data;
}

module.exports = { chat, health };
