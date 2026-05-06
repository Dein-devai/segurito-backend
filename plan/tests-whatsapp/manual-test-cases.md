# Casos de Prueba Manuales — Segurito WhatsApp

15 casos de prueba para validar el MVP antes de la demo.

## Precondiciones globales
- Backend levantado en `localhost:8000`.
- Bridge levantado, sesión WhatsApp activa, QR ya escaneado.
- Teléfono de prueba con WhatsApp abierto.

---

### TC-01: Reclamo CMF — Banco (cobro indebido)
**Pasos:**
1. Enviar: `tengo un problema con mi banco, me cobraron de más`
2. Esperar bienvenida + pregunta.
3. Responder: `banco`
4. Responder: `Banco de Chile`
5. Responder: `cobro indebido de 50.000 pesos en mi tarjeta`
6. Responder: `saltar`
7. Responder: `1-3 meses`
8. Responder: `No he reclamado`
9. Responder: `sí`

**Resultado esperado:**
- Bot menciona "Circular CMF" o "Ley 19.496".
- Indica pasos: reclamar al banco primero, luego CMF Online.
- Tiempo total < 30 segundos desde último mensaje.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-02: Reclamo CMF — AFP
**Pasos:**
1. Enviar: `mi afp no me quiere devolver los aportes`
2. Seguir flujo hasta confirmación.

**Resultado esperado:**
- Organismo = CMF.
- Menciona normativa de AFP y plazos.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-03: Reclamo CMF — Aseguradora
**Pasos:**
1. Enviar: `mi seguro no me pagó el siniestro`
2. Seguir flujo hasta confirmación.

**Resultado esperado:**
- Intención = RECLAMO_SERVICIO.
- Menciona póliza, plazo 30 días, CMF Online.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-04: Reclamo CMF — Mutuaria
**Pasos:**
1. Enviar: `una mutuaria me cobra intereses muy altos`
2. Seguir flujo hasta confirmación.

**Resultado esperado:**
- Menciona interés máximo, DFL 3.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-05: Reclamo CMF — Tarjeta de crédito
**Pasos:**
1. Enviar: `me llegó un cobro no reconocido en mi tarjeta`
2. Seguir flujo hasta confirmación.

**Resultado esperado:**
- Pasos claros: banco → CMF → SERNAC si aplica.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-06: Consulta simple — Deuda
**Pasos:**
1. Enviar: `¿cómo puedo saber si tengo deudas?`
2. Esperar respuesta directa del backend.

**Resultado esperado:**
- No entra al template reclamo-CMF.
- Respuesta informativa, corta, con canal verificable.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-07: Derivación SERNAC
**Pasos:**
1. Enviar: `me vendieron un celular defectuoso en una tienda`
2. Esperar respuesta.

**Resultado esperado:**
- Organismo detectado = SERNAC (o null si el backend no está extendido).
- Mensaje de derivación con web y fono del SERNAC.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-08: Derivación SII
**Pasos:**
1. Enviar: `no me devolvieron el iva de una compra`
2. Esperar respuesta.

**Resultado esperado:**
- Derivación a SII con canales de contacto.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-09: OUT_OF_SCOPE
**Pasos:**
1. Enviar: `quiero pedir una pizza`
2. Esperar respuesta.

**Resultado esperado:**
- Respuesta de delimitación de alcance.
- No entra a ningún template.
- Cortés pero firme.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-10: ALERTA / Fraude
**Pasos:**
1. Enviar: `me llamaron diciendo que gané un premio y me pidieron depositar`
2. Esperar respuesta.

**Resultado esperado:**
- Respuesta inmediata sin tool-loop (Haiku triage corta).
- Menciona: no entregues datos, fraude, PDI 134, Fiscalía.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-11: Adjunto de imagen
**Pasos:**
1. Iniciar flujo reclamo-CMF hasta paso `adjuntar_evidencia`.
2. Adjuntar una imagen (captura de pantalla o cartola).
3. Esperar que el bot no se caiga y avance al siguiente paso.

**Resultado esperado:**
- Bridge recibe la imagen.
- Si hay límite de tamaño, valida.
- Avanza a `plazo_problema` sin error.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-12: Saltar adjuntos
**Pasos:**
1. Iniciar flujo reclamo-CMF.
2. En paso `adjuntar_evidencia`, responder: `saltar`.

**Resultado esperado:**
- Avanza a `plazo_problema`.
- No se cae ni pide adjuntos de nuevo.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-13: Editar en confirmación
**Pasos:**
1. Iniciar flujo reclamo-CMF hasta `confirmar_envio`.
2. Responder: `no` o `editar`.

**Resultado esperado:**
- Vuelve a `descripcion_problema`.
- Permite reescribir la descripción.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-14: Mensaje vacío o emojis
**Pasos:**
1. Enviar mensaje vacío (solo espacios) o solo emojis.

**Resultado esperado:**
- Bridge o backend rechaza amablemente.
- No se cae.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**

---

### TC-15: Dos usuarios simultáneos
**Pasos:**
1. Desde teléfono A, iniciar flujo reclamo-CMF.
2. Desde teléfono B, enviar consulta simple.
3. Verificar que A y B reciben respuestas distintas y correctas.

**Resultado esperado:**
- Conversaciones no se mezclan.
- Cada uno recibe respuesta según su propio contexto.

**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
**Notas:**
