const derivacionJson = require('../../../plan/templates/derivacion.json');

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

derivacion.init();

module.exports = derivacion;