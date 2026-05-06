# Track D — Testing, QA y Validación

## Objetivo
Probar los flujos end-to-end, validar que el bot no se caiga, y crear casos de prueba manuales y automatizables.

## Responsable
Dev de apoyo (testing, QA, validación).

## Archivos a crear

### 1. `tests-whatsapp/manual-test-cases.md`

15 casos de prueba manuales con pasos exactos y criterios de aceptación.

Estructura por caso:
```markdown
### TC-01: Reclamo CMF completo — Banco
**Precondiciones:** Bridge y backend levantados. Sesión WhatsApp activa.
**Pasos:**
1. Enviar mensaje: "tengo un problema con mi banco, me cobraron de más"
2. Esperar respuesta de bienvenida
3. Responder: "banco"
4. Responder: "Banco de Chile"
5. Responder: "cobro de 50 mil pesos que no reconozco"
6. Responder: "saltar" (sin adjuntos)
7. Responder: "1-3 meses"
8. Responder: "No he reclamado"
9. Responder: "sí" (confirmar)
**Resultado esperado:**
- Bot responde con análisis normativo
- Menciona "Ley 19.496" o "Circular CMF"
- Indica pasos a seguir (reclamar al banco primero)
- Tiempo total < 30 segundos desde último mensaje
**Estado:** ☐ Pendiente ☐ Pass ☐ Fail
```

Casos mínimos a incluir:
- TC-01 a TC-05: Reclamos CMF con diferentes entidades (banco, AFP, aseguradora, mutuaria, tarjeta).
- TC-06: Consulta simple ("¿cómo consulto mi deuda?").
- TC-07: Derivación SERNAC ("me vendieron un celular defectuoso").
- TC-08: Derivación SII ("no me devolvieron el IVA").
- TC-09: OUT_OF_SCOPE ("quiero pedir una pizza").
- TC-10: ALERTA/Fraude ("me llamaron diciendo que soy ganador").
- TC-11: Adjunto de imagen en paso de evidencia.
- TC-12: Usuario escribe "saltar" en paso de adjuntos.
- TC-13: Usuario dice "no" en confirmación final (debe volver a editar).
- TC-14: Mensaje vacío o solo emojis.
- TC-15: Dos usuarios simultáneos (enviar desde 2 números distintos, verificar que no se mezclan).

### 2. `tests-whatsapp/regression-checklist.md`

Lista corta para correr antes de cada demo o presentación.

```markdown
# Regression Checklist — Segurito WhatsApp

## Infraestructura
- [ ] Backend responde `GET /health` con 200
- [ ] Bridge muestra "Client is ready" en logs
- [ ] QR no aparece (sesión persistida)

## Flujos críticos (5 min)
- [ ] TC-01: Reclamo banco completo
- [ ] TC-07: Derivación SERNAC
- [ ] TC-09: OUT_OF_SCOPE

## Calidad
- [ ] Ningún error en logs del bridge
- [ ] Ningún error en logs del backend
- [ ] Respuestas < 2000 caracteres
```

### 3. `tests-whatsapp/mock-backend.js`

Mock HTTP server que simula el backend real para probar el bridge sin depender del backend.

Requisitos:
- Express o http nativo.
- Endpoints:
  - `POST /chat` → responde con ChatResponse de ejemplo según keywords en el mensaje.
  - `GET /health` → `{ "status": "ok" }`.
- Lógica simple:
  - Si mensaje contiene "banco" → `organismo_detectado: "cmf"`, `intencion: "RECLAMO"`.
  - Si mensaje contiene "celular" → `organismo_detectado: "sernac"`, `intencion: "CONSULTA"`.
  - Si mensaje contiene "pizza" → `organismo_detectado: null`, `intencion: "OUT_OF_SCOPE"`.
- Puerto configurable (default 9000).

### 4. `tests-whatsapp/load-test-notes.md`

Instrucciones para verificar estabilidad básica.

```markdown
# Load Test — Notas

## Scope
No es un test de carga real (no tenemos infraestructura para miles de usuarios).
Es una validación de que no se cae con uso concurrente moderado.

## Escenario
1. Levantar backend y bridge.
2. Desde 3 teléfonos diferentes, iniciar conversaciones simultáneas.
3. Cada uno envía 5 mensajes en 2 minutos.

## Criterios de aceptación
- Ningún mensaje se pierde.
- Respuestas llegan en < 10 segundos cada una.
- No hay errores 500 en backend.
- Conversaciones no se mezclan (usuario A no recibe respuesta de usuario B).

## Limitaciones conocidas
- ConversationStore del backend es in-memory. Si el backend se reinicia, se pierden conversaciones activas.
- Rate limiter por IP puede afectar si todos los teléfonos usan la misma red WiFi (misma IP pública).
  - Mitigación: usar `conversation_id` para rate limit por conversación, no solo por IP.
```

## Dependencias

Este track no requiere dependencias adicionales salvo:
- Node.js (para mock-backend.js).
- Teléfono(s) con WhatsApp para pruebas manuales.
- Acceso a los logs del bridge y backend.

## Checklist de entrega

- [ ] 15 casos de prueba documentados.
- [ ] Mock backend funciona (`node tests-whatsapp/mock-backend.js` + `curl` responde).
- [ ] Regression checklist tiene máximo 10 items (debe poderse correr en 5 minutos).
- [ ] Al menos 3 casos de prueba fueron ejecutados en hardware real y marcan Pass o Fail con notas.

## Notas

- Si encuentras un bug, documentarlo en `tests-whatsapp/bugs-encontrados.md` con:
  - Pasos para reproducir.
  - Comportamiento esperado vs actual.
  - Logs relevantes.
  - Quién es el responsable (Track A o B).
- No intentes automatizar todo con Selenium/Playwright para WhatsApp — eso es demasiado para 8 horas. Enfócate en pruebas manuales estructuradas.
