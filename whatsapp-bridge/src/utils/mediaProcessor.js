'use strict';
/**
 * mediaProcessor.js — Descarga y valida adjuntos de WhatsApp.
 *
 * Solo para imágenes en el MVP. PDFs y otros tipos se documentan como
 * "recibidos" pero se envían al backend sin base64 (usando description).
 */

const MAX_MB = parseFloat(process.env.MAX_ATTACHMENT_MB) || 5;
const MAX_B64_CHARS = MAX_MB * 1024 * 1024 * (4 / 3); // bytes → chars base64

const SUPPORTED_MIME = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);

/**
 * Descarga el media de un mensaje WhatsApp y retorna un objeto Attachment
 * compatible con el schema del backend.
 *
 * @param {object} message — mensaje de whatsapp-web.js con hasMedia=true
 * @returns {Promise<{ok: true, attachment: object} | {ok: false, reason: string}>}
 */
async function processMedia(message) {
  let media;
  try {
    media = await message.downloadMedia();
  } catch (err) {
    return { ok: false, reason: `No se pudo descargar el adjunto: ${err.message}` };
  }

  if (!media) {
    return { ok: false, reason: 'El adjunto llegó vacío.' };
  }

  const { mimetype, data: base64Data, filename } = media;
  const safeFilename = filename || `adjunto.${mimetype.split('/')[1] || 'bin'}`;

  // Validar tamaño
  if (base64Data.length > MAX_B64_CHARS) {
    return {
      ok: false,
      reason: `El archivo es muy grande. Máximo ${MAX_MB} MB.`,
    };
  }

  // Solo imágenes en el MVP
  if (!SUPPORTED_MIME.has(mimetype)) {
    // Para tipos no soportados como imágenes, informar que fue recibido.
    return {
      ok: true,
      attachment: {
        mime_type: mimetype,
        filename: safeFilename,
        base64_data: '',
        description: `[Documento recibido: ${safeFilename}. Tipo: ${mimetype}. El bridge no procesó el contenido.]`,
      },
    };
  }

  return {
    ok: true,
    attachment: {
      mime_type: mimetype,
      filename: safeFilename,
      base64_data: base64Data,
      description: null,
    },
  };
}

module.exports = { processMedia };
