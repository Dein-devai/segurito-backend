const { v4: uuidv4 } = require('crypto');

/**
 * Estado de cada conversación WhatsApp en memoria.
 * TTL: 30 minutos de inactividad. Purge cada 5 minutos.
 */
class StateManager {
  constructor(ttlMinutes = 30, purgeIntervalMinutes = 5) {
    this._states = new Map();
    this._ttlMs = ttlMinutes * 60 * 1000;
    this._purgeIntervalMs = purgeIntervalMinutes * 60 * 1000;
    this._purgeTimer = setInterval(() => this.purgeExpired(), this._purgeIntervalMs);
  }

  get(chatId) {
    const state = this._states.get(chatId);
    if (!state) return null;
    this._updateActivity(chatId);
    return state;
  }

  set(chatId, state) {
    state.chatId = chatId;
    state.lastActivity = Date.now();
    if (!state.createdAt) {
      state.createdAt = Date.now();
    }
    if (!state.conversationId) {
      state.conversationId = crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }
    this._states.set(chatId, state);
    return state;
  }

  delete(chatId) {
    this._states.delete(chatId);
  }

  updateActivity(chatId) {
    const state = this._states.get(chatId);
    if (state) {
      state.lastActivity = Date.now();
    }
  }

  purgeExpired() {
    const now = Date.now();
    let purged = 0;
    for (const [chatId, state] of this._states) {
      if (now - state.lastActivity > this._ttlMs) {
        this._states.delete(chatId);
        purged++;
      }
    }
    if (purged > 0) {
      console.log(`[StateManager] Purged ${purged} expired sessions.`);
    }
  }

  destroy() {
    clearInterval(this._purgeTimer);
  }
}

module.exports = StateManager;