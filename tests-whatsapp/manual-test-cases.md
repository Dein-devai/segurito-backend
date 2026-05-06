# Manual Test Cases — Segurito WhatsApp

15 casos de prueba con pasos exactos y criterios de aceptación.

---

### TC-01: Reclamo CMF completo — Banco
**Precondiciones:** Bridge y backend levantados. Sesión WhatsApp activa.
**Pasos:**
1. Enviar mensaje: "tengo un problema con mi banco, me cobraron de más"
2. Esperar respuesta de bienvenida
3. Responder: "sí"
4. Responder: "1" (Banco)
5. Responder: "Banco de Chile"
6. Responder: "cobro de 50 mil pesos que no reconozco"
7. Responder: "saltar" (sin adjuntos)
8. Responder: "2" (1-3 meses)
9. Responder: "3" (No he reclamado)
10. Responder: "sí" (confirmar)
**Resultado esperado:**
- Bot responde con análisis normativo
- Menciona "Ley 19.496" o "Circular CMF"
- Indica pasos a seguir (reclamar al banco primero)
- Tiempo total < 30 segundos desde último mensaje
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-02: Reclamo CMF — AFP
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "mi AFP no me quiere devolver los aportes"
2. Confirmar reclamo: "sí"
3. Elegir: "2" (AFP)
4. Nombre: "AFP Provida"
5. Descripción: "no me devuelven cotizaciones pagadas en exceso"
6. Adjuntos: "saltar"
7. Plazo: "2" (1-3 meses)
8. Reclamo previo: "1" (Sí, y me respondieron)
9. Confirmar: "sí"
**Resultado esperado:**
- Menciona "AFP", "cotización", "CMF"
- Indica plazos y canales de contacto
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-03: Reclamo CMF — Aseguradora
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "mi seguro no me pagó el siniestro del auto"
2. Confirmar: "sí"
3. Elegir: "3" (Aseguradora)
4. Nombre: "Sura Seguros"
5. Descripción: "rechazan pago de siniestro sin justificación"
6. Adjuntos: "saltar"
7. Plazo: "1" (Menos de 1 mes)
8. Reclamo previo: "2" (Sí, pero no respondieron)
9. Confirmar: "sí"
**Resultado esperado:**
- Menciona "aseguradora", "póliza", "CMF Online"
- Indica plazo de 30 días
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-04: Reclamo CMF — Mutuaria
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "una mutuaria me cobra intereses abusivos"
2. Confirmar: "sí"
3. Elegir: "4" (Mutuaria)
4. Nombre: "Coopeuch"
5. Descripción: "intereses de cobranza exceden el monto original"
6. Adjuntos: "saltar"
7. Plazo: "3" (3-6 meses)
8. Reclamo previo: "3" (No he reclamado)
9. Confirmar: "sí"
**Resultado esperado:**
- Menciona "mutuaria", "tasa convencional", "CMF"
- Indica cómo verificar tasa máxima
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-05: Reclamo CMF — Tarjeta de crédito
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "me cobraron de más en mi tarjeta de crédito del banco estado"
2. Confirmar: "sí"
3. Elegir: "6" (Tarjeta de crédito)
4. Nombre: "Banco Estado"
5. Descripción: "cargo de 50.000 no reconocido en abril"
6. Adjuntos: "saltar"
7. Plazo: "2" (1-3 meses)
8. Reclamo previo: "3" (No he reclamado)
9. Confirmar: "sí"
**Resultado esperado:**
- Menciona "Circular CMF", "10 días hábiles"
- Guía paso a paso
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-06: Consulta simple
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "¿cómo consulto mi deuda en la CMF?"
2. Esperar respuesta directa
**Resultado esperado:**
- No inicia template guiado
- Responde con info sobre consulta de deuda
- Menciona "CMF" o "informe de deudas"
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-07: Derivación SERNAC
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "me vendieron un celular defectuoso en una tienda y no me lo quieren cambiar"
2. Esperar respuesta
**Resultado esperado:**
- Menciona "SERNAC"
- Indica garantía legal o Ley 19.496
- No inicia template CMF
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-08: Derivación SII
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "no me devolvieron el IVA de una compra que hice"
2. Esperar respuesta
**Resultado esperado:**
- Menciona "SII"
- Indica canales de contacto SII
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-09: OUT_OF_SCOPE
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "quiero pedir una pizza"
2. Esperar respuesta
**Resultado esperado:**
- Responde con delimitación de alcance
- Menciona que es asistente de organismos del Estado
- No invoca tools
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-10: ALERTA — Fraude
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "alguien me llamó diciendo que soy ganador de un premio y que deposite plata"
2. Esperar respuesta
**Resultado esperado:**
- Responde con alerta inmediata
- Menciona "fraude", "PDI" o "no entregues datos"
- No entra en tool-loop
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-11: Adjunto de imagen en paso de evidencia
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Iniciar reclamo CMF completo (TC-01)
2. En paso de adjuntos, enviar una imagen del estado de cuenta
3. Continuar flujo normal
**Resultado esperado:**
- Bot confirma recepción del documento
- Continúa al paso de plazo sin error
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-12: Usuario escribe "saltar" en adjuntos
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Iniciar reclamo CMF completo (TC-01)
2. En paso de adjuntos, escribir "saltar"
3. Verificar que avanza al paso de plazo
**Resultado esperado:**
- Avanza sin pedir adjuntos
- Flujo continúa normalmente
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-13: Usuario dice "no" en confirmación final
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Iniciar reclamo CMF completo (TC-01)
2. En paso de confirmación final, escribir "no" o "editar"
3. Verificar que vuelve al paso de descripción
**Resultado esperado:**
- Vuelve al paso de descripción del problema
- No envía nada al backend
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-14: Mensaje vacío o solo emojis
**Precondiciones:** Bridge y backend levantados.
**Pasos:**
1. Enviar: "" (mensaje vacío) o "😀😀😀"
2. Esperar respuesta
**Resultado esperado:**
- Responde pidiendo aclaración o descripción del problema
- No crashea
- No clasifica como reclamo
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail

---

### TC-15: Dos usuarios simultáneos
**Precondiciones:** Bridge y backend levantados. Dos teléfonos con WhatsApp.
**Pasos:**
1. Teléfono A envía: "me cobraron de más en mi tarjeta"
2. Teléfono B envía: "quiero consultar mi deuda" (antes de que A reciba respuesta)
3. Verificar que cada teléfono recibe su propia respuesta
**Resultado esperado:**
- Conversaciones no se mezclan
- A recibe orientación sobre reclamo tarjeta
- B recibe info sobre consulta de deuda
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail