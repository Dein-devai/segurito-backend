# Track A — WhatsApp Bridge (Node.js)

## Objetivo
Crear la aplicación Node.js que conecta `whatsapp-web.js` con el backend Python vía HTTP.

## Responsable
Dev técnico principal (backend/Node.js).

## Archivos a crear

```
whatsapp-bridge/
├── package.json
├── .env.example
├── src/
│   ├── index.js              # Entrypoint
│   ├── client.js             # Factory de whatsapp-web.js Client
│   ├── stateManager.js       # Mapa en memoria chatId → state
│   ├── messageHandler.js     # Routea mensajes según topic
│   ├── apiClient.js          # Axios wrapper para backend
│   ├── templateEngine.js     # Máquina de estados de templates
│   ├── templates/
│   │   ├── index.js          # Registro de templates
│   │   ├── reclamo-cmf.js    # Template principal (estado machine)
│   │   ├── consulta-rapida.js
│   │   └── derivacion.js
│   └── utils/
│       └── mediaProcessor.js # Descarga media, valida size
```

## Dependencias (package.json)

```json
{
  "name": "segurito-whatsapp-bridge",
  "version": "1.0.0",
  "description": "WhatsApp bridge for Segurito hackathon MVP",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js",
    "dev": "node src/index.js"
  },
  "dependencies": {
    "whatsapp-web.js": "^1.26.0",
    "qrcode-terminal": "^0.12.0",
    "axios": "^1.7.0",
    "dotenv": "^16.4.0"
  }
}
```

## Configuración (.env.example)

```bash
# Backend
BACKEND_URL=http://localhost:8000
BACKEND_TIMEOUT_MS=35000

# WhatsApp
WA_CLIENT_ID=segurito-hackathon
WA_DATA_PATH=./.wwebjs_auth

# Bridge
BRIDGE_LOG_LEVEL=info
MAX_ATTACHMENT_MB=5
SESSION_TTL_MINUTES=30
```

## Especificación por archivo

### 1. `src/client.js`

Responsabilidad: crear y configurar el cliente de `whatsapp-web.js`.

Requisitos:
- Usar `LocalAuth` con `clientId` configurable.
- Puppeteer args: `--no-sandbox`, `--disable-setuid-sandbox`.
- Eventos a manejar: `qr` (imprime QR en terminal), `ready` (loguea conexión), `authenticated` (loguea éxito), `auth_failure` (loguea error), `disconnected` (intenta reconectar 1 vez).
- Exportar función `createClient()` que retorna la instancia.

### 2. `src/stateManager.js`

Responsabilidad: mantener el estado de cada conversación WhatsApp en memoria.

Requisitos:
- Mapa en memoria: `Map<string, ConversationState>` donde la key es `chatId`.
- TTL: 30 minutos de inactividad. Purge cada 5 minutos.
- Estructura del estado:
  ```javascript
  {
    chatId: "56912345678@c.us",
    conversationId: "uuid-v4-generado-por-backend",
    topic: "default" | "reclamo-cmf" | "consulta-rapida" | "derivacion",
    stepId: "bienvenida" | "identificar-producto" | ... | null,
    data: {}, // datos recolectados del usuario
    createdAt: timestamp,
    lastActivity: timestamp
  }
  ```
- Métodos: `get(chatId)`, `set(chatId, state)`, `delete(chatId)`, `updateActivity(chatId)`, `purgeExpired()`.
- Generar `conversationId` como UUID v4 si el backend no lo devuelve.

### 3. `src/messageHandler.js`

Responsabilidad: decidir qué hacer con cada mensaje entrante.

Requisitos:
- Recibe `message` del evento de whatsapp-web.js.
- Extrae: `chatId` (message.from), `body` (message.body), `hasMedia` (message.hasMedia).
- Si tiene media → delegar a `mediaProcessor.js` primero.
- Buscar estado en `stateManager`.
- Si `topic === "default"`:
  - Llamar a `apiClient.chat({ message: body })` (sin conversation_id la primera vez).
  - Backend responde con `organismo_detectado`, `intencion`, `response`, `conversation_id`.
  - Si `intencion` contiene `"RECLAMO"` y `organismo_detectado === "cmf"`:
    - Actualizar estado: `topic = "reclamo-cmf"`, `stepId = "bienvenida"`, guardar `conversationId`.
    - Obtener pregunta del template y enviarla.
  - Si no → enviar respuesta del backend directamente.
