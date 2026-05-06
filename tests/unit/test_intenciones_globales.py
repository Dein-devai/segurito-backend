"""Tests para backend.core.intenciones_globales."""
from __future__ import annotations

from backend.core.intenciones_globales import (
    ALERTA,
    INTENCIONES_GLOBALES,
    OUT_OF_SCOPE,
)


def test_alerta_no_usa_rag() -> None:
    assert ALERTA.usa_rag is False
    assert ALERTA.respuesta_fija is not None


def test_out_of_scope_no_usa_rag() -> None:
    assert OUT_OF_SCOPE.usa_rag is False
    assert OUT_OF_SCOPE.respuesta_fija is not None


def test_intenciones_globales_contiene_ambas() -> None:
    assert "ALERTA" in INTENCIONES_GLOBALES
    assert "OUT_OF_SCOPE" in INTENCIONES_GLOBALES
    assert len(INTENCIONES_GLOBALES) == 2
