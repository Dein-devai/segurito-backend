'use strict';
/**
 * derivacion.js — Template de derivación a otro organismo.
 *
 * Informa al usuario que el caso corresponde a otro organismo y envía
 * el mensaje al backend para una respuesta detallada.
 */

const FIRST_STEP = 'derivacion';

function getNextStep() { return null; }
function getQuestion() {
  return (
    'Tu caso parece corresponder a otro organismo. ' +
    'Cuéntame más sobre el problema y te orientaré al canal correcto.'
  );
}
function getChoices() { return []; }
function getSaveAs() { return 'descripcion_derivacion'; }
function getStepType() { return 'backend_call'; }

module.exports = { getNextStep, getQuestion, getChoices, getSaveAs, getStepType, FIRST_STEP };
