"""Endpoints /health y /metrics."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import (
    get_registry_dep,
    get_repository_dep,
    get_settings_dep,
)
from backend.api.schemas import HealthResponse, MetricsResponse
from backend.prompt.pipeline import PROMPT_VERSION
from backend.registry import PluginRegistry
from backend.repository import InteractionRepository
from backend.settings import Settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(
    registry: PluginRegistry = Depends(get_registry_dep),
    settings: Settings = Depends(get_settings_dep),
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=settings.model_chat,
        organismos=list(registry.keys()),
        prompt_version=PROMPT_VERSION,
    )


@router.get("/metrics", response_model=MetricsResponse)
def metrics(
    repo: InteractionRepository = Depends(get_repository_dep),
) -> MetricsResponse:
    data = repo.metrics()
    return MetricsResponse(**data)
