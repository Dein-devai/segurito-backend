# Riesgos y Mitigaciones — Segurito WhatsApp MVP

## R1: Sesión de WhatsApp no persiste o pide QR constantemente
- **Probabilidad:** Alta
- **Impacto:** Alto (demo falla si no hay conexión)
- **Mitigación:**
  1. Usar `LocalAuth` con `clientId` fijo.
  2. Esperar 2 minutos después del primer scan antes de cualquier reinicio.
  3. Plan B: demo vía `backend.cli` si WhatsApp no coopera.
  4. Track A es prioridad #1 al empezar la mañana.

## R2: `whatsapp-web.js` es bloqueado o banneado por WhatsApp
- **Probabilidad:** Media
- **Impacto:** Alto
- **Mitigación:**
  1. Es un hackathon, no producción. Riesgo aceptado.
  2. No enviar spam ni mensajes masivos.
  3. Plan B: CLI demo.

## R3: Adjuntos grandes consumen memoria o rompen el bridge
- **Probabilidad:** Media
- **Impacto:** Medio
- **Mitigación:**
  1. Limitar a 5MB en `mediaProcessor.js`.
  2. Rechazar con mensaje amigable al usuario.
  3. No soportar video/audio en MVP (solo imágenes y PDFs pequeños).

## R4: Backend no detecta intención correcta
- **Probabilidad:** Media
- **Impacto:** Medio
- **Mitigación:**
  1. Fallback en bridge: si backend devuelve organismo != CMF para un reclamo, explicar al usuario y ofrecer reintentar.
  2. Extender `INTENCIONES_CMF` con sub-intenciones (Track B).
  3. Si el triage falla, cae al default Sonnet que tiene más contexto.

## R5: Rate limiter del backend bloquea la demo
- **Probabilidad:** Baja
- **Impacto:** Medio
- **Mitigación:**
  1. Rate limit por `conversation_id` ya existe (30 turnos/hora).
  2. Para demo, aumentar `SEGURITO_RL_CONV_HOUR` a 200 si es necesario.
  3. Usar diferentes `conversation_id` por cada demo run.

## R6: Dos devs de apoyo no pueden contribuir por falta de experiencia técnica
- **Probabilidad:** Alta
- **Impacto:** Medio (pierden tiempo, no avanzan)
- **Mitigación:**
  1. Tracks C y D diseñados para no requerir código complejo.
  2. Solo editar Markdown y JSON.
  3. Daily de 10 min para desbloquear dudas.

## R7: Tiempo insuficiente (8 horas)
- **Probabilidad:** Alta
- **Impacto:** Alto
- **Mitigación:**
  1. Scope reducido: solo flujo reclamo-CMF + 2 casos de derivación.
  2. No construir frontend web.
  3. No implementar OCR en el bridge.
  4. No implementar base de datos persistente de conversaciones (se usa in-memory).
  5. Prioridad: conexión WhatsApp > flujo completo > normativa precisa > documentación > extras.

## R8: Backend se cae por costo excedido
- **Probabilidad:** Baja
- **Impacto:** Alto
- **Mitigación:**
  1. `CostTracker` ya existe con budget diario (`SEGURITO_COST_BUDGET_DAY_USD`).
  2. Default es $5-10 USD, suficiente para cientos de mensajes.
  3. Monitorear en `GET /metrics`.

## R9: Hallucination de URLs o normativa inexistente
- **Probabilidad:** Media
- **Impacto:** Medio (da credibilidad al bot)
- **Mitigación:**
  1. RAG con ChromaDB sobre datos curados reduce alucinación.
  2. Prompt instrucción explícita: "Nunca inventes URLs. Usa solo URLs presentes en los servicios curados."
  3. Track D valida que URLs mencionadas existen en `data/cmf/services.json`.

## R10: Conflictos de merge/codebase entre 4 personas trabajando en paralelo
- **Probabilidad:** Media
- **Impacto:** Medio
- **Mitigación:**
  1. Tracks A y B trabajan en directorios separados (`whatsapp-bridge/` vs `backend/`).
  2. Track A no modifica código Python; Track B no modifica código JS.
  3. Tracks C y D solo crean archivos en `plan/` y `docs/`.
  4. Si hay que integrar, hacerlo en una sola sesión conjunta al final.
