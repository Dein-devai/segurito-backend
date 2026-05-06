/**
 * WhatsAppFormatter — convierte markdown del LLM a formato nativo de WhatsApp.
 *
 * WhatsApp soporta:
 * - *negrita*      → *negrita*
 * - _cursiva_      → _cursiva_
 * - ~tachado~      → ~tachado~
 * - ```monospace``` → ```monospace```
 *
 * Problemas que resuelve:
 * - Bullet points Unicode (•⁠ ⁠, •, ●, ‣) → bullet simple o sub-item
 * - Headers markdown (### ##) → *negrita*
 * - Listas numeradas markdown → formato WhatsApp con emojis
 * - Sub-bullets (indentados) → punto medio • en vez de número
 * - Espacios extra / caracteres invisibles
 */
function formatForWhatsApp(text) {
  if (!text) return text;

  // Limpiar caracteres Unicode invisibles (zero-width, word joiner, etc.)
  text = text.replace(/⁠/g, ''); // word joiner (U+2060)
  text = text.replace(/​/g, ''); // zero-width space (U+200B)
  text = text.replace(/﻿/g, ''); // BOM (U+FEFF)
  text = text.replace(/­/g, ''); // soft hyphen (U+00AD)
  text = text.replace(/‌/g, ''); // zero-width non-joiner (U+200C)
  text = text.replace(/‍/g, ''); // zero-width joiner (U+200D)

  let lines = text.split('\n');
  let result = [];
  let listCounter = 0;

  for (let line of lines) {
    const trimmed = line.trim();

    // Vacío → mantener (resetea contador)
    if (!trimmed) {
      listCounter = 0;
      result.push('');
      continue;
    }

    // Headers markdown: ### Título → *TÍTULO*
    const headerMatch = trimmed.match(/^#{1,6}\s+(.+)/);
    if (headerMatch) {
      result.push('*' + headerMatch[1].trim().toUpperCase() + '*');
      listCounter = 0;
      continue;
    }

    // Línea horizontal --- → línea decorativa
    if (/^[-—─]{3,}$/.test(trimmed)) {
      result.push('───────────────');
      listCounter = 0;
      continue;
    }

    // Sub-bullets indentados (2+ espacios o tab + guión/punto)
    // Estos son sub-items de una lista, NO se numeran
    const subBulletMatch = trimmed.match(/^[•●‣◦]\s+(.*)/);
    const subDashMatch = trimmed.match(/^[-*]\s+(.+)/);
    // Detectar si es un sub-item: está indentado o es un bullet después de
    // un item numerado y el contenido es corto (URL, teléfono, nota)
    if (subBulletMatch || (subDashMatch && !trimmed.startsWith('**'))) {
      const content = boldMarkdownToWhatsApp(subBulletMatch ? subBulletMatch[1] : subDashMatch[1]);
      // Sub-bullet: usar punto medio, no número
      result.push(`  • ${content}`);
      continue;
    }

    // Listas numeradas markdown: 1. texto → emoji numerado
    const numMatch = trimmed.match(/^(\d+)[.)]\s+(.+)/);
    if (numMatch) {
      const num = parseInt(numMatch[1], 10);
      listCounter = num;
      const content = boldMarkdownToWhatsApp(numMatch[2]);
      const numEmoji = numberToEmoji(num);
      result.push(`${numEmoji} ${content}`);
      continue;
    }

    // Blockquote: > texto → cursiva indentada
    if (trimmed.startsWith('>')) {
      const content = boldMarkdownToWhatsApp(trimmed.replace(/^>\s*/, ''));
      result.push(`   _${content}_`);
      listCounter = 0;
      continue;
    }

    // Línea normal
    listCounter = 0;
    result.push(boldMarkdownToWhatsApp(trimmed));
  }

  // Limpiar: máximo 2 líneas vacías consecutivas
  let cleaned = [];
  let emptyCount = 0;
  for (const line of result) {
    if (line === '') {
      emptyCount++;
      if (emptyCount <= 1) cleaned.push(line);
    } else {
      emptyCount = 0;
      cleaned.push(line);
    }
  }

  return cleaned.join('\n');
}

/**
 * Convierte **bold** markdown a *bold* de WhatsApp.
 */
function boldMarkdownToWhatsApp(text) {
  if (!text) return text;

  // **bold** → *bold* (WhatsApp)
  let result = text.replace(/\*\*(.+?)\*\*/g, '*$1*');

  // Limpiar caracteres Unicode invisibles residuales
  result = result.replace(/⁠/g, '');
  result = result.replace(/​/g, '');

  return result;
}

/**
 * Convierte número a emoji.
 */
function numberToEmoji(n) {
  const emojis = ['0️⃣','1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣'];
  if (n < 0 || n > 9) return `${n}.`;
  return emojis[n];
}

module.exports = { formatForWhatsApp };