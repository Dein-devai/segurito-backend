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
 * - Bullet points Unicode (•⁠ ⁠, •, ●, ‣) → emoji 1️⃣2️⃣3️⃣ o bullet simple
 * - Headers markdown (### ##) → *negrita*
 * - Listas numeradas markdown → formato WhatsApp
 * - Espacios extra / caracteres invisibles
 */
function formatForWhatsApp(text) {
  if (!text) return text;

  // Limpiar caracteres Unicode invisibles (zero-width, word joiner, etc.)
  text = text.replace(/[​‌‍⁠﻿­]/g, '');
  text = text.replace(/⁠/g, ''); // word joiner
  text = text.replace(/​/g, ''); // zero-width space
  text = text.replace(/﻿/g, ''); // BOM
  text = text.replace(/­/g, ''); // soft hyphen

  let lines = text.split('\n');
  let result = [];
  let listCounter = 0;

  for (let line of lines) {
    const trimmed = line.trim();

    // Vacío → mantener
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

    // Bullet points Unicode: •⁠ ⁠, •, ●, ‣, ◦ + contenido
    const bulletMatch = trimmed.match(/^[•●‣◦]\s*(.*)/);
    if (bulletMatch) {
      listCounter++;
      const content = boldMarkdownToWhatsApp(bulletMatch[1]);
      result.push(`${listCounter}️⃣ ${content}`);
      continue;
    }

    // Bullet points con guión: - texto
    const dashMatch = trimmed.match(/^[-*]\s+(.+)/);
    if (dashMatch && !trimmed.startsWith('**')) {
      listCounter++;
      const content = boldMarkdownToWhatsApp(dashMatch[1]);
      result.push(`${listCounter}️⃣ ${content}`);
      continue;
    }

    // Listas numeradas markdown: 1. texto
    const numMatch = trimmed.match(/^(\d+)[.)]\s+(.+)/);
    if (numMatch) {
      const num = parseInt(numMatch[1], 10);
      listCounter = num;
      const content = boldMarkdownToWhatsApp(numMatch[2]);
      const numEmoji = numberToEmoji(num);
      result.push(`${numEmoji} ${content}`);
      continue;
    }

    // Blockquote: > texto
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
 * Maneja: **texto**, *texto* (si no es italic), y combinaciones.
 */
function boldMarkdownToWhatsApp(text) {
  if (!text) return text;

  // **bold** → *bold* (WhatsApp)
  let result = text.replace(/\*\*(.+?)\*\*/g, '*$1*');

  // Limpiar caracteres Unicode invisibles (zero-width spaces, etc.)
  result = result.replace(/[​‌‍⁠﻿­]/g, '');

  // Limpiar ⁠ (word joiner) que aparece en bullets de Anthropic
  result = result.replace(/⁠/g, '');

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