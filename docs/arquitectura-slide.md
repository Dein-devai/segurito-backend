# Arquitectura — Segurito WhatsApp

> Slide de arquitectura listo para copiar a Google Slides o presentar como texto.

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                        USUARIO                                  │
│                  📱 WhatsApp móvil                              │
│            Envía texto, imagen o documento                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ WhatsApp Web Protocol
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WHATSAPP BRIDGE                              │
│                    🟢 Node.js                                   │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐      │
│  │  client.js   │  │ stateManager │  │ templateEngine    │      │
│  │  (QR + Auth) │  │ (sesiones)   │  │ (máquina estados)│      │
│  └─────────────┘  └──────────────┘  └───────────────────┘      │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐      │
│  │ messageHand.│  │ mediaProcess.│  │   apiClient.js    │      │
│  │ (enruta msg)│  │ (adjuntos)   │  │ (POST al backend) │      │
│  └─────────────┘  └──────────────┘  └───────────────────┘      │
│                                                                 │
│  Tech: whatsapp-web.js · LocalAuth · Express                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ HTTP POST /chat (JSON)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND PYTHON                                │
│                    🔵 FastAPI                                    │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐      │
│  │  /chat       │  │ ChatService  │  │ Conv. Store       │      │
│  │  /health     │  │ (orquestador)│  │ (memoria TTL 30m) │      │
│  │  /metrics    │  │              │  │                   │      │
│  └─────────────┘  └──────┬───────┘  └───────────────────┘      │
│                          │                                      │
│         ┌────────────────┼────────────────┐                     │
│         ▼                ▼                ▼                      │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐      │
│  │ Plugin CMF  │  │ Plugin Legal │  │ Plugin SERNAC/SII │      │
│  │ (reclamos)  │  │ (normativa)  │  │ (derivación)      │      │
│  └─────────────┘  └──────────────┘  └───────────────────┘      │
│         │                │                │                      │
│         └────────────────┼────────────────┘                     │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              ChromaDB + SQLite                         │       │
│  │         (RAG: normativa y documentos)                 │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
│  Tech: FastAPI · Anthropic (Haiku→Sonnet→Opus) · ChromaDB       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Flujo de datos

```
Mensaje → WhatsApp → Bridge → POST /chat → ChatService → Triage (Haiku)
                                                        ↓
                                          ┌─────────────────────────┐
                                          │ ¿Es reclamo CMF?       │
                                          │ ¿Es consulta?           │
                                          │ ¿Es alerta?             │
                                          │ ¿Fuera de alcance?      │
                                          └─────────┬───────────────┘
                                                    ↓
                                    Template guiado / Respuesta directa
                                                    ↓
                                          RAG (ChromaDB) → Contexto normativo
                                                    ↓
                                          Sonnet/Opus → Respuesta final
                                                    ↓
                                          Bridge ← JSON ← Backend
                                                    ↓
                                          WhatsApp → Usuario
```

---

## Stack tecnológico

| Capa | Tecnología | Propósito |
|---|---|---|
| Mensajería | whatsapp-web.js | Conexión a WhatsApp Web |
| Transporte | HTTP/JSON | Comunicación Bridge ↔ Backend |
| API | FastAPI | Endpoints REST del backend |
| IA | Anthropic (Haiku → Sonnet → Opus) | Clasificación, análisis, respuesta |
| RAG | ChromaDB + SQLite | Búsqueda semántica en normativa |
| Memoria | ConversationStore | Historial de conversación con TTL 30 min |

---

## Decisones clave

1. **Bridge separado** — El backend Python no depende de WhatsApp, se puede testear con CLI.
2. **HTTP entre capas** — El bridge es un adaptador de transporte, no agrega lógica de negocio.
3. **Templates en el bridge** — El flujo guiado de reclamos vive en el bridge, el contexto LLM en el backend.
4. **Cascada de modelos** — Haiku para triage rápido, Sonnet para análisis, Opus solo si es necesario.

---

## Notas para la presentación

- Copiar el diagrama ASCII principal al slide de arquitectura.
- Resaltar los 3 bloques: Usuario → Bridge → Backend.
- Mencionar que el backend ya existía antes del hackathon (poc-v2).
- El bridge se construyó durante el hackathon en 8 horas.