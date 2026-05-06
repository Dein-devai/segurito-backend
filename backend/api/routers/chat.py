"""Endpoint /chat."""
from __future__ import annotations

import anthropic
from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import (
    get_anthropic_dep,
    get_conversation_store_dep,
    get_cost_tracker_dep,
    get_pipeline_dep,
    get_rate_limiter_dep,
    get_registry_dep,
    get_repository_dep,
    get_settings_dep,
)
from backend.api.schemas import ChatRequest, ChatResponse
from backend.core.exceptions import LLMError, ToolExecutionError
from backend.logging_setup import get_logger
from backend.prompt.pipeline import PromptPipeline
from backend.registry import PluginRegistry
from backend.repository import InteractionRepository
from backend.services.chat_service import ChatService
from backend.services.conversation_store import ConversationStore
from backend.services.cost_tracker import CostTracker
from backend.services.rate_limiter import RateLimiter, RateLimitExceeded
from backend.settings import Settings

log = get_logger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    client: anthropic.Anthropic = Depends(get_anthropic_dep),
    registry: PluginRegistry = Depends(get_registry_dep),
    settings: Settings = Depends(get_settings_dep),
    pipeline: PromptPipeline = Depends(get_pipeline_dep),
    conversations: ConversationStore = Depends(get_conversation_store_dep),
    repo: InteractionRepository = Depends(get_repository_dep),
    limiter: RateLimiter = Depends(get_rate_limiter_dep),
    cost_tracker: CostTracker = Depends(get_cost_tracker_dep),
) -> ChatResponse:
    if len(req.message) > settings.max_user_input_chars:
        raise HTTPException(
            status_code=400,
            detail=f"message excede {settings.max_user_input_chars} chars",
        )

    # Rate limit por conversación si el cliente la trae explícita.
    if req.conversation_id:
        try:
            limiter.check_conversation(req.conversation_id)
        except RateLimitExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail={
                    "scope": exc.scope,
                    "retry_after_s": int(exc.retry_after_s),
                },
                headers={"Retry-After": str(max(1, int(exc.retry_after_s)))},
            ) from exc

    # Budget USD: si ya superamos, cortamos al toque.
    if cost_tracker.would_exceed(0.0):
        raise HTTPException(
            status_code=429,
            detail="cost budget diario excedido",
            headers={"Retry-After": "3600"},
        )

    service = ChatService(
        client=client,
        registry=registry,
        settings=settings,
        pipeline=pipeline,
        conversations=conversations,
        rate_limiter=limiter,
        cost_tracker=cost_tracker,
    )

    # Validar attachments
    attachments = req.attachments
    if attachments:
        if len(attachments) > 3:
            raise HTTPException(
                status_code=400,
                detail="Máximo 3 adjuntos por mensaje.",
            )
        for att in attachments:
            size_bytes = len(att.base64_data) * 3 // 4
            if size_bytes > 5 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"Adjunto '{att.filename}' excede 5MB.",
                )

    try:
        result = service.chat(
            req.message,
            conversation_id=req.conversation_id,
            attachments=[
                {"mime_type": a.mime_type, "base64_data": a.base64_data}
                for a in (attachments or [])
            ],
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={"scope": exc.scope, "retry_after_s": int(exc.retry_after_s)},
            headers={"Retry-After": str(max(1, int(exc.retry_after_s)))},
        ) from exc
    except LLMError as exc:
        log.exception("LLM error")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ToolExecutionError as exc:
        log.exception("tool execution error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    repo.save_interaction(
        interaction_id=result.interaction_id,
        conversation_id=result.conversation_id,
        user_message=req.message,
        response=result.response,
        organismo=result.organismo_detectado,
        intencion=result.intencion,
        servicio_id=result.servicio_id,
        iterations=result.iterations,
        elapsed_ms=result.elapsed_ms,
        tools_used=[t.model_dump() for t in result.tools_used],
    )
    return result
