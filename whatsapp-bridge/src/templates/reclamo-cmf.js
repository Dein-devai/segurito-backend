'use strict';
/**
 * reclamo-cmf.js — Template de reclamo formal ante la CMF.
 *
 * Importa la definición JSON del plan y expone funciones de transición.
 */

const definition = require('../../../plan/templates/reclamo-cmf.json');

const steps = {};
for (const step of definition.steps) {
  steps[step.id] = step;
}

/**
 * Dada la respuesta del usuario y el stepId actual, devuelve el siguiente stepId
 * aplicando las reglas especiales de transición.
 *
 * @param {string} stepId — paso actual
 * @param {string} userResponse — respuesta del usuario (texto libre o elección)
 * @param {object} data — datos acumulados del estado
 * @returns {string|null} — siguiente stepId, o null si el template termina
 */
function getNextStep(stepId, userResponse, data) {
  const normalized = userResponse.trim().toLowerCase();

  // Regla: bienvenida → si el usuario dice "consulta" o "pregunta", salir del template.
  if (stepId === 'bienvenida' && (normalized.includes('consulta') || normalized.includes('pregunta'))) {
    return '__EXIT_TO_DEFAULT__';
  }

  // Regla: confirmar_envio → "no" o "editar" vuelven a descripcion_problema.
  if (stepId === 'confirmar_envio' && (normalized === 'no' || normalized.includes('editar'))) {
    return 'descripcion_problema';
  }

  // Regla: adjuntar_evidencia → "saltar" o "no tengo" avanza sin guardar evidencia.
  if (stepId === 'adjuntar_evidencia' && (normalized === 'saltar' || normalized.includes('no tengo'))) {
    return steps['adjuntar_evidencia']?.next || null;
  }

  const current = steps[stepId];
  if (!current) return null;
  return current.next || null;
}

/**
 * Retorna el texto de la pregunta para un paso dado.
 * Reemplaza placeholders {clave} con valores de data.
 *
 * @param {string} stepId
 * @param {object} data
 * @returns {string}
 */
function getQuestion(stepId, data) {
  const step = steps[stepId];
  if (!step) return '(paso desconocido)';
  let question = step.question;
  // Reemplazar placeholders con datos acumulados
  for (const [key, value] of Object.entries(data)) {
    question = question.replace(new RegExp(`\\{${key}\\}`, 'g'), value || '—');
  }
  return question;
}

/**
 * Retorna las opciones de un paso tipo "choice".
 * @param {string} stepId
 * @returns {Array<{label: string, value: string}>}
 */
function getChoices(stepId) {
  const step = steps[stepId];
  return step?.choices || [];
}

/**
 * Retorna la clave en la que guardar la respuesta del usuario.
 * @param {string} stepId
 * @returns {string|null}
 */
function getSaveAs(stepId) {
  return steps[stepId]?.saveAs || null;
}

/**
 * Retorna el tipo de paso ('text', 'choice', 'document', 'confirm', 'backend_call').
 * @param {string} stepId
 * @returns {string}
 */
function getStepType(stepId) {
  return steps[stepId]?.type || 'text';
}

const FIRST_STEP = definition.steps[0]?.id || 'bienvenida';

module.exports = { getNextStep, getQuestion, getChoices, getSaveAs, getStepType, FIRST_STEP, steps };