- Si `topic !== "default"`:
  - Llamar a `templateEngine.processStep(chatId, body, state)`.
  - Guardar respuesta en `state.data`.
  - Obtener siguiente paso.
  - Si hay siguiente paso → enviar pregunta.
  - Si es el último paso → armar resumen, enviar al backend, enviar respuesta final.

### 4. `src/apiClient.js`

Responsabilidad: cliente HTTP hacia el backend.

Requisitos:
- Usar `axios`.
- Base URL desde `BACKEND_URL`.
- Timeout: `BACKEND_TIMEOUT_MS` (default 35000).
- Métodos:
  - `async chat(payload)` → POST `/chat` con `{ message, conversation_id }`.
  - `async health()` → GET `/health` (para verificar backend disponible).
- Manejar errores: si backend devuelve 429, esperar `Retry-After` y reintentar 1 vez. Si sigue fallando, responder al usuario: "El servicio está ocupado, intenta en unos segundos."
- Logging de requests/responses.

### 5. `src/templateEngine.js`

Responsabilidad: orquestar la máquina de estados de los templates.

Requisitos:
- Cargar todos los templates desde `src/templates/`.
- Método `processStep(chatId, userResponse, state)`:
  1. Obtener template activo (`state.topic`).
  2. Obtener paso actual (`state.stepId`).
  3. Guardar `userResponse` en `state.data[step.saveAs]`.
  4. Determinar siguiente paso (`step.next` puede ser string o función).
  5. Si siguiente paso existe → retornar `{ action: "ask", step: nextStep }`.
  6. Si no hay siguiente paso → retornar `{ action: "complete", data: state.data }`.
- Método `getQuestion(topic, stepId)` → retorna el texto de la pregunta.
- Método `getChoices(topic, stepId)` → retorna opciones si el paso es tipo `choice`.

### 6. `src/templates/reclamo-cmf.js`

Responsabilidad: definir el flujo estructurado de reclamo CMF.

Ver archivo de template en `plan/templates/reclamo-cmf.json`. El JS debe importar ese JSON y exponer funciones de transición.

Reglas de transición específicas:
- `bienvenida` → si usuario dice "consulta" o "pregunta" → salir del template y enviar como consulta libre.
- `confirmar-envio` → si usuario dice "no" o "editar" → volver a `descripcion-problema`.
- `adjuntar-evidencia` → si usuario escribe "saltar" o "no tengo" → avanzar sin guardar nada.

### 7. `src/utils/mediaProcessor.js`

Responsabilidad: descargar y procesar archivos adjuntos de WhatsApp.

Requisitos:
- Recibe `message` de whatsapp-web.js.
- Si `message.hasMedia` → `await message.downloadMedia()`.
- Validar tamaño: si `data.length` (base64) > `MAX_ATTACHMENT_MB * 1024 * 1024` → rechazar con mensaje: "El archivo es muy grande. Máximo 5MB."
- Retornar: `{ mimeType, filename, base64Data, sizeBytes }`.
- Para el MVP, no hacer OCR en el bridge. El bridge puede adjuntar el base64 al payload del backend (si extendemos el schema) o simplemente decir al usuario: "Documento recibido. Lo incluiré en tu caso."

### 8. `src/index.js`

Responsabilidad: punto de entrada.

Requisitos:
- Cargar `.env`.
- Verificar que backend responde `/health` antes de inicializar WhatsApp.
- Crear cliente WhatsApp.
- Registrar handler `client.on('message', messageHandler)`.
- Inicializar: `client.initialize()`.
- Graceful shutdown: `SIGINT` → `client.destroy()` → `process.exit(0)`.

## Checklist de entrega

- [ ] `npm install` funciona sin errores.
- [ ] `npm start` muestra QR en terminal.
- [ ] Al escanear QR, aparece "Client is ready!".
- [ ] Enviar mensaje de prueba al número → bridge lo recibe y hace POST al backend.
- [ ] Backend responde → bridge responde en WhatsApp.
- [ ] Sesión persiste entre reinicios (LocalAuth).
- [ ] Manejo básico de errores (backend caído, timeout).

## Comandos de verificación

```bash
cd whatsapp-bridge
npm install
npm start
# En otra terminal:
curl http://localhost:8000/health  # backend debe estar levantado
```
