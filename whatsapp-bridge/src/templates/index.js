const path = require('path');

// Cargar templates desde JSON
const reclamoCmfJson = require('../../plan/templates/reclamo-cmf.json');
const consultaRapidaJson = require('../../plan/templates/consulta-rapida.json');
const derivacionJson = require('../../plan/templates/derivacion.json');

/**
 * Template de reclamo CMF — máquina de estados.
 */
const reclamoCmf = {
  _steps: {},
  _transitions: {},

  init() {
    this._steps = {};
    for (const step of reclamoCmfJson.steps) {
      this._steps[step.id] = step;
    }
    this._transitions = reclamoCmfJson.transitions || {};
  },

  getStep(stepId) {
    return this._steps[stepId] || null;
  },

  getFirstStep() {
    return this._steps['bienvenida'] || null;
  },

  getTransition(stepId, userResponse) {
    const trans = this._transitions[stepId];
    if (!trans || !trans.onAnswer) return null;

    const lower = userResponse.toLowerCase().trim();
    for (const [key, nextStep] of Object.entries(trans.onAnswer)) {
      if (key === 'default') continue;
      if (lower.includes(key)) return nextStep;
    }
    return trans.onAnswer['default'] || null;
  },
};

/**
 * Template de consulta rápida — envío directo al backend.
 */
const consultaRapida = {
  getStep(stepId) {
    if (stepId === 'envio_libre') {
      return { id: 'envio_libre', type: 'backend_call', question: 'generado_por_backend', saveAs: null, next: null };
    }
    return null;
  },

  getFirstStep() {
    return { id: 'envio_libre', type: 'backend_call', question: 'generado_por_backend', saveAs: null, next: null };
  },

  getTransition() {
    return null;
  },
};

/**
 * Template de derivación — informa al usuario a dónde derivar.
 */
const derivacion = {
  _steps: {},

  init() {
    this._steps = {};
    for (const step of derivacionJson.steps) {
      this._steps[step.id] = step;
    }
  },

  getStep(stepId) {
    return this._steps[stepId] || null;
  },

  getFirstStep() {
    return this._steps['mensaje_derivacion'] || null;
  },

  getTransition() {
    return null;
  },
};

// Inicializar templates con datos JSON
reclamoCmf.init();
derivacion.init();

module.exports = { reclamoCmf, consultaRapida, derivacion };