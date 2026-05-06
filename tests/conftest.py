"""Pytest fixtures globales."""
from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[None]:
    """Aísla variables de entorno y paths de cada test.

    Evita que los tests dependan del .env real o del filesystem del repo.
    """
    # Limpia env vars que la app lee
    for var in (
        "ANTHROPIC_API_KEY",
        "SEGURITO_MODEL_CHAT",
        "SEGURITO_MAX_TOOL_ITERATIONS",
        "SEGURITO_TOOL_LOOP_TIMEOUT",
        "SEGURITO_MAX_USER_INPUT",
        "SEGURITO_DATA_DIR",
        "SEGURITO_CHROMA_PATH",
        "SEGURITO_LOG_PATH",
        "SEGURITO_DB_PATH",
        "SEGURITO_ENABLED_ORGANISMOS",
        "SEGURITO_CORS_ORIGINS",
        "SEGURITO_MCP_HOST",
        "SEGURITO_MCP_PORT",
        "SEGURITO_ENABLE_TRIAGE",
        "SEGURITO_ENABLE_PROMPT_CACHE",
        "SEGURITO_ALLOW_MODEL_OVERRIDE",
    ):
        monkeypatch.delenv(var, raising=False)

    # Setea defaults seguros para tests
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SEGURITO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SEGURITO_CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("SEGURITO_LOG_PATH", str(tmp_path / "interaction_log.jsonl"))
    monkeypatch.setenv("SEGURITO_DB_PATH", str(tmp_path / "segurito.db"))
    # Tests legacy del ChatService asumen 1 llamada por turno: triage off por
    # defecto y prompt cache off. Tests de cascada los activan explícitamente.
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "false")
    monkeypatch.setenv("SEGURITO_ENABLE_PROMPT_CACHE", "false")

    # Limpia singleton de settings
    from backend.settings import get_settings
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest.fixture
def fresh_settings():
    """Obtiene una instancia limpia de Settings respetando el env actual."""
    from backend.settings import get_settings
    get_settings.cache_clear()
    return get_settings()
