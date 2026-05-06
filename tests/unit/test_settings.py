"""Tests para backend.settings."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_settings_loads_with_defaults(fresh_settings) -> None:
    """Settings se construye con defaults si no hay env vars custom."""
    assert fresh_settings.anthropic_api_key == "test-key"
    assert fresh_settings.model_chat == "claude-sonnet-4-5"
    assert fresh_settings.max_tool_iterations == 5
    assert fresh_settings.tool_loop_timeout_s == 30.0
    assert fresh_settings.embed_model_name == "paraphrase-multilingual-MiniLM-L12-v2"


def test_settings_reads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings lee variables de entorno con prefijo SEGURITO_."""
    monkeypatch.setenv("SEGURITO_MODEL_CHAT", "claude-haiku-4-5")
    monkeypatch.setenv("SEGURITO_MAX_TOOL_ITERATIONS", "8")

    from backend.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()

    assert s.model_chat == "claude-haiku-4-5"
    assert s.max_tool_iterations == 8


def test_settings_paths_are_path_objects(fresh_settings) -> None:
    """Paths se materializan como Path, no string."""
    assert isinstance(fresh_settings.data_dir, Path)
    assert isinstance(fresh_settings.chroma_db_path, Path)
    assert isinstance(fresh_settings.log_path, Path)


def test_settings_singleton_caches(fresh_settings) -> None:
    """get_settings devuelve la misma instancia hasta que se invalida cache."""
    from backend.settings import get_settings

    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

    get_settings.cache_clear()
    s3 = get_settings()
    assert s3 is not s1


def test_enabled_organismos_default_is_cmf(fresh_settings) -> None:
    """Por defecto solo CMF está activo."""
    assert "cmf" in fresh_settings.enabled_organismos


def test_settings_ignores_unknown_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Variables no declaradas no rompen la inicialización."""
    monkeypatch.setenv("SEGURITO_THIS_DOES_NOT_EXIST", "xx")

    from backend.settings import get_settings
    get_settings.cache_clear()

    # No debe lanzar
    s = get_settings()
    assert s.model_chat == "claude-sonnet-4-5"


def test_multi_model_cascade_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """FM1: cascada Haiku → Sonnet → Opus con defaults sensatos.

    Limpia overrides del autouse fixture para validar defaults de la clase.
    """
    monkeypatch.delenv("SEGURITO_ENABLE_TRIAGE", raising=False)
    monkeypatch.delenv("SEGURITO_ENABLE_PROMPT_CACHE", raising=False)
    monkeypatch.delenv("SEGURITO_ALLOW_MODEL_OVERRIDE", raising=False)

    from backend.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()

    assert s.model_triage == "claude-haiku-4-5"
    assert s.model_default == "claude-sonnet-4-5"
    assert s.model_escalation == "claude-opus-4-6"
    assert s.thinking_budget_tokens == 2048
    assert s.allow_model_override is False
    assert s.enable_prompt_cache is True
    assert s.enable_triage is True
    assert isinstance(s.escalation_keywords, tuple)
    assert any("demanda" in k for k in s.escalation_keywords)


def test_multi_model_cascade_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """FM1: alias por modelo permite override individual."""
    monkeypatch.setenv("SEGURITO_MODEL_TRIAGE", "claude-haiku-future")
    monkeypatch.setenv("SEGURITO_MODEL_ESCALATION", "claude-opus-future")
    monkeypatch.setenv("SEGURITO_THINKING_BUDGET", "4096")
    monkeypatch.setenv("SEGURITO_ALLOW_MODEL_OVERRIDE", "true")

    from backend.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()

    assert s.model_triage == "claude-haiku-future"
    assert s.model_escalation == "claude-opus-future"
    assert s.thinking_budget_tokens == 4096
    assert s.allow_model_override is True


def test_rate_limits_defaults(fresh_settings) -> None:
    """FM1: rate limits transversales con defaults razonables."""
    assert fresh_settings.rate_limit_per_ip_per_min == 60
    assert fresh_settings.rate_limit_per_ip_per_day == 1000
    assert fresh_settings.rate_limit_per_conversation_turns == 30
    assert fresh_settings.rate_limit_per_conversation_per_hour == 120
    assert fresh_settings.rate_limit_sonnet_per_min == 40
    assert fresh_settings.rate_limit_opus_per_min_global == 10
    assert fresh_settings.rate_limit_opus_per_conversation == 5
    assert fresh_settings.cost_budget_usd_per_day == 10.0


def test_rate_limits_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEGURITO_RL_OPUS_MIN_GLOBAL", "3")
    monkeypatch.setenv("SEGURITO_COST_BUDGET_DAY_USD", "25.5")

    from backend.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()

    assert s.rate_limit_opus_per_min_global == 3
    assert s.cost_budget_usd_per_day == 25.5
