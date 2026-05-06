"use strict";

/**
 * Trocea respuestas largas en mensajes WhatsApp más naturales.
 *
 * Estrategia:
 *   1. Si el texto es corto (<= maxChars), un solo mensaje.
 *   2. Intenta cortar por dobles saltos de línea (párrafos).
 *   3. Si un párrafo sigue siendo muy largo, corta por oraciones.
 *   4. Une chunks consecutivos hasta llenar maxChars sin pasarse.
 */
function chunkResponse(text, maxChars = 900) {
  const t = (text || "").trim();
  if (!t) return [];
  if (t.length <= maxChars) return [t];

  // 1. Por párrafos.
  const paragraphs = t.split(/\n{2,}/g).map((p) => p.trim()).filter(Boolean);

  // 2. Si algún párrafo excede maxChars, lo subdividimos por oraciones.
  const pieces = [];
  for (const p of paragraphs) {
    if (p.length <= maxChars) {
      pieces.push(p);
      continue;
    }
    const sentences = p.match(/[^.!?\n]+[.!?]+|\S[^.!?\n]*$/g) || [p];
    for (const s of sentences) pieces.push(s.trim());
  }

  // 3. Pack greedy hasta maxChars.
  const chunks = [];
  let current = "";
  for (const piece of pieces) {
    if (!current) {
      current = piece;
    } else if (current.length + 2 + piece.length <= maxChars) {
      current += "\n\n" + piece;
    } else {
      chunks.push(current);
      current = piece;
    }
  }
  if (current) chunks.push(current);

  // 4. Hard split si algún chunk quedó >maxChars (oración monstruo).
  const final = [];
  for (const c of chunks) {
    if (c.length <= maxChars) {
      final.push(c);
      continue;
    }
    for (let i = 0; i < c.length; i += maxChars) {
      final.push(c.slice(i, i + maxChars));
    }
  }
  return final;
}

module.exports = { chunkResponse };
