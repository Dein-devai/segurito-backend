"""Tests para backend.bootstrap — verifica que enabled_organismos arme un registry válido."""
from __future__ import annotations

import pytest

from backend.bootstrap import build_registry
from backend.core.exceptions import ConfigurationError
from backend.settings import Settings


def test_build_registry_with_only_cmf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    s = Settings()
    registry = build_registry(s)
    assert registry.keys() == ("cmf",)


def test_build_registry_with_multiple_organismos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SERNAC/SII (presence-only) y legal se activan por config."""
    monkeypatch.setenv(
        "SEGURITO_ENABLED_ORGANISMOS", '["cmf", "legal", "sernac", "sii"]'
    )
    s = Settings()
    registry = build_registry(s)
    assert set(registry.keys()) == {"cmf", "legal", "sernac", "sii"}


def test_build_registry_rejects_unknown_organismo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["foo"]')
    s = Settings()
    with pytest.raises(ConfigurationError, match="Plugin desconocido"):
        build_registry(s)


def test_registry_aggregates_tools_from_active_plugins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    s = Settings()
    registry = build_registry(s)
    tool_names = {t.name for t in registry.all_tools()}
    assert "buscar_servicios_cmf" in tool_names
    assert "obtener_detalle_servicio_cmf" in tool_names


def test_registry_includes_globals_in_intenciones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    s = Settings()
    registry = build_registry(s)
    intenciones = registry.all_intenciones()
    assert "ALERTA" in intenciones
    assert "OUT_OF_SCOPE" in intenciones
    assert "RECLAMO" in intenciones
    assert "CONSULTA" in intenciones
    assert "TRAMITE" in intenciones
