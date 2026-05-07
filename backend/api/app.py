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
    registry = get_registry_dep()
    get_repository_dep()
    _ensure_collections_ingested(registry)
    yield
    log.info("stopping Segurito API")


def _ensure_collections_ingested(registry) -> None:
    """Llama a ``plugin.ingest_data()`` para poblar colecciones vacías.

    Se ejecuta al startup. Si el plugin no usa RAG el hook devuelve None y
    no hace nada. Si la colección ya tiene datos, también es no-op.
    """
    for plugin in registry.all_plugins():
        try:
            count = plugin.ingest_data()
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "ingest_data falló para plugin %s: %s", plugin.key, exc,
            )
            continue
        if count is not None:
            log.info("plugin %s collection size=%d", plugin.key, count)


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
    cors_origins = list(settings.cors_origins)
    cors_origin_regex = settings.cors_origin_regex.strip() or None
    if cors_origins == ["*"] and not cors_origin_regex:
        log.warning(
            "CORS abierto a *: aceptable solo en dev local. "
            "En producción configura SEGURITO_CORS_ORIGINS con dominios exactos "
            "o SEGURITO_CORS_ORIGIN_REGEX para previews dinámicos."
        )
        # Con allow_credentials=False puedes usar wildcard.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=False,
        )
    else:
        # Si solo hay regex (sin lista explícita), no usamos el wildcard como
        # lista ya que sería incompatible con allow_credentials=True.
        explicit_origins = [] if cors_origins == ["*"] else cors_origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=explicit_origins,
            allow_origin_regex=cors_origin_regex,
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True,
        )
    app.add_middleware(RateLimitMiddleware, limiter=get_rate_limiter_dep())
    app.include_router(chat_router.router, tags=["chat"])
    app.include_router(feedback_router.router, tags=["feedback"])
    app.include_router(health_router.router, tags=["meta"])
    app.include_router(admin_router.router)
    # Auth: /auth/me y /auth/logout siempre disponibles si hay JWT_SECRET.
    # /auth/google/* solo se habilita si además hay Google credentials.
    if settings.jwt_secret:
        from backend.api.routers import auth as auth_router

        app.include_router(auth_router.router, tags=["auth"])
        if not (settings.google_client_id and settings.google_client_secret):
            log.info(
                "Google OAuth deshabilitado: GOOGLE_CLIENT_ID/SECRET no configurados. "
                "/auth/me y /auth/logout funcionan con JWT existente."
            )
    else:
        log.info("auth router deshabilitado: JWT_SECRET no configurado")

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
