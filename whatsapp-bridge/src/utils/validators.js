"use strict";

/**
 * Validadores reutilizables para inputs del usuario en templates.
 * Devuelven { ok: true, value } o { ok: false, error }.
 */

function normalize(s) {
  return (s || "").toString().trim();
}

function stripNonDigits(s) {
  return normalize(s).replace(/[^0-9kK]/g, "");
}

/**
 * RUT chileno: acepta con o sin puntos/guion. Valida dígito verificador.
 */
function validateRut(input) {
  const raw = stripNonDigits(input).toUpperCase();
  if (raw.length < 2) return { ok: false, error: "RUT muy corto. Ej: 12.345.678-9." };
  const dv = raw.slice(-1);
  const num = raw.slice(0, -1);
  if (!/^\d+$/.test(num)) {
    return { ok: false, error: "RUT inválido. Usa formato 12.345.678-9." };
  }
  let sum = 0;
  let mul = 2;
  for (let i = num.length - 1; i >= 0; i--) {
    sum += parseInt(num[i], 10) * mul;
    mul = mul === 7 ? 2 : mul + 1;
  }
  const res = 11 - (sum % 11);
  const expected = res === 11 ? "0" : res === 10 ? "K" : String(res);
  if (expected !== dv) {
    return { ok: false, error: "El dígito verificador del RUT no coincide." };
  }
  // Formato canónico
  const body = num.replace(/(\d)(?=(\d{3})+$)/g, "$1.");
  return { ok: true, value: `${body}-${dv}` };
}

function validateEmail(input) {
  const v = normalize(input);
  // RFC simplificado, suficiente para input humano.
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  if (!re.test(v)) {
    return { ok: false, error: "Email inválido. Ej: nombre@dominio.cl." };
  }
  return { ok: true, value: v.toLowerCase() };
}

/**
 * Acepta dd-mm-yyyy, dd/mm/yyyy, yyyy-mm-dd. Devuelve ISO yyyy-mm-dd.
 */
function validateDate(input) {
  const v = normalize(input);
  let m = v.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
  let y, mm, d;
  if (m) {
    d = parseInt(m[1], 10);
    mm = parseInt(m[2], 10);
    y = parseInt(m[3], 10);
  } else {
    m = v.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (!m) {
      return {
        ok: false,
        error: "Fecha inválida. Usa dd/mm/aaaa (ej: 15/03/2024).",
      };
    }
    y = parseInt(m[1], 10);
    mm = parseInt(m[2], 10);
    d = parseInt(m[3], 10);
  }
  if (mm < 1 || mm > 12 || d < 1 || d > 31 || y < 1900 || y > 2100) {
    return { ok: false, error: "Fecha fuera de rango." };
  }
  const iso = `${y}-${String(mm).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  // Sanity check: que JS reconozca la fecha (filtra 31/02 etc.)
  const probe = new Date(iso + "T00:00:00Z");
  if (isNaN(probe.getTime())) {
    return { ok: false, error: "Fecha inválida." };
  }
  return { ok: true, value: iso };
}

const VALIDATORS = {
  rut: validateRut,
  email: validateEmail,
  date: validateDate,
};

function validate(kind, input) {
  const fn = VALIDATORS[kind];
  if (!fn) return { ok: true, value: input };
  return fn(input);
}

module.exports = {
  validate,
  validateRut,
  validateEmail,
  validateDate,
};
