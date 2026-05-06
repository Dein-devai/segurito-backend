# Glosario — Segurito para no-técnicos

Definiciones simples de los términos técnicos que se usan en el proyecto.

---

## Términos de mensajería

| Término | Definición simple |
|---|---|
| **WhatsApp Web** | La versión de WhatsApp que funciona en un navegador web. El bot se conecta a través de esto. |
| **Bridge** | El programa intermediario que conecta WhatsApp con el "cerebro" del bot. Piensa en él como un traductor entre WhatsApp y el backend. |
| **QR** | Código de imagen que escaneas para vincular el bot a un número de WhatsApp. Se hace una sola vez. |
| **chatId** | Identificador único de cada conversación en WhatsApp (ej: `56912345678@c.us`). |

## Términos del backend

| Término | Definición simple |
|---|---|
| **Backend** | El "cerebro" del bot, donde vive la inteligencia artificial. Recibe mensajes, los analiza y devuelve respuestas. |
| **API** | La forma en que dos programas se comunican. El bridge le envía mensajes al backend a través de una API. |
| **Endpoint** | Una "dirección" específica en la API. Por ejemplo, `/chat` es donde se envían los mensajes. |
| **POST /chat** | La acción de enviar un mensaje nuevo al backend para que lo procese. |
| **FastAPI** | El framework (herramienta) de Python que usamos para construir la API del backend. |

## Términos de IA

| Término | Definición simple |
|---|---|
| **LLM** | Modelo de lenguaje grande. La IA que entiende y genera texto (como ChatGPT, pero de Anthropic). |
| **Haiku** | El modelo más rápido y económico de Anthropic. Lo usamos para clasificar rápidamente el tipo de consulta. |
| **Sonnet** | Modelo de capacidad intermedia. Genera las respuestas principales del bot. |
| **Opus** | El modelo más potente. Se usa solo cuando el caso es muy complejo. |
| **Triage** | La clasificación inicial del mensaje. Determina si es un reclamo, consulta, alerta o fuera de alcance. |
| **Cascada** | Sistema donde primero probamos con Haiku (rápido), luego Sonnet, y solo usamos Opus si es necesario. |

## Términos del flujo conversacional

| Término | Definición simple |
|---|---|
| **Template** | Un guion de preguntas predefinidas que el bot sigue paso a paso cuando detecta un reclamo. |
| **Topic** | El tema actual de la conversación. Por ejemplo: "reclamo-cmf" o "default" (consulta libre). |
| **Step** | Un paso dentro de un template. Cada step es una pregunta que el bot hace al usuario. |
| **Estado** | La información que el bot recuerda de la conversación (qué tipo de reclamo, qué entidad, etc.). |
| **TTL** | "Time to live" o tiempo de vida. Las conversaciones se borran automáticamente después de 30 minutos de inactividad. |

## Términos de datos

| Término | Definición simple |
|---|---|
| **RAG** | Sistema que busca en documentos y leyes para dar respuestas precisas. Significa "Retrieval Augmented Generation". |
| **ChromaDB** | Base de datos especial que guarda los documentos de normativa y permite buscarlos por significado, no solo por palabra exacta. |
| **Embedding** | Representación numérica del significado de un texto. Permite buscar documentos por concepto, no por palabra clave. |

## Términos del dominio (Chile)

| Término | Definición simple |
|---|---|
| **CMF** | Comisión para el Mercado Financiero. El organismo que regula bancos, aseguradoras, AFP y otras entidades financieras en Chile. |
| **SERNAC** | Servicio Nacional del Consumidor. Protege los derechos de los consumidores en compras y servicios. |
| **SII** | Servicio de Impuestos Internos. Maneja todo lo relacionado con impuestos en Chile. |
| **Ley 19.496** | Ley del Consumidor. Protege tus derechos cuando compras productos o servicios. |
| **Circular CMF** | Documento normativo que la CMF emite para regular a las entidades financieras. |
| **Reclamo** | Acción formal de pedir que se revise un cobro, servicio o situación que consideras injusta. |

## Términos del hackathon

| Término | Definición simple |
|---|---|
| **Track** | Línea de trabajo asignada a una persona. Hay 4 tracks: A (bridge), B (backend), C (documentación), D (testing). |
| **ADR** | Architecture Decision Record. Una decisión arquitectónica que ya está tomada y no se debe debatir. |
| **MVP** | Minimum Viable Product. La versión más simple que demuestra que la idea funciona. |
| **Dry-run** | Ensayo general de la presentación antes de hacerlo frente al jurado. |