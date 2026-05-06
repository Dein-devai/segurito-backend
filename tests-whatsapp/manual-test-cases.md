# Casos de Prueba Manuales — Segurito WhatsApp

Todos los casos asumen: Bridge y backend levantados, sesión WhatsApp activa.

---

### TC-01: Reclamo CMF completo — Banco
**Precondiciones:** Bridge y backend levantados. Sesión WhatsApp activa.
**Pasos:**
1. Enviar: `"tengo un problema con mi banco, me cobraron de más"`
2. Esperar respuesta de bienvenida del template.
3. Responder: `"sí"` (confirmar reclamo formal)
4. Responder: `"banco"`
5. Responder: `"Banco de Chile"`
6. Responder: `"cobro de 50 mil pesos que no reconozco"`
7. Responder: `"saltar"` (sin adjuntos)
8. Responder: `"1-3 meses"`
9. Responder: `"No he reclamado todavía"`
10. Responder: `"sí"` (confirmar envío)
**Resultado esperado:**
- Respuesta final menciona Ley 19.496 o normativa CMF.
- Indica pasos: reclamar al banco primero → CMF Online → SERNAC.
- Tiempo total < 30 s desde el último mensaje.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-02: Reclamo CMF — AFP
**Pasos:**
1. `"mi AFP no registra mis cotizaciones"`
2. Seguir flujo: `"sí"` → `"AFP"` → `"AFP Habitat"` → `"no enteró cotizaciones de 3 meses"` → `"saltar"` → `"1-3 meses"` → `"No he reclamado"` → `"sí"`
**Resultado esperado:** Menciona DL 3.500, Inspección del Trabajo y CMF.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-03: Reclamo CMF — Aseguradora
**Pasos:**
1. `"mi seguro de auto no quiere pagar el siniestro"`
2. Seguir flujo seleccionando `"aseguradora"` → `"Sura Seguros"` → descripción → `"saltar"` → plazo → reclamo previo → confirmar.
**Resultado esperado:** Menciona DFL 251, canal CMF Online.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-04: Reclamo CMF — Mutuaria
**Pasos:**
1. `"la mutuaria no me quiere desembolsar el crédito aprobado"`
2. Seguir flujo completo.
**Resultado esperado:** Menciona Ley 18.010, pasos para reclamar.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-05: Reclamo CMF — Corredora de bolsa
**Pasos:**
1. `"mi corredora vendió mis acciones sin mi permiso"`
2. Seguir flujo completo seleccionando `"corredora"`.
**Resultado esperado:** Menciona Ley 18.045, reclamo CMF y posible querella.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-06: Consulta simple
**Pasos:**
1. `"¿cómo consulto mi deuda en el sistema financiero?"`
**Resultado esperado:**
- Respuesta directa del backend (sin activar template).
- Menciona CMF Online o Informe de Deudas.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-07: Derivación SERNAC
**Pasos:**
1. `"me vendieron un celular defectuoso y no me quieren devolver la plata"`
**Resultado esperado:**
- Backend detecta SERNAC como organismo competente.
- Respuesta directa, no activa template de reclamo CMF.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-08: Derivación SII
**Pasos:**
1. `"no me devolvieron el IVA de una boleta de honorarios"`
**Resultado esperado:** Backend detecta SII. Respuesta directa.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-09: OUT_OF_SCOPE
**Pasos:**
1. `"quiero pedir una pizza con queso extra"`
**Resultado esperado:**
- Backend responde con mensaje de delimitación (OUT_OF_SCOPE).
- No activa ningún template.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-10: ALERTA / Fraude
**Pasos:**
1. `"me llamaron diciendo que gané un premio y debo pagar para recibirlo"`
**Resultado esperado:**
- Backend responde con mensaje de ALERTA sobre posible fraude.
- Indica no entregar datos personales ni dinero.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-11: Adjunto de imagen en paso de evidencia
**Precondiciones:** TC-01 activo hasta el paso `adjuntar_evidencia`.
**Pasos:**
1. En lugar de escribir `"saltar"`, adjuntar una imagen de captura de pantalla.
**Resultado esperado:**
- Bridge procesa la imagen y la incluye en el payload al backend.
- El flujo avanza al siguiente paso (plazo_problema).
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-12: Saltar adjuntos con texto "saltar"
**Precondiciones:** TC-01 activo hasta el paso `adjuntar_evidencia`.
**Pasos:**
1. Escribir: `"saltar"`
**Resultado esperado:** El flujo avanza a `plazo_problema` sin error.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-13: Editar confirmación final
**Precondiciones:** TC-01 activo hasta el paso `confirmar_envio`.
**Pasos:**
1. Escribir: `"editar"`
**Resultado esperado:** El flujo retrocede a `descripcion_problema`.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-14: Mensaje vacío o solo emojis
**Pasos:**
1. Enviar solo `"🙂🙂🙂"`
**Resultado esperado:**
- El bridge no se cae.
- Backend responde con OUT_OF_SCOPE o mensaje de aclaración.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-15: Dos usuarios simultáneos (aislamiento de sesión)
**Precondiciones:** Dos números WhatsApp distintos.
**Pasos:**
1. Número A inicia reclamo CMF con banco.
2. Número B inicia consulta sobre SII al mismo tiempo.
3. Ambos responden a sus flujos independientemente.
**Resultado esperado:**
- Número A recibe respuestas del flujo de reclamo CMF.
- Número B recibe respuesta de consulta SII.
- Ninguno recibe la respuesta del otro.
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
