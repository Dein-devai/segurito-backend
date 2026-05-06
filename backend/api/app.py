"""Factory de FastAPI.

`main.py` queda reducido a un único `app = create_app()`. Esto permite tests
de integración con `TestClient(create_app())` sin acoplarse a globals.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.dependencies import (
    get_rate_limiter_dep,
    get_registry_dep,
    get_repository_dep,
    get_settings_dep,
)
from backend.api.middleware.rate_limit import RateLimitMiddleware
from backend.api.routers import chat as chat_router
from backend.api.routers import feedback as feedback_router
from backend.api.routers import health as health_router
from backend.logging_setup import configure_logging, get_logger
from backend.settings import Settings

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    settings = get_settings_dep()
    configure_logging(settings.log_level)
    log.info("starting Segurito API")
    get_registry_dep()
    get_repository_dep()
    yield
    log.info("stopping Segurito API")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings_dep()
    app = FastAPI(
        title="Segurito API",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, limiter=get_rate_limiter_dep())
    app.include_router(chat_router.router, tags=["chat"])
    app.include_router(feedback_router.router, tags=["feedback"])
    app.include_router(health_router.router, tags=["meta"])
    return app
