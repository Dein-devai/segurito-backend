# Demo Script — Segurito WhatsApp (5 minutos)

## Objetivo
Presentar el MVP de Segurito vía WhatsApp en 5 minutos netos, mostrando el valor central: un ciudadano común puede entender sus derechos financieros sin ser abogado.

## Setup previo (realizar 5 min antes de entrar a presentar)

- [ ] Laptop con backend levantado (`uvicorn main:app --reload` en puerto 8000).
- [ ] Laptop con bridge levantado (`npm start` en `whatsapp-bridge/`), QR ya escaneado, sesión activa.
- [ ] Teléfono de prueba con WhatsApp abierto, conversación con el bot visible.
- [ ] Proyector o pantalla compartida mostrando el teléfono (Reflector, scrcpy, o cámara al teléfono).
- [ ] `docs/arquitectura-slide.md` abierto por si preguntan técnica.

---

## Acto 1 — Intro (45 segundos)

**Diálogo sugerido:**
> "En Chile, 5 millones de personas tienen derechos financieros que no pueden ejercer. La información existe, pero está en portales que requieren abogado para entenderlos."
>
> "Segurito es un asistente conversacional que traduce la normativa CMF, SERNAC, SII al lenguaje de cualquier ciudadano. Hoy lo mostramos por WhatsApp."

**Acción:** Mostrar el número del bot en pantalla (o la conversación ya abierta).

---

## Acto 2 — Caso 1: Reclamo CMF completo (2 min 30 seg)

**Contexto:** Un ciudadano tiene un cobro indebido en su tarjeta de crédito.

**Diálogo sugerido:**
> "Imaginemos a Juan. Le cobraron 50 mil pesos que no reconocen en su tarjeta. No sabe si reclamar al banco, a la CMF, o al SERNAC."

**Pasos en vivo:**

1. **Enviar mensaje:** `tengo un cobro indebido en mi tarjeta del banco estado`
   - **Esperar:** 3-5 segundos.
   - **Debe aparecer:** "Hola, soy Segurito. Veo que tienes un problema..."

2. **Responder:** `tarjeta` (o tocar opción si el bridge envía botones; en MVP será texto)
   - **Esperar:** "¿Cuál es el nombre de la entidad?"

3. **Responder:** `Banco Estado`
   - **Esperar:** "Describe brevemente el problema..."

4. **Responder:** `me cobraron 50.000 pesos en abril que no reconozco`
   - **Esperar:** "Adjunta documentos o escribe 'saltar'"

5. **Responder:** `saltar`
   - **Esperar:** "¿Hace cuánto tiempo ocurrió el problema?"

6. **Responder:** `1-3 meses`
   - **Esperar:** "¿Ya reclamaste directamente a la entidad?"

7. **Responder:** `no`
   - **Esperar:** Resumen + "¿Confirmas que quieres que analice tu caso?"

8. **Responder:** `sí`
   - **Esperar:** 5-10 segundos (backend procesa).
   - **Debe aparecer:** Análisis normativo con citas ("Según la Circular CMF..."), pasos a seguir ("Primero reclama al banco por escrito..."), y canales de contacto.

**Comentario del presentador:**
> "En menos de 2 minutos, Juan sabe exactamente qué norma protege su caso, qué pasos dar, y en qué orden."

---

## Acto 3 — Caso 2: Derivación a SERNAC (45 segundos)

**Diálogo sugerido:**
> "Pero no todos los casos son de la CMF. ¿Qué pasa si el problema es una compra en retail?"

**Pasos en vivo:**

1. **Enviar mensaje:** `me vendieron un celular defectuoso en una tienda y no me lo quieren cambiar`
   - **Esperar:** 3-5 segundos.
   - **Debe aparecer:** "Según el análisis de tu consulta, este caso corresponde a SERNAC..." con web y fono.

**Comentario del presentador:**
> "El bot no inventa. Cruza la consulta con el marco legal y deriva al organismo correcto."

---

## Acto 4 — Caso 3: Out of scope + cierre (1 min)

**Diálogo sugerido:**
> "Y si alguien intenta usarlo para otra cosa..."

**Pasos en vivo:**

1. **Enviar mensaje:** `quiero pedir una pizza`
   - **Esperar:** 2-3 segundos.
   - **Debe aparecer:** "Soy Segurito, asistente de organismos del Estado de Chile. No puedo ayudarte con pedidos de comida."

**Cierre:**
> "En 8 horas construimos un puente entre la ley y el ciudadano. La normativa ya existe. Lo que faltaba era la última milla."

---

## Plan B (si WhatsApp falla)

Si el bridge no responde o el QR expira:

1. Abrir terminal.
2. Ejecutar: `python -m backend.cli`
3. Escribir los mismos 3 mensajes del script.
4. Decir: *"Este es el motor de inteligencia. La capa de WhatsApp se conecta a este mismo backend. Estamos en una hackathon de 8 horas, así que priorizamos el cerebro."*

---

## Materiales de apoyo

- `docs/flujo-reclamo-cmf.md` — si preguntan cómo funciona por dentro.
- `plan/diagramas/arquitectura-general.puml` — si preguntan arquitectura.
- `README.md` del backend — si preguntan stack técnico.

## Checklist final antes de presentar

- [ ] Los 3 casos del script fueron probados en vivo y funcionan.
- [ ] Bridge muestra "ready" y no pide QR.
- [ ] Backend responde `/health` en < 1 segundo.
- [ ] Teléfono de prueba tiene batería > 50%.
- [ ] Demo dura 5 minutos o menos si se ejecuta sin improvisar.
