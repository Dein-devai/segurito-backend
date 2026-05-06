'use strict';
/**
 * templateEngine.js — Orquesta la máquina de estados de los templates.
 *
 * Responsabilidades:
 * - Cargar todos los templates registrados.
 * - Método processStep: avanza el estado y determina la acción siguiente.
 * - Métodos getQuestion, getChoices: exponen el contenido del paso actual.
 */

const TEMPLATES = require('./templates/index');

/**
 * Avanza el estado de la conversación.
 *
 * @param {string} chatId — identificador de la conversación (solo para logs)
 * @param {string} userResponse — respuesta del usuario al paso actual
 * @param {object} state — estado completo de la conversación
 * @returns {{ action: 'ask', stepId: string } | { action: 'complete', data: object } | { action: 'exit_to_default' }}
 */
function processStep(chatId, userResponse, state) {
  const template = TEMPLATES[state.topic];
  if (!template) {
    console.warn(`[templateEngine] Template desconocido: ${state.topic}`);
    return { action: 'complete', data: state.data };
  }

  const currentStepId = state.stepId;

  // Guardar la respuesta del usuario
  const saveAs = template.getSaveAs(currentStepId);
  if (saveAs) {
    state.data[saveAs] = userResponse;
  }

  const nextStepId = template.getNextStep(currentStepId, userResponse, state.data);

  if (nextStepId === '__EXIT_TO_DEFAULT__') {
    return { action: 'exit_to_default' };
  }

  if (!nextStepId) {
    return { action: 'complete', data: state.data };
  }

  return { action: 'ask', stepId: nextStepId };
}

/**
 * Retorna el texto de la pregunta para el paso indicado.
 * @param {string} topic
 * @param {string} stepId
 * @param {object} data — datos acumulados para reemplazar placeholders
 * @returns {string|null}
 */
function getQuestion(topic, stepId, data = {}) {
  const template = TEMPLATES[topic];
  return template ? template.getQuestion(stepId, data) : null;
}

/**
 * Retorna las opciones de un paso tipo "choice".
 * @param {string} topic
 * @param {string} stepId
 * @returns {Array<{label: string, value: string}>}
 */
function getChoices(topic, stepId) {
  const template = TEMPLATES[topic];
  return template ? template.getChoices(stepId) : [];
}

module.exports = { processStep, getQuestion, getChoices };
