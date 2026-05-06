# Track B — Extensiones Backend Python

## Objetivo
Extender el backend existente (`poc-v2`) para soportar adjuntos opcionales en `ChatRequest` y mejorar la precisión del plugin CMF para reclamos.

## Responsable
Dev técnico principal (Python/FastAPI).

## Archivos a tocar (con precaución)

### 1. `backend/api/schemas.py` — Agregar `Attachment` + extender `ChatRequest`

**Qué cambiar:**
- Agregar modelo `Attachment`:
  ```python
  class Attachment(BaseModel):
      mime_type: str
      filename: str
      base64_data: str  # máximo ~5MB decodificado
      description: str | None = None  # OCR o texto extraído (lo puede poner el bridge)
  ```
- Extender `ChatRequest`:
  ```python
  class ChatRequest(BaseModel):
      message: str = Field(..., min_length=1, max_length=2000)
      conversation_id: str | None = None
      attachments: list[Attachment] | None = None  # NUEVO, opcional
  ```

**Restricciones:**
- No modificar `ChatResponse`.
- No romper tests existentes: `attachments=None` debe ser default válido.

### 2. `backend/api/routers/chat.py` — Parsear attachments opcional

**Qué cambiar:**
- En la función `chat()`, extraer `req.attachments`.
- Si hay adjuntos, pasarlos a `ChatService.chat()`.

**Restricciones:**
- Si `attachments` es `None`, comportamiento idéntico al actual.
- Validar que no se exceda un límite razonable (ej: max 3 adjuntos, max 5MB cada uno).

### 3. `backend/services/chat_service.py` — Inyectar attachments en messages[]

**Qué cambiar:**
- Extender el método que construye los `messages` para Anthropic.
- Si hay adjuntos de tipo `image/*`, convertirlos a bloques `image` en el formato de Anthropic:
  ```json
  {
    "type": "image",
    "source": {
      "type": "base64",
      "media_type": "image/jpeg",
      "data": "base64_data"
    }
  }
  ```
- Si hay adjuntos de tipo `application/pdf` o texto, el bridge debería haber hecho OCR o simplemente adjuntar la descripción como texto adicional en el `message`.

**Restricciones:**
- Solo soportar imágenes (`image/jpeg`, `image/png`) en el MVP. PDFs quedan como texto extraído.
- No modificar la lógica de triage ni de tool-loop.

### 4. `backend/plugins/cmf.py` — Extender intenciones de reclamo

**Qué cambiar:**
- Agregar sub-intenciones en `INTENCIONES_CMF`:
  ```python
  "RECLAMO_PRODUCTO": IntencionDef(
      nombre="RECLAMO_PRODUCTO",
      descripcion="Problemas con productos financieros: cobros indebidos, cargos no reconocidos, tarjetas de crédito, cuentas corrientes."
  ),
  "RECLAMO_SERVICIO": IntencionDef(
      nombre="RECLAMO_SERVICIO",
      descripcion="Problemas con servicios: negativa de pago de seguros, malas prácticas de cobranza, incumplimiento de póliza."
  ),
  "RECLAMO_INFORMACION": IntencionDef(
      nombre="RECLAMO_INFORMACION",
      descripcion="Falta de información, publicidad engañosa, términos no explicados, documentación incompleta."
  ),
  ```
- Extender `PROMPT_FRAGMENT_CMF` para mencionar las nuevas sub-intenciones y dar ejemplos.
- Las tools `buscar_servicios_cmf` y `obtener_detalle_servicio_cmf` **no cambian**.

### 5. `backend/prompt/pipeline.py` — Fragmento de reclamos CMF

**Qué cambiar:**
- Agregar nueva `PromptSection` opcional `ReclamoCMFSection` que se incluye cuando el plugin CMF detecta una intención de reclamo.
- Contenido sugerido:
  ```
  Cuando el usuario esté formalizando un reclamo CMF, debes:
  1. Identificar el tipo de entidad (banco, AFP, aseguradora, mutuaria, corredora).
  2. Preguntar o verificar si ya reclamó directamente a la entidad (prerequisito CMF).
  3. Preguntar o verificar plazos transcurridos.
  4. Cruzar con normativa: Ley 19.496 (Protección al Consumidor), circulares CMF, DFL 3.
  5. Indicar canal correcto: entidad directa → CMF Online → SERNAC (si aplica) → tribunales.
  6. Nunca inventar URLs. Solo usar URLs presentes en los servicios curados.
  ```

**Restricciones:**
- No modificar `CoreIdentitySection` ni `OrganismosSection`.
- La nueva sección debe ser condicional (solo si la intención es RECLAMO*).

### 6. `data/cmf/reclamos_casos.json` — Nuevo archivo (datos de ejemplo)

**Qué crear:**
- JSON con casos típicos de reclamos para enriquecer el RAG o servir de ejemplos en prompts:
  ```json
  [
    {
      "id": "reclamo-cobro-indebido-tarjeta",
      "titulo": "Cobro indebido en tarjeta de crédito",
      "descripcion": "El banco cobró un cargo que no reconozco en mi estado de cuenta.",
      "entidad_tipo": "banco",
      "intencion": "RECLAMO_PRODUCTO",
      "normativa_relacionada": ["Ley 19.496 Art. 14", "Circular CMF N°..."],
      "pasos_recomendados": [
        "Reclamar directamente al banco por escrito",
        "Si no responden en 10 días hábiles, acudir a CMF Online",
        "Adjuntar estado de cuenta y comprobante de pago"
      ]
    }
  ]
  ```
- Estos datos pueden ser ingestados en ChromaDB o simplemente usados en few-shot prompts.

## Archivos de SOLO LECTURA (NO tocar)

| Archivo | Por qué |
|---|---|
| `backend/core/models.py` | Tipos base. Si necesitas algo nuevo, extiende, no modifiques existentes. |
| `backend/core/plugin.py` | Protocolo `OrganismoPlugin`. No cambiar la interfaz. |
| `backend/registry.py` | Lógica de descubrimiento de plugins. Agrega tu plugin al listado si creas uno nuevo, pero no toques el mecanismo. |
| `backend/services/model_router.py` | Lógica de cascada Haiku→Sonnet→Opus. Está bien. |
| `backend/services/rate_limiter.py` | Rate limiting en 5 scopes. No tocar. |
| `backend/services/cost_tracker.py` | Tracking de costos. No tocar. |
| `backend/vector_store.py` | ChromaDB abstraction. No tocar salvo que necesites nueva colección. |
| `backend/settings.py` | Agrega nuevas settings al final si es necesario, pero no modificar existentes. |

## Tests a mantener

- Correr `pytest` antes y después de cada cambio. Todos los tests existentes (185) deben seguir pasando.
- Si agregas un test nuevo para attachments, colocarlo en `tests/unit/test_schemas.py` o crear `tests/unit/test_attachments.py`.

## Checklist de entrega

- [ ] `POST /chat` acepta `attachments: null` (comportamiento anterior).
- [ ] `POST /chat` acepta `attachments: [...]` con imágenes.
- [ ] Plugin CMF detecta `RECLAMO_PRODUCTO`, `RECLAMO_SERVICIO`, `RECLAMO_INFORMACION`.
- [ ] Todos los tests existentes pasan.
- [ ] `GET /health` responde 200.

## Comandos de verificación

```bash
# Quality gate completo
./check.ps1

# Solo tests
pytest -q

# Verificar que el backend levanta
uvicorn main:app --reload
# En otra terminal:
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"tengo un cobro indebido en mi tarjeta"}'
```
