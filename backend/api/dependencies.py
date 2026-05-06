"""DI providers para FastAPI.

Cada provider devuelve un objeto singleton para todo el ciclo de vida del app
(salvo que se sobrescriba con `app.dependency_overrides[...]` en tests).
"""
from __future__ import annotations

from functools import lru_cache

import anthropic
from fastapi import Depends, Header, HTTPException, Query, status

from backend.bootstrap import build_registry
from backend.prompt.pipeline import PromptPipeline
from backend.registry import PluginRegistry
from backend.repository import InteractionRepository
from backend.services.conversation_store import ConversationStore
from backend.services.cost_tracker import CostTracker
from backend.services.rate_limiter import RateLimiter
from backend.settings import Settings, get_settings


# get_settings ya viene cacheado en backend.settings
def get_settings_dep() -> Settings:
    return get_settings()


@lru_cache(maxsize=1)
def get_registry_dep() -> PluginRegistry:
    return build_registry(get_settings())


@lru_cache(maxsize=1)
def get_pipeline_dep() -> PromptPipeline:
    return PromptPipeline()


@lru_cache(maxsize=1)
def get_conversation_store_dep() -> ConversationStore:
    return ConversationStore(ttl_seconds=get_settings().conversation_ttl_seconds)


@lru_cache(maxsize=1)
def get_repository_dep() -> InteractionRepository:
    return InteractionRepository(get_settings().db_path)


@lru_cache(maxsize=1)
def get_anthropic_dep() -> anthropic.Anthropic:
    s = get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")
    return anthropic.Anthropic(api_key=s.anthropic_api_key)


@lru_cache(maxsize=1)
def get_rate_limiter_dep() -> RateLimiter:
    return RateLimiter(get_settings())


@lru_cache(maxsize=1)
def get_cost_tracker_dep() -> CostTracker:
    return CostTracker(budget_usd_per_day=get_settings().cost_budget_usd_per_day)


def reset_dependencies() -> None:
    """Limpia caches de DI; útil tras cambiar env en tests."""
    for fn in (
        get_registry_dep,
        get_pipeline_dep,
        get_conversation_store_dep,
        get_repository_dep,
        get_anthropic_dep,
        get_rate_limiter_dep,
        get_cost_tracker_dep,
    ):
        fn.cache_clear()


def verify_admin_token(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Protege endpoints administrativos.

    Acepta el token en `Authorization: Bearer <token>` o como query
    `?token=<token>` (útil para iframes que no pueden setear headers).

    Si `ADMIN_TOKEN` está vacío, deniega todo (modo seguro por defecto).
    """
    expected = settings.admin_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin desactivado: ADMIN_TOKEN no configurado",
        )
    provided: str | None = None
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided = parts[1].strip()
    if provided is None and token:
        provided = token.strip()
    if not provided or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
