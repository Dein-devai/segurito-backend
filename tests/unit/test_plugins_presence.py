"""Tests SERNAC/SII presence-only — sin tools, sólo prompt fragment."""
from __future__ import annotations

from backend.plugins.sernac import SernacPlugin
from backend.plugins.sii import SiiPlugin


def test_sernac_no_expone_tools() -> None:
    p = SernacPlugin()
    assert p.key == "sernac"
    assert p.activo is True
    assert p.tools() == []
    assert p.tool_handlers() == {}
    assert p.intenciones() == {}


def test_sernac_prompt_fragment_menciona_canales_publicos() -> None:
    fragment = SernacPlugin().prompt_fragment()
    assert "SERNAC" in fragment
    # Canales públicos verificables sin sesión.
    assert "800 700 100" in fragment
    assert "sernac.cl" in fragment
    # Honestidad sobre la barrera ClaveÚnica.
    assert "ClaveÚnica" in fragment


def test_sernac_prompt_fragment_remite_a_marco_legal() -> None:
    assert "consultar_marco_legal" in SernacPlugin().prompt_fragment()


def test_sii_no_expone_tools() -> None:
    p = SiiPlugin()
    assert p.key == "sii"
    assert p.activo is True
    assert p.tools() == []
    assert p.tool_handlers() == {}
    assert p.intenciones() == {}


def test_sii_prompt_fragment_menciona_canales_publicos() -> None:
    fragment = SiiPlugin().prompt_fragment()
    assert "SII" in fragment
    assert "sii.cl" in fragment
    assert "ChileAtiende" in fragment
    assert "ClaveTributaria" in fragment or "ClaveÚnica" in fragment


def test_sii_prompt_fragment_remite_a_marco_legal() -> None:
    assert "consultar_marco_legal" in SiiPlugin().prompt_fragment()
