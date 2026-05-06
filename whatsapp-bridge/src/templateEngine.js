const reclamoCmf = require('./templates/reclamo-cmf');
const consultaRapida = require('./templates/consulta-rapida');
const derivacion = require('./templates/derivacion');

/**
 * Registro de templates disponibles.
 */
const TEMPLATES = {
  'reclamo-cmf': reclamoCmf,
  'consulta-rapida': consultaRapida,
  'derivacion': derivacion,
};

/**
 * TemplateEngine — orquesta la máquina de estados de los templates.
 */
class TemplateEngine {
  /**
   * Procesa la respuesta del usuario en el paso actual del template.
   * @param {string} chatId
   * @param {string} userResponse - Texto enviado por el usuario.
   * @param {object} state - Estado actual de la conversación.
   * @returns {{ action: 'ask'|'complete', step?: object, data?: object }}
   */
  processStep(chatId, userResponse, state) {
    const template = TEMPLATES[state.topic];
    if (!template) {
      return { action: 'complete', data: state.data };
    }

    const currentStep = template.getStep(state.stepId);
    if (!currentStep) {
      return { action: 'complete', data: state.data };
    }

    // Guardar respuesta del usuario
    if (currentStep.saveAs) {
      state.data[currentStep.saveAs] = userResponse;
    }

    // Verificar transiciones especiales
    const transition = template.getTransition(state.stepId, userResponse);
    if (transition === 'EXIT_TO_DEFAULT') {
      return { action: 'complete', data: state.data, exitToDefault: true };
    }

    // Determinar siguiente paso
    const nextStepId = transition || currentStep.next;
    if (!nextStepId) {
      // Último paso → completar
      return { action: 'complete', data: state.data };
    }

    const nextStep = template.getStep(nextStepId);
    state.stepId = nextStepId;

    if (nextStep && nextStep.type === 'backend_call') {
      return { action: 'complete', data: state.data };
    }

    return { action: 'ask', step: nextStep };
  }

  /**
   * Retorna el texto de la pregunta para un paso dado.
   * @param {string} topic
   * @param {string} stepId
   * @param {object} data - Datos para interpolar en la pregunta.
   * @returns {string}
   */
  getQuestion(topic, stepId, data = {}) {
    const template = TEMPLATES[topic];
    if (!template) return '';
    const step = template.getStep(stepId);
    if (!step) return '';
    return this._interpolate(step.question, data);
  }

  /**
   * Retorna las opciones para un paso tipo choice.
   * @param {string} topic
   * @param {string} stepId
   * @returns {Array|undefined}
   */
  getChoices(topic, stepId) {
    const template = TEMPLATES[topic];
    if (!template) return undefined;
    const step = template.getStep(stepId);
    if (!step) return undefined;
    return step.choices;
  }

  /**
   * Retorna el primer paso de un template.
   * @param {string} topic
   * @returns {object|null}
   */
  getFirstStep(topic) {
    const template = TEMPLATES[topic];
    if (!template) return null;
    return template.getFirstStep();
  }

  /**
   * Interpola {variables} en un string.
   */
  _interpolate(text, data) {
    return text.replace(/\{(\w+)\}/g, (match, key) => data[key] || match);
  }
}

module.exports = TemplateEngine;