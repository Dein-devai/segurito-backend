"""Modelos Pydantic de la API (request/response)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    mime_type: str = Field(..., description="Tipo MIME del archivo, ej. image/jpeg")
    filename: str = Field(..., description="Nombre del archivo original")
    base64_data: str = Field(..., description="Contenido del archivo en base64")
    description: str | None = Field(
        default=None,
        description="Texto extraído del archivo (OCR, descripción).",
    )


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = Field(
        default=None,
        description="Si se omite, el servidor genera uno nuevo (CONSULTA multi-turno).",
    )
    session_id: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "Identificador estable de cliente web (UUID v4 en localStorage). "
            "Se usa para rate-limit y correlación cuando el usuario es anónimo."
        ),
    )
    attachments: list[Attachment] | None = Field(
        default=None,
        description="Archivos adjuntos opcionales (imágenes, documentos).",
    )


class ToolTrace(BaseModel):
    name: str
    input: dict


class ReasoningStep(BaseModel):
    """Una llamada al LLM dentro del turno (triage, default o escalation).

    Permite auditar la cascada Haiku → Sonnet → Opus: qué modelo se usó en
    cada fase, cuánto pensó, cuántos tokens consumió y por qué se eligió.
    """

    model: str
    phase: str  # triage | default | escalation | override
    reason: str
    thinking: str | None = None
    elapsed_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0


class ChatResponse(BaseModel):
    interaction_id: str
    conversation_id: str
    response: str
    organismo_detectado: str | None = None
    intencion: str | None = None
    servicio_id: str | None = None
    servicios_encontrados: list[str] = []
    requiere_confirmacion: bool = False
    tools_used: list[ToolTrace] = []
    iterations: int = 0
    elapsed_ms: int = 0
    # --- FM3: cascada multi-modelo ----------------------------------------
    reasoning: list[ReasoningStep] = []
    model_used_final: str | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cost_usd: float = 0.0


class FeedbackRequest(BaseModel):
    interaction_id: str
    helpful: bool
    comment: str | None = None


class FeedbackResponse(BaseModel):
    ok: bool
    interaction_id: str


class HealthResponse(BaseModel):
    status: str
    model: str
    organismos: list[str]
    prompt_version: str


class MetricsResponse(BaseModel):
    total_interactions: int
    by_organismo: dict[str, int]
    by_intencion: dict[str, int]
    feedback_helpful_rate: float | None
