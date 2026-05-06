'use strict';
/**
 * stateManager.js — Mapa en memoria chatId → ConversationState.
 *
 * Mantiene el estado de cada conversación WhatsApp con TTL configurable.
 * El purge se ejecuta cada 5 minutos.
 */

const { v4: uuidv4 } = require('crypto');

const TTL_MS = (parseInt(process.env.SESSION_TTL_MINUTES, 10) || 30) * 60 * 1000;
const PURGE_INTERVAL_MS = 5 * 60 * 1000;

/** @type {Map<string, object>} */
const _store = new Map();

/**
 * Genera un UUID v4 sin dependencias externas (usa crypto nativo de Node.js).
 */
function _uuid() {
  // crypto.randomUUID() disponible desde Node.js 14.17
  try {
    return require('crypto').randomUUID();
  } catch {
    // fallback manual si el entorno no lo soporta
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }
}

function get(chatId) {
  return _store.get(chatId) || null;
}

/**
 * Crea o reemplaza el estado para un chatId.
 * Si no se incluye conversationId, se genera uno nuevo.
 */
function set(chatId, state) {
  const now = Date.now();
  _store.set(chatId, {
    chatId,
    conversationId: state.conversationId || _uuid(),
    topic: state.topic || 'default',
    stepId: state.stepId || null,
    data: state.data || {},
    createdAt: state.createdAt || now,
    lastActivity: now,
  });
}

function del(chatId) {
  _store.delete(chatId);
}

function updateActivity(chatId) {
  const s = _store.get(chatId);
  if (s) s.lastActivity = Date.now();
}

function purgeExpired() {
  const now = Date.now();
  for (const [chatId, state] of _store.entries()) {
    if (now - state.lastActivity > TTL_MS) {
      _store.delete(chatId);
      console.log(`[stateManager] Sesión expirada eliminada: ${chatId}`);
    }
  }
}

// Purge automático cada 5 minutos.
setInterval(purgeExpired, PURGE_INTERVAL_MS).unref();

module.exports = { get, set, delete: del, updateActivity, purgeExpired };
