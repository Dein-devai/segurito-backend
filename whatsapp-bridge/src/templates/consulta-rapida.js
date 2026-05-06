'use strict';
/**
 * consulta-rapida.js — Template de consulta libre.
 *
 * No aplica flujo estructurado. El mensaje se envía directamente al backend.
 */

const FIRST_STEP = 'envio_libre';

function getNextStep() { return null; }
function getQuestion() { return null; }
function getChoices() { return []; }
function getSaveAs() { return null; }
function getStepType() { return 'backend_call'; }

module.exports = { getNextStep, getQuestion, getChoices, getSaveAs, getStepType, FIRST_STEP };
