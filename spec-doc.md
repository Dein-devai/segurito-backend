# Segurito · Backend Spec

> Asistente público chileno que orienta a ciudadanos sobre servicios de organismos del Estado (CMF, SERNAC, SII) anclado en marco legal verificable.
> PoC para **Claude Impact Lab Chile 2026**.

---

## Tabla de contenidos

1. [Visión y problema](#1-visión-y-problema)
2. [Decisiones de arquitectura](#2-decisiones-de-arquitectura-adr-resumidos)
3. [Estructura de carpetas](#3-estructura-de-carpetas)
4. [Stack y dependencias](#4-stack-y-dependencias)
5. [Arquitectura — orquestador y flujo](#5-arquitectura--orquestador-y-flujo)
6. [Cascada multi-modelo](#6-cascada-multi-modelo-haiku--sonnet--opus)
7. [Prompt pipeline](#7-prompt-pipeline-composable)
8. [Reglas de negocio](#8-reglas-de-negocio)
9. [Casos de uso (intenciones)](#9-casos-de-uso--intenciones)
10. [Datos](#10-datos)
11. [Rate limiting transversal](#11-rate-limiting-transversal-5-niveles)
12. [Cost guard](#12-cost-guard)
13. [API & schemas](#13-api--schemas)
14. [CLI](#14-cli-de-debug)
15. [Servidor MCP](#15-servidor-mcp)
16. [Testing y cobertura](#16-testing-y-cobertura)
17. [Comandos](#17-comandos)
18. [Configuración (env vars)](#18-configuración-variables-de-entorno)
19. [Riesgos abiertos](#19-riesgos-abiertos)
20. [Instrucciones para diagramas](#20-instrucciones-para-diagramas)

---

## 1. Visión y problema

**Problema.** Un ciudadano que tiene un problema con su banco, una multa del SII o una compra fallida no sabe a qué organismo acudir. La información pública existe pero está fragmentada en portales, leyes y procedimientos heterogéneos. Las páginas de auto-atención (CMF Online, SERNAC reclamos, SII online) están detrás de **ClaveÚnica/ClaveTributaria**, así que **no son scrapeables** sin sesión.

**Hipótesis.** Un agente conversacional puede:
1. Leer una consulta en lenguaje natural.
2. Detectar el organismo competente usando el **marco legal** como árbitro (no la opinión del modelo).
3. Citar la ley/circular aplicable y derivar a un canal público verificable (fono, portal raíz).
4. Cuando el caso cae en CMF, además recomendar el servicio curado del JSON.

**Importancia.** Reduce ambigüedad cross-organismo (ej: "tengo problema con seguro de mi auto" → SERNAC si es retail, CMF si es póliza fiscalizada) y entrega respuestas **auditables** (cada decisión queda registrada en `reasoning[]`).

---

## 2. Decisiones de arquitectura (ADR resumidos)

| ID | Decisión | Razón |
|---|---|---|
| ADR-001 | **Anthropic SDK puro**, sin frameworks (no claude-agent-sdk, no pydantic-ai) | Control total sobre tool-loop; sin dependencias Node.js; ecosistema 100% Anthropic; auditabilidad |
| ADR-002 | **Plugin pattern** por organismo (`OrganismoPlugin`) | Agregar SERNAC/SII fue zero-touch en el orquestador; aislamiento de datos curados |
| ADR-003 | **Capa Legal transversal** como router cross-organismo | SERNAC/SII no son scrapeables → el corpus legal mapea consultas a organismo competente vía `organismos_competentes` |
| ADR-004 | **Cascada Haiku → Sonnet → Opus** | Haiku triage barato detecta fuera-de-scope; Sonnet hace tool-loop por defecto; Opus solo en casos legales pesados |
| ADR-005 | **Prompt cache de Anthropic** (`cache_control: ephemeral`) | System prompt + tools schema son estables → 90% off en lecturas repetidas |
| ADR-006 | **Extended thinking solo en escalation** | Ahorro de tokens; razonamiento profundo solo cuando vale la pena |
| ADR-007 | **Rate limit token-bucket en proceso** (no Redis) | PoC monolítico; 5 scopes cubren el espectro (IP, conv, modelo) |
| ADR-008 | **Cost tracker con multiplicadores cache** (1.25× write, 0.10× read) | Refleja pricing real de Anthropic; budget diario corta antes de quemar plata |
| ADR-009 | **ChromaDB local** + `paraphrase-multilingual-MiniLM-L12-v2` | RAG persistente sin servicio externo; embeddings ES nativos |
| ADR-010 | **Schemas de tools centralizados** en cada plugin | Misma definición consumida por FastAPI router y por servidor MCP (stdio) |

---

## 3. Estructura de carpetas

```
PoC-MVP-Challenge/
├── backend/                    Código del agente
│   ├── api/                    FastAPI: routers, schemas, middleware, DI
│   │   ├── app.py              Factory create_app() — CORS + RateLimitMiddleware
│   │   ├── dependencies.py     lru_cache de Settings, Anthropic, Registry, Limiter, etc.
│   │   ├── schemas.py          Pydantic: ChatRequest/Response, ReasoningStep, etc.
│   │   ├── middleware/
│   │   │   └── rate_limit.py   429 + Retry-After según RateLimiter
│   │   └── routers/
│   │       ├── chat.py         POST /chat (rate-checks → ChatService)
│   │       ├── feedback.py     POST /feedback
│   │       └── health.py       GET /health  GET /metrics
│   ├── core/                   Tipos transversales (sin dependencias de framework)
│   │   ├── exceptions.py       LLMError, ToolExecutionError, IntencionInvalidaError
│   │   ├── intenciones_globales.py  ALERTA, OUT_OF_SCOPE
│   │   ├── models.py           ServiceItem, IntencionDef, ToolDef
│   │   └── plugin.py           Protocolo OrganismoPlugin
│   ├── plugins/                Un módulo por organismo
│   │   ├── cmf.py              CMF — RAG sobre data/cmf/services.json
│   │   ├── legal.py            Marco normativo transversal (RAG corpus legal)
│   │   ├── sernac.py           Solo prompt fragment + canales públicos (sin RAG)
│   │   └── sii.py              Solo prompt fragment + canales públicos (sin RAG)
│   ├── prompt/
│   │   └── pipeline.py         Composable PromptSection → system prompt versionado
│   ├── services/               Lógica del agente
│   │   ├── chat_service.py     Orquestador: cascada + tool-loop + reasoning trace
│   │   ├── conversation_store.py  Conversaciones efímeras con TTL
│   │   ├── cost_tracker.py     Budget diario USD con multiplicadores cache
│   │   ├── model_router.py     RouteDecision Haiku/Sonnet/Opus
│   │   └── rate_limiter.py     TokenBucket + 5 scopes
│   ├── bootstrap.py            Wire-up: Settings → Registry → ChatService
│   ├── cli.py                  CLI debug (argparse + ANSI) — auditar cascada localmente
│   ├── logging_setup.py        Logger JSON estructurado
│   ├── mcp_server.py           Servidor MCP stdio (mismas tools que la API)
│   ├── registry.py             PluginRegistry: descubre intenciones + tools + ingest RAG
│   ├── repository.py           SQLite append-only de interacciones + feedback
│   ├── settings.py             Settings (pydantic_settings) — single source of truth
│   └── vector_store.py         ChromaDB + sentence-transformers (singleton lazy)
├── tests/
│   ├── conftest.py             Fixtures + reset de env entre tests
│   ├── unit/                   23 archivos — un test por módulo
│   └── integration/            test_api.py, test_rate_limit_middleware.py
├── data/
│   ├── cmf/services.json       37 servicios CMF curados (output de scraper, 102 KB)
│   └── legal/articulos.json    Corpus legal multi-organismo (32 KB)
├── chroma_db/                  Vector store persistido (gitignored)
├── main.py                     Entrypoint: app = create_app()
├── check.ps1                   Quality gate (ruff + mypy + pytest)
├── pyproject.toml              ruff + mypy + pytest config
├── requirements.txt            Runtime deps
├── requirements-dev.txt        Dev/test deps
├── .env.example                Plantilla de configuración
└── .env                        Configuración real (gitignored)
```

### Uso de cada carpeta

| Carpeta | Responsabilidad | Acoplamiento |
|---|---|---|
| `backend/core/` | Tipos puros, sin FastAPI ni Anthropic | Importable desde cualquier capa |
| `backend/plugins/` | Conocimiento de cada organismo (datos + intenciones + tool schemas + prompt fragment) | Solo depende de `core` y `vector_store` |
| `backend/prompt/` | Construcción del system prompt | Lee `Registry` |
| `backend/services/` | Lógica de aplicación (orquestación, cascada, costos, rate limits) | Inyecta plugins vía registry |
| `backend/api/` | Capa HTTP (FastAPI) | Inyecta services |
| `backend/mcp_server.py` | Capa MCP (stdio) — alternativa a HTTP | Comparte registry y servicios |
| `data/` | JSON curados (no se editan en runtime) | Los plugins los leen al boot |
| `chroma_db/` | Embeddings persistidos | Regenerable desde `data/` |
| `tests/` | unit aislado + integration con TestClient | Mocks de Anthropic |

---

## 4. Stack y dependencias

| Categoría | Tech | Versión | Por qué |
|---|---|---|---|
| LLM | `anthropic` SDK | 0.96.0 | Cliente oficial; tool-use, prompt cache, extended thinking |
| API | `fastapi` | 0.136.1 | Tipado + DI + middleware |
| Schemas | `pydantic` v2 | 2.13.2 | Validación + settings |
| Vector DB | `chromadb` | 1.5.8 | Embebido, persistente local |
| Embeddings | `sentence-transformers` | — | `paraphrase-multilingual-MiniLM-L12-v2` (ES nativo) |
| MCP | `mcp` | 1.27.0 | Servidor stdio compatible Claude Desktop/Code |
| Test | `pytest` + `pytest-cov` + `pytest-asyncio` | 8.3.4 | Async + cobertura |
| Lint | `ruff` | 0.9.4 | E/F/I/B/UP/SIM/N/C90 + complejidad ≤10 |
| Types | `mypy` | 1.14.1 | `disallow_untyped_defs=true` en backend/ |

**Python**: 3.11+ (target_version=`py311`).

---

## 5. Arquitectura — orquestador y flujo

### Capas

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENTE (HTTP / MCP / CLI)                                      │
└─────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ Capa transporte                                                 │
│   • FastAPI: RateLimitMiddleware → /chat, /feedback, /health    │
│   • MCP server stdio: tools = registry.tool_schemas()           │
│   • CLI argparse: ANSI debug local                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ ChatService (orquestador)                                       │
│   1. limiter.check_ip / check_conversation                      │
│   2. cost_tracker.would_exceed(0)                               │
│   3. _run_triage() → Haiku decide ALERTA / OUT_OF_SCOPE         │
│   4. ModelRouter.main_model() → Sonnet o Opus                   │
│   5. tool-loop (max 5 iter, 30s timeout)                        │
│        └─ registry.execute_tool(name, args)                     │
│   6. Construye ReasoningStep[] (modelo, fase, tokens, cost)     │
│   7. repository.append(interaction)                             │
│   8. cost_tracker.record(total)                                 │
└──────┬─────────────┬─────────────┬─────────────┬────────────────┘
       │             │             │             │
   PromptPipeline  Registry    RateLimiter   CostTracker
       │             │
       │     ┌───────┴────────────────┐
       │     │ OrganismoPlugin (×N)   │
       │     │  • intenciones         │
       │     │  • tool_defs           │
       │     │  • tool_handlers       │
       │     │  • prompt_fragment     │
       │     │  • ingest() → RAG      │
       │     └───────┬────────────────┘
       │             │
       │     ┌───────▼────────┐
       │     │ VectorStore    │ ChromaDB + ST embeddings
       │     └────────────────┘
       │
   System prompt v3.0.0-marco-legal
   (CoreIdentity + Organismos + Tools + IntencionesGlobales)
```

### Flujo de un turno (POST /chat)

```
Client → Middleware → Router /chat → ChatService.chat()
   ├─ pre-checks: IP rate, conv rate, budget
   ├─ run_triage() — Haiku (opcional)
   │    ├─ ALERTA → respuesta directa, no llama Sonnet
   │    └─ OK → continua
   ├─ ModelRouter.main_model(msg)
   │    ├─ keywords legales → escalation (Opus + thinking)
   │    ├─ iteration ≥ 3 → escalation
   │    └─ default → Sonnet
   ├─ messages.create(model, tools, cache_control)
   │    └─ tool_use loop (registry.execute_tool)
   ├─ ReasoningStep por cada llamada al LLM
   └─ ChatResponse(response, reasoning, cost, tokens)
```

---

## 6. Cascada multi-modelo (Haiku → Sonnet → Opus)

### Triggers

| Fase | Modelo | Cuándo |
|---|---|---|
| `triage` | `claude-haiku-4-5` | Siempre primero (si `enable_triage=true`); detecta `ALERTA` (estafa, fraude, urgencia) y `OUT_OF_SCOPE` (prompt injection, no-Chile) |
| `default` | `claude-sonnet-4-5` | Turno estándar; maneja tool-loop normal |
| `escalation` | `claude-opus-4-6` | Si query contiene keywords legales (`demanda`, `tribunal`, `querella`, `información privilegiada`, …) o si `iteration ≥ 3` (loop atascado) |
| `override` | a elección | Solo si `SEGURITO_ALLOW_MODEL_OVERRIDE=true`; CLI `--force-model` |

Constante de threshold: `ESCALATION_ITERATION_THRESHOLD = 3`.

### Pricing (USD por 1M tokens)

| Modelo | Input | Output |
|---|---|---|
| Haiku 4.5 | 1.00 | 5.00 |
| Sonnet 4.5 | 3.00 | 15.00 |
| Opus 4.6 | 15.00 | 75.00 |

Multiplicadores prompt-cache:
- **Cache write**: 1.25× input
- **Cache read**: 0.10× input  ← descuento del 90%

### Optimización aplicada

| Técnica | Cómo | Impacto |
|---|---|---|
| Prompt caching | `cache_control={"type":"ephemeral"}` en system + tools | ~90% off en lecturas repetidas (verificado en smoke: 3407 cache_read tokens) |
| Triage Haiku | 1 llamada extra de ~150 tokens; corta antes si ALERTA/OUT_OF_SCOPE | Evita Sonnet/Opus en casos triviales |
| Extended thinking solo escalation | `thinking={"type":"enabled","budget_tokens":2048}` + `temperature=1.0` | Razonamiento profundo solo cuando lo amerita |
| `temperature=0` por defecto | Determinismo en respuestas legales | Auditabilidad |

---

## 7. Prompt pipeline composable

`backend/prompt/pipeline.py` define `PromptSection` (ABC) y compone:

| Sección | Render | Cacheable |
|---|---|---|
| `CoreIdentitySection` | "Eres Segurito… organismos: cmf, legal, sernac, sii" | sí |
| `OrganismosSection` | Concatena `prompt_fragment` de cada plugin activo | sí |
| `ToolsContractSection` | Reglas de uso de tools (cuándo invocar `consultar_marco_legal`, etc.) | sí |
| `IntencionesGlobalesSection` | ALERTA + OUT_OF_SCOPE handling | sí |

Versión actual: **v3.0.0-marco-legal** (constante `PROMPT_VERSION`).

Agregar un organismo nuevo no requiere tocar el pipeline: el plugin aporta su `prompt_fragment` y el registry lo descubre.

---

## 8. Reglas de negocio

### 8.1 Detección de organismo competente

> El **marco legal** es el árbitro, no la opinión del modelo.

Cuando una consulta es ambigua (ej: "problema con seguro de auto"), el agente debe llamar `consultar_marco_legal(query)`. El corpus retorna artículos con campo `organismos_competentes: ["cmf"]` o `["sernac"]`. Esto desambigua sin alucinación.

### 8.2 Hand-off cuando hay barrera de auth

SERNAC y SII tienen sus servicios de auto-atención detrás de ClaveÚnica/ClaveTributaria. **No se scrapean.** El agente:
1. Identifica que es competencia SERNAC/SII vía marco legal.
2. Cita el artículo aplicable.
3. Deriva al canal público verificable (fono o portal raíz declarado en `prompt_fragment`).

### 8.3 ALERTA prioritaria

Si triage Haiku detecta `ALERTA` (estafa, fraude, urgencia):
- Respuesta inmediata sin llamar Sonnet/Opus.
- Mensaje template: "no entregues datos, corta contacto, denuncia en PDI 134".

### 8.4 OUT_OF_SCOPE

Triage detecta consultas no relacionadas con servicios públicos chilenos o intentos de prompt injection. Respuesta cortés delimitando alcance.

### 8.5 Iteraciones acotadas

- Máximo `5` iteraciones del tool-loop.
- Timeout duro `30s`.
- En iteración ≥ 3 se escala automáticamente a Opus (asumimos que Sonnet se atascó).

### 8.6 Confirmación humana (HITL)

`ChatResponse.requiere_confirmacion: bool` — el plugin puede marcar respuestas que requieren validación humana antes de enviarse a producción (no automático en PoC).

---

## 9. Casos de uso — intenciones

### 9.1 Globales (`backend/core/intenciones_globales.py`)

| Intención | Trigger | Acción |
|---|---|---|
| `ALERTA` | Estafa, fraude, urgencia | Respuesta-template; no consume tools |
| `OUT_OF_SCOPE` | No-Chile, prompt injection | Cortar amablemente |

### 9.2 CMF (`backend/plugins/cmf.py`)

| Intención | Descripción | Tool sugerida |
|---|---|---|
| `RECLAMO` | Disputa concreta con entidad fiscalizada (banco, AFP, aseguradora) | `buscar_servicios_cmf(intencion="RECLAMO")` |
| `CONSULTA` | Pregunta informativa sobre productos/derechos | `buscar_servicios_cmf(intencion="CONSULTA")` |
| `TRAMITE` | Iniciar proceso administrativo (ej: certificado vigencia) | `buscar_servicios_cmf(intencion="TRAMITE")` |

Tools CMF:
- `buscar_servicios_cmf(query, intencion?, n_results=3)` — RAG sobre 37 servicios.
- `obtener_detalle_servicio_cmf(servicio_id)` — devuelve item completo del JSON.

### 9.3 Legal (`backend/plugins/legal.py`)

Sin intenciones (transversal). Una sola tool:
- `consultar_marco_legal(query, n_results=5)` — retorna artículos con `organismos_competentes`.

### 9.4 SERNAC y SII

Sin tools, solo `prompt_fragment`. Hand-off a canales públicos.

---

## 10. Datos

### 10.1 `data/cmf/services.json` (37 servicios)

Schema:
```json
{
  "id": "string",
  "title": "string",
  "url": "string (oficial cmfchile.cl)",
  "intencion": "RECLAMO | CONSULTA | TRAMITE",
  "description": "string",
  "tags": ["string"]
}
```

Origen: scraper Playwright legacy (eliminado del repo). Output curado y persistido. Re-scrape no automático.

### 10.2 `data/legal/articulos.json` (corpus legal)

Schema:
```json
{
  "id": "ley-xxx-art-y",
  "titulo": "string",
  "texto": "string (texto legal completo)",
  "organismos_competentes": ["cmf" | "sernac" | "sii"],
  "fuente_url": "string (leychile.cl / sii.cl / ...)"
}
```

Cubre Ley 19.496 (consumidor → SERNAC), DL 824/825 (renta/IVA → SII), Ley 18.045/18.046 (mercado de valores → CMF), entre otras.

### 10.3 ChromaDB

Colecciones separadas por plugin (`cmf`, `legal`). Embedding `paraphrase-multilingual-MiniLM-L12-v2` (384 dims, multilingüe ES-EN).

Ingest se ejecuta una vez al boot (`registry.ingest_all()`); idempotente sobre `id`.

### 10.4 Conversaciones

`ConversationStore` — in-memory, TTL 30 min. No persistente. Para producción reemplazar por Redis.

### 10.5 Interacciones

`InteractionRepository` — SQLite append-only en `segurito.db`. Cada turno guarda: id, timestamp, organismo, intencion, model_used_final, total_cost_usd, helpful (post feedback).

---

## 11. Rate limiting transversal (5 niveles)

Token bucket en proceso (`threading.Lock`), buckets lazy por scope+key.

| Scope | Capacity (default) | Refill | Key |
|---|---|---|---|
| `ip-min` | 60 | 60/min | `request.client.host` (o X-Forwarded-For) |
| `ip-day` | 1000 | 1000/día | idem |
| `conv-hour` | 120 | 120/hora | `conversation_id` |
| `model-min:claude-sonnet-4-5` | 40 | 40/min | global (key fijo) |
| `model-min:claude-opus-4-6` | 10 | 10/min | global |
| `opus-conv` | 5 | 5/conv | `conversation_id` |

> Haiku no tiene rate limit propio (volumen alto, costo bajo).

Cuando se excede:
- Middleware HTTP → `429 Too Many Requests` + header `Retry-After: <segundos>`.
- Body JSON: `{"detail": "...", "scope": "...", "retry_after_s": N}`.

---

## 12. Cost guard

`CostTracker` — bucket diario en memoria (`_DayBucket`), rolling automático al cambiar de fecha.

```
estimate_cost_usd(model, input_tokens, output_tokens, cache_creation, cache_read)
  = pricing[model].input  · (input + 1.25·cache_creation + 0.10·cache_read) / 1e6
  + pricing[model].output · output / 1e6
```

Pre-check antes de cada turno: `cost_tracker.would_exceed(0.0)` → si el budget diario ya está agotado, 429 con `Retry-After: 3600`.

Default: `SEGURITO_COST_BUDGET_DAY_USD=10.0`.

---

## 13. API & schemas

### POST `/chat`

Request:
```json
{
  "message": "...",
  "conversation_id": "uuid|null"
}
```

Response (`ChatResponse`):
```json
{
  "interaction_id": "uuid",
  "conversation_id": "uuid",
  "response": "texto al usuario",
  "organismo_detectado": "cmf|sernac|sii|null",
  "intencion": "RECLAMO|CONSULTA|TRAMITE|ALERTA|OUT_OF_SCOPE|null",
  "servicio_id": "string|null",
  "servicios_encontrados": ["id1", "id2"],
  "requiere_confirmacion": false,
  "tools_used": [{"name": "...", "input": {...}}],
  "iterations": 2,
  "elapsed_ms": 13996,
  "reasoning": [
    {
      "model": "claude-haiku-4-5",
      "phase": "triage",
      "reason": "triage inicial: clasificar intención",
      "thinking": null,
      "elapsed_ms": 880,
      "input_tokens": 163,
      "output_tokens": 4,
      "cache_read_tokens": 0,
      "cache_creation_tokens": 0,
      "cost_usd": 0.000183
    },
    { "model": "claude-sonnet-4-5", "phase": "default", "...": "..." }
  ],
  "model_used_final": "claude-sonnet-4-5",
  "total_input_tokens": 521,
  "total_output_tokens": 455,
  "total_cache_read_tokens": 3407,
  "total_cache_creation_tokens": 0,
  "total_cost_usd": 0.009044
}
```

### POST `/feedback`
```json
{ "interaction_id": "uuid", "helpful": true, "comment": "string|null" }
```

### GET `/health`
```json
{ "status": "ok", "model": "claude-sonnet-4-5", "organismos": ["cmf","legal","sernac","sii"], "prompt_version": "v3.0.0-marco-legal" }
```

### GET `/metrics`
```json
{ "total_interactions": N, "by_organismo": {...}, "by_intencion": {...}, "feedback_helpful_rate": 0.87 }
```

### Errores
- `400` mensaje > 2000 chars
- `429` rate limit / cost budget (con `Retry-After`)
- `500` LLMError / ToolExecutionError

---

## 14. CLI de debug

Dos modos:

- **REPL** (sin argumentos): conversación interactiva persistente.
- **One-shot** (con `query` posicional): un turno y termina.

```bash
# Modo interactivo (REPL)
python -m backend.cli

# One-shot
python -m backend.cli "tu consulta"

Flags (aplican a ambos modos):
  --no-thinking          fuerza thinking_budget=0 (deshabilita extended thinking)
  --force-model MODEL    requiere SEGURITO_ALLOW_MODEL_OVERRIDE=true
  --no-cache             desactiva prompt cache
  --conversation-id UUID continúa una conversación previa (seed del REPL)
```

### Comandos del REPL

| Input | Acción |
|---|---|
| texto libre | turno normal; `conversation_id` se reusa entre turnos (multi-turno automático) |
| `exit` / `quit` / `salir` / `:q` | salir limpio (rc=0) |
| `:reset` | nueva conversación sin salir del REPL |
| línea vacía | ignora (no llama al LLM) |
| Ctrl+C / Ctrl+Z+Enter (EOF) | salir limpio |

Al salir imprime `turnos=N cost_total=$X.XXXXXX`.

### Output

- Cyan = triage · Green = default · Magenta = escalation · Yellow = override
- Por cada paso: razón, tokens (in/out/cache_r/cache_w), costo, elapsed, thinking truncado a 200 chars
- Línea final por turno: `organismo · intencion · iter · elapsed · cost · conversation_id`

`NO_COLOR=1` desactiva ANSI.

### Embeddings offline

El CLI fija `HF_HUB_OFFLINE=1` y `TRANSFORMERS_OFFLINE=1` por default (vía `setdefault`) para evitar HEAD a HuggingFace Hub que cuelga si la red es lenta. El modelo `paraphrase-multilingual-MiniLM-L12-v2` debe estar cacheado en `~/.cache/huggingface/`. Para descargarlo la primera vez:

```powershell
$env:HF_HUB_OFFLINE="0"
python -c "from backend.vector_store import _get_model; _get_model()"
```

### Smoke real ejecutado (2026-05-05)

Query: *"qué hacer si me llamó alguien diciendo que ganó plata invirtiendo en cripto"*

```
[1] TRIAGE · claude-haiku-4-5    in=163 out=4 cost=$0.000183 elapsed=880ms
[2] DEFAULT · claude-sonnet-4-5  in=358 out=451 cache_r=3407 cost=$0.008861 elapsed=13115ms
total: cost=$0.009044  iter=1  elapsed=13996ms
```

Cache hit confirmado (3407 tokens read = 90% off en esa porción del input).

---

## 15. Servidor MCP

`backend/mcp_server.py` expone vía stdio las **mismas tools** que la API HTTP (definidas en cada plugin). Compatible con Claude Desktop/Code:

```jsonc
// claude_desktop_config.json
{
  "mcpServers": {
    "segurito": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"],
      "env": { "ANTHROPIC_API_KEY": "..." }
    }
  }
}
```

---

## 16. Testing y cobertura

### Suite

| Carpeta | Archivos | Tests |
|---|---|---|
| `tests/unit/` | 23 | 179 |
| `tests/integration/` | 2 | 2 |
| **Total** | **25** | **181 passed, 1 warning, ~4.7s** |

### Cobertura actual (post-cleanup)

```
TOTAL  1299 stmts  66 miss  cov 94.10%  (umbral CI: 80%)
```

| Módulo | Cov | Stmts | Notas |
|---|---|---|---|
| `services/cost_tracker.py` | 100% | 42 | bucket diario + multipliers |
| `services/model_router.py` | 100% | 41 | RouteDecision frozen |
| `prompt/pipeline.py` | 100% | 62 | secciones composables |
| `core/exceptions.py` | 100% | 16 | |
| `core/models.py` | 100% | 17 | |
| `bootstrap.py` | 100% | 26 | |
| `repository.py` | 100% | 50 | SQLite append-only |
| `api/schemas.py` | 100% | 54 | |
| `settings.py` | 100% | 40 | |
| `plugins/sernac.py` / `sii.py` | 100% | 20 | |
| `plugins/legal.py` | 99% | 59 | |
| `registry.py` | 99% | 58 | |
| `plugins/cmf.py` | 96% | 68 | |
| `services/conversation_store.py` | 96% | 50 | |
| `services/rate_limiter.py` | 94% | 90 | branches refill |
| `api/routers/feedback.py` | 94% | 15 | |
| `services/chat_service.py` | 93% | 180 | branches del tool-loop |
| `core/plugin.py` | 92% | 25 | protocol abstract |
| `cli.py` | 90% | 67 | argparse paths |
| `mcp_server.py` | 85% | 52 | stdio mainloop |
| `api/routers/chat.py` | 72% | 41 | ramas de error |
| `vector_store.py` | 70% | 67 | ST require red para tests con modelo real |

### Qué cubre cada suite

**Unit aisladas:**
- `test_settings.py` — defaults FM1, override por env, escalation_keywords list parsing
- `test_model_router.py` — 13 tests: triage, default, escalation por keyword/iteration/explicit, override on/off
- `test_chat_service.py` — flujo legacy del tool-loop con mocks
- `test_chat_service_cascade.py` — 9 tests: triage on/off/falla, prompt cache on/off, thinking solo en escalation, reasoning trace, threshold de iteración
- `test_cost_tracker.py` — pricing Haiku/Sonnet/Opus, multiplicadores cache 1.25/0.10, fallback, day rollover, would_exceed
- `test_rate_limiter.py` — TokenBucket consume/refill, key isolation, opus-conv, Haiku no-limit, scope desconocido, RateLimitExceeded fields
- `test_cli.py` — basic query, missing API key→2, force-model bloqueado→2, --no-thinking, --help
- `test_registry.py` — descubrimiento de plugins, resolución de tools, ingest idempotente
- `test_repository.py` — append + query + feedback update
- `test_conversation_store.py` — TTL, get/append, rollover
- `test_prompt_pipeline.py` — render por sección, version constant
- `test_plugin_cmf.py`, `test_plugin_legal.py`, `test_plugins_presence.py` — schemas + tools + ingest
- `test_vector_store.py` — singleton, embed con stub
- `test_logging_setup.py`, `test_exceptions.py`, `test_intenciones_globales.py`, `test_core_models.py`, `test_bootstrap.py`, `test_mcp_server.py`

**Integration:**
- `test_api.py` — TestClient end-to-end con Anthropic mockeado
- `test_rate_limit_middleware.py` — `/health` exempt; `/chat` 429 al exceder bucket

### Lo que NO se testea
- Anthropic API real (requeriría key + tokens; se ejecuta manualmente vía CLI smoke).
- Descarga real del modelo de embeddings (HuggingFace) — requiere red.

---

## 17. Comandos

### Referencia rápida

| Qué | Comando |
|---|---|
| Crear venv | `python -m venv .venv` |
| Activar venv (Windows) | `.\.venv\Scripts\Activate.ps1` |
| Instalar deps | `pip install -r requirements.txt -r requirements-dev.txt` |
| Quality gate completo | `.\check.ps1` |
| Servidor HTTP | `uvicorn main:app --reload` (→ http://127.0.0.1:8000/docs) |
| **CLI interactivo (REPL)** | `python -m backend.cli` |
| CLI one-shot | `python -m backend.cli "tu consulta"` |
| CLI sin thinking | `python -m backend.cli --no-thinking "X"` |
| CLI forzar Opus | `$env:SEGURITO_ALLOW_MODEL_OVERRIDE="true"; python -m backend.cli --force-model claude-opus-4-6 "X"` |
| CLI continuar conversación | `python -m backend.cli --conversation-id UUID` |
| MCP server stdio | `python -m backend.mcp_server` |
| Solo linter | `ruff check backend tests` |
| Solo type-check | `mypy backend` |
| Solo tests | `pytest -q` |
| Tests + HTML coverage | `pytest --cov=backend --cov-report=html` (→ `htmlcov/index.html`) |
| Test selectivo | `pytest -k "rate_limit" -v` |
| Fix encoding PowerShell (tildes) | `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` |
| Descargar modelo ST (1ª vez) | `$env:HF_HUB_OFFLINE="0"; python -c "from backend.vector_store import _get_model; _get_model()"` |
| Reset ChromaDB | `Remove-Item chroma_db -Recurse -Force` (se regenera al boot) |

### Encoding correcto en PowerShell (problema visto con tildes)

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

Los `.py` están en UTF-8; PowerShell por default los muestra como CP-1252. Aplicar lo de arriba antes de `Get-Content` o ejecutar el CLI.

### Setup desde cero (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
# editar .env con ANTHROPIC_API_KEY
# Primera vez: descargar modelo de embeddings (~470 MB)
$env:HF_HUB_OFFLINE="0"
python -c "from backend.vector_store import _get_model; _get_model()"
# Verificar gate
.\check.ps1
```

---

## 18. Configuración (variables de entorno)

Todas con prefijo `SEGURITO_*`. Defaults vivos en [`backend/settings.py`](backend/settings.py).

| Var | Default | Significado |
|---|---|---|
| `ANTHROPIC_API_KEY` | (vacío) | Obligatoria para invocar Anthropic |
| `SEGURITO_MODEL_TRIAGE` | `claude-haiku-4-5` | Modelo fase triage |
| `SEGURITO_MODEL_DEFAULT` | `claude-sonnet-4-5` | Modelo fase default |
| `SEGURITO_MODEL_ESCALATION` | `claude-opus-4-6` | Modelo fase escalation |
| `SEGURITO_ENABLE_TRIAGE` | `true` | Si `false`, salta Haiku y va directo a Sonnet |
| `SEGURITO_ENABLE_PROMPT_CACHE` | `true` | Si `false`, no inyecta `cache_control` |
| `SEGURITO_ALLOW_MODEL_OVERRIDE` | `false` | Permite `--force-model` |
| `SEGURITO_THINKING_BUDGET` | `2048` | Tokens de thinking en escalation; 0 desactiva |
| `SEGURITO_ESCALATION_KEYWORDS` | (8 keywords) | JSON list; trigger Opus |
| `SEGURITO_RL_IP_MIN` | `60` | Rate limit por IP/min |
| `SEGURITO_RL_IP_DAY` | `1000` | Rate limit por IP/día |
| `SEGURITO_RL_CONV_HOUR` | `120` | Rate limit por conv/hora |
| `SEGURITO_RL_SONNET_MIN` | `40` | Rate limit Sonnet/min global |
| `SEGURITO_RL_OPUS_MIN_GLOBAL` | `10` | Rate limit Opus/min global |
| `SEGURITO_RL_OPUS_CONV` | `5` | Rate limit Opus/conv |
| `SEGURITO_COST_BUDGET_DAY_USD` | `10.0` | Budget diario duro |
| `SEGURITO_MAX_TOOL_ITERATIONS` | `5` | Tope tool-loop |
| `SEGURITO_TOOL_LOOP_TIMEOUT` | `30` | Segundos timeout |
| `SEGURITO_MAX_USER_INPUT` | `2000` | Chars máx en `message` |
| `SEGURITO_ENABLED_ORGANISMOS` | `["cmf","legal","sernac","sii"]` | JSON list |
| `SEGURITO_CORS_ORIGINS` | `["*"]` | CORS |
| `SEGURITO_LOG_LEVEL` | `INFO` | |
| `SEGURITO_CONVERSATION_TTL` | `1800` | Segundos |
| `SEGURITO_MCP_HOST` / `_MCP_PORT` | `127.0.0.1` / `8765` | Solo si se usa MCP TCP en vez de stdio |

---

## 19. Riesgos abiertos

| ID | Riesgo | Severidad | Mitigación pendiente |
|---|---|---|---|
| R-001 | **Hallucination de URLs** — el modelo cita deep-links de su entrenamiento (ej: CMF Educa) que ya no existen | Alta | Validador post-LLM + allowlist + system prompt prohibiendo URLs no-tool. Detectado en smoke 2026-05-05 |
| R-002 | Rate limiter en proceso no resiste multi-instancia | Media | Migrar a Redis para producción |
| R-003 | `ConversationStore` in-memory (TTL 30 min); reinicio = pérdida | Media | Redis con persistencia |
| R-004 | Costo de embeddings al primer arranque (descarga ST de HF) | Baja | Pre-bake imagen Docker con modelo cacheado |
| R-005 | SERNAC/SII sin RAG — solo derivación a fono | Aceptado para PoC | Si abren API pública, plugin futuro |
| R-006 | Triage Haiku puede generar falsos positivos `OUT_OF_SCOPE` | Media | Métricas + fail-soft (ya implementado: APIError → continúa) |
| R-007 | Coverage de `vector_store.py` 70% por dependencia de red | Baja | Acepta. ST se mockea en tests unitarios |

> R-001 está documentado en detalle en memoria del repo: `/memories/repo/url-hallucination-risk.md`.



## Anexo A — Resumen ejecutivo (TL;DR)

- Backend Python 3.11 con FastAPI + Anthropic SDK puro.
- Cascada Haiku → Sonnet → Opus con triage barato + escalation por keywords/iter.
- Plugin pattern por organismo (CMF/LEGAL/SERNAC/SII); marco legal arbitra desambiguación.
- 5 niveles de rate limit + cost guard diario.
- Prompt cache + extended thinking solo en escalation.
- 181 tests, cobertura 94.10%, ruff + mypy clean.
- Triple entrypoint: HTTP, MCP stdio, CLI debug.
- Riesgo abierto principal: hallucination de URLs (mitigación pendiente).
