# Segurito

> Asistente público chileno que orienta a ciudadanos sobre servicios de organismos del Estado (CMF, SERNAC, SII), anclado en marco legal verificable.
> PoC para **Claude Impact Lab Chile 2026**.

La especificación completa, ADRs, diagramas y referencia de comandos viven en [spec-doc.md](spec-doc.md). Este README es el **quickstart** y un mapa del repo.

---

## ¿Qué hace?

1. Lee una consulta en lenguaje natural ("me llamó alguien diciendo que ganó plata invirtiendo en cripto").
2. Detecta el organismo competente usando el **marco legal** como árbitro (no la opinión del modelo).
3. Cita la ley/circular aplicable y deriva a un canal público verificable (fono, portal raíz).
4. Cuando el caso cae en CMF, además recomienda el servicio curado del JSON.

Cada decisión queda en `reasoning[]` — respuestas auditables, no caja negra.

### Cascada multi-modelo

```
[1] TRIAGE      claude-haiku-4-5    barato, detecta fuera de scope
[2] DEFAULT     claude-sonnet-4-5   tool-loop, RAG, respuesta
[3] ESCALATION  claude-opus-4-6     solo cuando el legal lo amerita
```

Con `prompt cache` (system + tools schema = ephemeral) y `extended thinking` solo en escalation.

---

## Setup (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
# editar .env y poner ANTHROPIC_API_KEY=sk-...

# Primera vez: descargar modelo de embeddings (~470 MB)
$env:HF_HUB_OFFLINE="0"
python -c "from backend.vector_store import _get_model; _get_model()"

# Verificar quality gate
.\check.ps1
```

`check.ps1` corre `ruff check` + `mypy backend` + `pytest --cov=backend --cov-fail-under=80`.

> **Nota encoding**: si ves tildes rotas en PowerShell, ejecutá:
> `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8`

---

## Cómo correrlo

### CLI interactivo (REPL) — recomendado para probar

```powershell
python -m backend.cli
```

Conversación persistente entre turnos. Comandos: `exit` / `quit` / `salir` / `:q` / Ctrl+C / Ctrl+Z+Enter para salir; `:reset` para nueva conversación. Imprime cascada paso a paso (cyan = triage, green = default, magenta = escalation), tokens, costo USD por step y respuesta final.

### CLI one-shot

```powershell
python -m backend.cli "tengo un problema con mi banco, me cobraron de más"
python -m backend.cli --no-thinking "consulta"
$env:SEGURITO_ALLOW_MODEL_OVERRIDE="true"
python -m backend.cli --force-model claude-opus-4-6 "X"
```

### Servidor HTTP

```powershell
uvicorn main:app --reload
# http://127.0.0.1:8000/docs
```

Endpoints: `POST /chat`, `POST /feedback`, `GET /health`, `GET /metrics`. Rate limit en middleware con 5 scopes (IP global, IP por minuto, conversación, modelo Opus, anti-burst). Devuelve 429 con `Retry-After`.

### Servidor MCP (stdio)

```powershell
python -m backend.mcp_server
```

Mismas tools que la API, expuestas vía protocolo MCP (consumible por Claude Desktop u otros clientes).

---

## Estructura

```
backend/
├── api/             FastAPI: routers, schemas, middleware, DI (lru_cache)
├── core/            Tipos transversales (sin framework)
├── plugins/         Un módulo por organismo (cmf, legal, sernac, sii)
├── prompt/          Prompt pipeline composable
├── services/        chat_service (orquestador), rate_limiter, cost_tracker, model_router, conversation_store
├── bootstrap.py     Wire-up Settings → Registry → ChatService
├── cli.py           CLI debug REPL + one-shot
└── mcp_server.py    Servidor MCP stdio
data/
├── cmf/services.json       Curado CMF (~38 servicios)
└── legal/articulos.json    Corpus legal (DFL 3, DL 3500, Ley 19.496, DL 824, DL 825, ...)
tests/
├── unit/            Cobertura ≥ 80% (185 tests, 94% actual)
└── integration/     API end-to-end + middleware rate-limit
main.py              ASGI entry point (FastAPI)
spec-doc.md          Especificación completa
check.ps1            Quality gate one-shot
```

---

## Decisiones clave (ADR)

| ID | Decisión |
|---|---|
| ADR-001 | **Anthropic SDK puro**, sin frameworks |
| ADR-002 | **Plugin pattern** por organismo (`OrganismoPlugin`) |
| ADR-003 | **Capa Legal transversal** como router cross-organismo |
| ADR-004 | **Cascada Haiku → Sonnet → Opus** |
| ADR-005 | **Prompt cache** (`cache_control: ephemeral`) en system + tools |
| ADR-006 | **Extended thinking solo en escalation** |
| ADR-007 | **Rate limit token-bucket en proceso** (no Redis) — 5 scopes |
| ADR-008 | **Cost tracker** con multiplicadores cache (1.25× write, 0.10× read) |
| ADR-009 | **ChromaDB local** + `paraphrase-multilingual-MiniLM-L12-v2` |
| ADR-010 | **Schemas de tools centralizados** (FastAPI + MCP comparten) |

Razones extendidas en [spec-doc.md §2](spec-doc.md#2-decisiones-de-arquitectura-adr-resumidos).

---

## Calidad

- **Tests**: 185 passed, **cobertura 93.95%** (gate `--cov-fail-under=80`).
- **Lint**: `ruff check backend tests` limpio.
- **Types**: `mypy backend` strict, 37 archivos.

```powershell
.\check.ps1                                          # gate completo
pytest -q                                            # solo tests
pytest --cov=backend --cov-report=html               # → htmlcov/index.html
pytest -k "rate_limit" -v                            # selectivo
```

---

## Configuración

Todas las env vars con prefijo `SEGURITO_*` están listadas en `.env.example` y documentadas en [spec-doc.md §18](spec-doc.md#18-configuración-variables-de-entorno). Las más usadas:

| Var | Default | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | obligatoria |
| `SEGURITO_ENABLED_ORGANISMOS` | `["cmf","sernac","sii","legal"]` | qué plugins cargar |
| `SEGURITO_ENABLE_TRIAGE` | `true` | activar Haiku triage |
| `SEGURITO_THINKING_BUDGET` | `4000` | tokens de extended thinking en escalation |
| `SEGURITO_ENABLE_PROMPT_CACHE` | `true` | prompt cache de Anthropic |
| `SEGURITO_COST_BUDGET_USD_PER_DAY` | `5.0` | hard stop diario |
| `SEGURITO_ALLOW_MODEL_OVERRIDE` | `false` | habilita `--force-model` en CLI |
| `HF_HUB_OFFLINE` | `1` (CLI) | embeddings desde caché local |

---

## Riesgos abiertos

- **R-001 — URL hallucination**: el modelo puede generar URLs específicas que no existen (ej: `cmfchile.cl/educa/621/...` que da 404). Mitigación pendiente: validador post-LLM con allowlist de dominios + verificación de paths contra los servicios curados.

Lista completa en [spec-doc.md §19](spec-doc.md#19-riesgos-abiertos).

---

## Licencia y créditos

PoC interna para Claude Impact Lab Chile 2026. Datos curados de fuentes públicas (CMF, BCN, SII, SERNAC). El agente cita ley y deriva a canal público verificable; nunca recolecta credenciales del ciudadano.
