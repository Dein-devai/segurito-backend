/**
 * Template de consulta rápida — envío directo al backend.
 */
const consultaRapida = {
  getStep(stepId) {
    if (stepId === 'envio_libre') {
      return {
        id: 'envio_libre',
        type: 'backend_call',
        question: 'generado_por_backend',
        saveAs: null,
        next: null,
      };
    }
    return null;
  },

  getFirstStep() {
    return {
      id: 'envio_libre',
      type: 'backend_call',
      question: 'generado_por_backend',
      saveAs: null,
      next: null,
    };
  },

  getTransition() {
    return null;
  },
};

module.exports = consultaRapida;