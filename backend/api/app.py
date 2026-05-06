"""Factory de FastAPI.

`main.py` queda reducido a un único `app = create_app()`. Esto permite tests
de integración con `TestClient(create_app())` sin acoplarse a globals.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.dependencies import (
    get_rate_limiter_dep,
    get_registry_dep,
    get_repository_dep,
    get_settings_dep,
)
from backend.api.middleware.rate_limit import RateLimitMiddleware
from backend.api.routers import admin as admin_router
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
    _warn_if_public_bind()
    get_registry_dep()
    get_repository_dep()
    yield
    log.info("stopping Segurito API")


def _warn_if_public_bind() -> None:
    """Avisa si uvicorn fue lanzado con bind público (0.0.0.0).

    El dashboard expone datos sensibles (mensajes de usuario, costos). En
    operación local debe correr en 127.0.0.1. Se detecta inspeccionando los
    args del proceso porque uvicorn no expone el host al app desde lifespan.
    """
    import sys

    argv = " ".join(sys.argv).lower()
    if "0.0.0.0" in argv or "--host *" in argv:
        log.warning(
            "uvicorn está bindeado a un host público (0.0.0.0). "
            "El dashboard /admin expone datos sensibles. "
            "Usa --host 127.0.0.1 salvo que sepas lo que haces."
        )


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
    app.include_router(admin_router.router)

    # Dashboard estático (logs-ui). Servido bajo /admin/ui para que el JS
    # pueda usar URLs relativas hacia /admin/* y evitar CORS.
    from pathlib import Path

    ui_dir = Path(__file__).resolve().parents[2] / "logs-ui"
    if ui_dir.is_dir():
        app.mount(
            "/admin/ui",
            StaticFiles(directory=ui_dir, html=True),
            name="admin-ui",
        )

    return app
