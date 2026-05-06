# Arquitectura Segurito WhatsApp — Hackathon MVP

## Propósito

Documento maestro de arquitectura para el MVP de Segurito vía WhatsApp. Define cómo conectar el backend `poc-v2` con un cliente WhatsApp usando `whatsapp-web.js`, cómo fluye la información, y qué decisiones ya están tomadas para que el equipo no pierda tiempo discutiéndolas mañana.

## Estado actual (`poc-v2`)

El backend es una aplicación Python 3.11 / FastAPI que expone:

- `POST /chat` — recibe `message` + `conversation_id` opcional, devuelve `ChatResponse`
- `POST /feedback` — feedback de utilidad
- `GET /health` — estado del sistema
- `GET /metrics` — métricas básicas

La lógica de negocio vive en `ChatService` (cascada Haiku → Sonnet → Opus, tool-loop, RAG con ChromaDB). El `ConversationStore` mantiene historial en memoria con TTL de 30 minutos.

**No existe frontend ni interfaz de mensajería.**

## Arquitectura objetivo

```
+--------------------------------------------------------------+
|  USUARIO (WhatsApp móvil)                                    |
|  Envía mensaje de texto, imagen o documento                  |
+---------------------------+----------------------------------+
                            |
                            v
+--------------------------------------------------------------+
|  CAPA WHATSAPP (Node.js)                                    |
|  whatsapp-web.js + LocalAuth                               |
|  ├── client.js        (conexión y QR)                      |
|  ├── stateManager.js  (sesiones por chatId, TTL 30 min)      |
|  ├── messageHandler.js (routea mensajes según topic)       |
|  ├── templateEngine.js (máquina de estados de templates)    |
|  ├── mediaProcessor.js (descarga adjuntos → base64)       |
|  └── apiClient.js     (HTTP POST al backend)               |
+---------------------------+----------------------------------+
                            | HTTP POST /chat (JSON)
                            v
+--------------------------------------------------------------+
|  BACKEND PYTHON (FastAPI, existente)                       |
|  ├── POST /chat      (router ya existe)                    |
|  ├── ChatService     (orquestador, ya existe)              |
|  ├── ConversationStore (memoria TTL, ya existe)            |
|  ├── Plugins (CMF, Legal, SERNAC, SII) — ya existen        |
|  └── ChromaDB + SQLite (ya existen)                          |
+--------------------------------------------------------------+
```

## Decisiones arquitectónicas ya tomadas (no debatir mañana)

| ADR | Decisión | Por qué |
|---|---|---|
| ADR-W01 | Bridge en **Node.js separado** | `whatsapp-web.js` es Node-only. Mantener backend puro Python permite testearlo independientemente sin depender de WhatsApp. |
| ADR-W02 | Bridge habla con backend **vía HTTP** (`POST /chat`) | Reutiliza 100% del backend sin tocar lógica de negocio. El bridge es solo adaptador de transporte. |
| ADR-W03 | **Topic state en el bridge**, contexto LLM en el backend | El backend ya tiene `ConversationStore` para el LLM. El estado del flujo de negocio (paso 1, 2, 3 del template) es específico de WhatsApp, va en el bridge. |
| ADR-W04 | **Templates como máquina de estados** | Reduce ambigüedad para usuarios no técnicos. Cada template define pasos con preguntas, tipos de respuesta y transiciones. |
| ADR-W05 | **Media proxy en bridge** | El backend acepta `message: str`. Los adjuntos se procesan en el bridge (OCR simple o envío como imagen a Anthropic si extendemos el schema). Para el MVP, el bridge puede extraer texto básico y adjuntarlo al mensaje. |
| ADR-W06 | **Un solo número de WhatsApp** | `whatsapp-web.js` autentica como un número personal. Se usará un número de prueba dedicado. No simula ser "la CMF", simplemente entrega orientación normativa como un asistente. |
| ADR-W07 | **Prompts de triage ya existen, no tocar** | El triage Haiku ya detecta `ALERTA` y `OUT_OF_SCOPE`. No invertir tiempo reescribiéndolo. |

## Identificadores de conversación

El backend usa `conversation_id` (UUID) para mantener contexto entre turnos. El bridge debe mapear:

```
WhatsApp chatId (ej: "56912345678@c.us") → conversation_id (UUID generado por backend o bridge)
```

El bridge guarda en `stateManager`:

```json
{
  "chatId": "56912345678@c.us",
  "conversationId": "uuid-generado",
  "topic": "reclamo-cmf",
  "stepId": "identificar-producto",
  "data": {
    "tipo_contacto": "reclamo",
    "tipo_entidad": "banco",
    "nombre_entidad": "Banco de Chile"
  },
  "lastActivity": 1715000000
}
```

