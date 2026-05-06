'use strict';
/**
 * index.js (templates) — Registro de todos los templates disponibles.
 */

const reclamoCMF = require('./reclamo-cmf');
const consultaRapida = require('./consulta-rapida');
const derivacion = require('./derivacion');

const TEMPLATES = {
  'reclamo-cmf': reclamoCMF,
  'consulta-rapida': consultaRapida,
  derivacion,
};

module.exports = TEMPLATES;
