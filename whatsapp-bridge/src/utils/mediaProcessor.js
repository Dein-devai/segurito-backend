const MAX_ATTACHMENT_MB = parseInt(process.env.MAX_ATTACHMENT_MB, 10) || 5;
const MAX_ATTACHMENT_BYTES = MAX_ATTACHMENT_MB * 1024 * 1024;

/**
 * Procesa archivos adjuntos de WhatsApp.
 * Para el MVP: descarga y valida tamaño. No hace OCR.
 * @param {import('whatsapp-web.js').Message} message
 * @returns {Promise<{mimeType: string, filename: string, base64Data: string, sizeBytes: number, description?: string} | {error: string}>}
 */
async function processMedia(message) {
  try {
    const media = await message.downloadMedia();
    if (!media) {
      return { error: 'No se pudo descargar el archivo adjunto. Intenta enviarlo de nuevo.' };
    }

    const sizeBytes = Math.ceil((media.data.length * 3) / 4);
    if (sizeBytes > MAX_ATTACHMENT_BYTES) {
      return {
        error: `El archivo es muy grande (máximo ${MAX_ATTACHMENT_MB}MB). Intenta con un archivo más pequeño.`,
      };
    }

    return {
      mimeType: media.mimetype,
      filename: media.filename || `adjunto.${media.mimetype.split('/')[1] || 'bin'}`,
      base64Data: media.data,
      sizeBytes,
      description: `[Archivo adjunto: ${media.filename || 'documento'}]`,
    };
  } catch (err) {
    console.error('[MediaProcessor] Error processing media:', err.message);
    return { error: 'Error al procesar el archivo adjunto.' };
  }
}

module.exports = { processMedia };