Si una conversación no tiene actividad en 30 minutos, se expira y el siguiente mensaje inicia desde cero.

## Flujo de un mensaje entrante (WhatsApp)

1. **Recibir** mensaje en `client.on('message', handler)`
2. **Buscar** estado por `chatId`. Si no existe, crear nuevo con `topic = "default"`
3. **Si topic == "default"**:
   - Enviar `POST /chat` con `message` + `conversation_id`
   - Backend responde con `organismo_detectado`, `intencion`, `response`
   - Si `intencion` contiene `"RECLAMO"` y `organismo` es `"cmf"` → cambiar `topic` a `"reclamo-cmf"`, `step` a `"bienvenida"`, enviar pregunta del primer paso
   - Si es consulta simple → responder directamente y mantener `topic = "default"`
   - Si es `OUT_OF_SCOPE` → responder mensaje de delimitación y mantener `topic = "default"`
4. **Si topic != "default"** (estamos dentro de un template):
   - Guardar respuesta del usuario en `data[step.saveAs]`
   - Calcular `nextStep` (puede ser estático o función de la respuesta)
   - Si hay siguiente paso → enviar pregunta del siguiente paso
   - Si es el último paso → armar resumen completo, enviar al backend como `message`, y enviar respuesta final al usuario
   - Limpiar topic o dejarlo en `default` según el caso

## Extensión mínima del backend (Track B)

Para que el flujo de reclamos funcione bien, el backend necesita **mínimos cambios**:

### 1. `ChatRequest` con adjuntos opcionales

Agregar campo `attachments` opcional al schema. Si un paso del template pide documentos, el bridge los adjunta.

### 2. Plugin CMF: extender intenciones de reclamo

Agregar sub-intenciones al plugin CMF para mejorar la precisión:
- `RECLAMO_PRODUCTO` (cobros indebidos, tarjetas)
- `RECLAMO_SERVICIO` (seguros no pagados, cobranza abusiva)
- `RECLAMO_INFORMACION` (falta de info, publicidad engañosa)

### 3. Prompt pipeline: fragmento de reclamos

Nueva sección `ReclamoCMFSection` en el pipeline que instruye al modelo a:
- Preguntar por plazos transcurridos
- Verificar si ya reclamó a la entidad
- Identificar montos involucrados
- Citar normativa aplicable (Ley del Consumidor, circulares CMF)
- Derivar a SERNAC, tribunales o CMF según corresponda

**Estas extensiones están detalladas en `TRACK-B-backend.md`.**

## Diagramas disponibles

- `diagramas/arquitectura-general.puml` — vista de componentes
- `diagramas/secuencia-mensaje.puml` — flujo de un mensaje end-to-end
- `diagramas/maquina-estados-reclamo.puml` — estados del template principal
- `diagramas/despliegue.puml` — cómo corre todo localmente

## Tracks de trabajo

| Track | Responsable | Qué hace | Archivo guía |
|---|---|---|---|
| A | Dev técnico principal | WhatsApp Bridge Node.js | `TRACK-A-bridge.md` |
| B | Dev técnico principal | Extensiones backend Python | `TRACK-B-backend.md` |
| C | Dev apoyo | Documentación + demo script | `TRACK-C-documentacion.md` |
| D | Dev apoyo | Testing + casos de prueba | `TRACK-D-testing.md` |

## Cómo empezar mañana (orden de ejecución)

1. **07:00** — Daily 10 min: cada track lee su archivo guía
2. **07:15** — Track A crea `whatsapp-bridge/` y conecta WhatsApp (QR)
3. **07:15** — Track B extiende `ChatRequest` y plugin CMF en paralelo
4. **08:30** — Tracks A+B integran: bridge hace POST al backend real
5. **09:30** — Track C prepara datos de prueba y demo script
6. **10:00** — Track D prueba flujos manuales y reporta bugs
7. **Repetir** hasta las 15:00, luego dry-run de demo

## Glosario

| Término | Significado |
|---|---|
| **Bridge** | Aplicación Node.js que conecta WhatsApp con el backend |
| **Template** | Definición de un flujo conversacional estructurado (pasos, preguntas, transiciones) |
| **Topic** | Estado de la conversación que indica qué template está activo |
| **Step** | Un paso dentro de un template (una pregunta al usuario) |
| **Track** | Línea de trabajo paralela asignada a una persona |
| **ADR** | Architecture Decision Record — decisión arquitectónica documentada |
| **RAG** | Retrieval Augmented Generation — búsqueda semántica en ChromaDB + respuesta del LLM |
| **Triage** | Fase inicial con modelo Haiku que clasifica urgencia y alcance |
| **Tool-loop** | Ciclo donde el LLM decide si usar una tool (buscar en RAG) o responder |
