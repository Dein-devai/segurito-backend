const reclamoCmfJson = require('../../../plan/templates/reclamo-cmf.json');

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

reclamoCmf.init();

module.exports = reclamoCmf;