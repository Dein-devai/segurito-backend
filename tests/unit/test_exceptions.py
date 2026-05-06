"""Tests para backend.core.exceptions."""
from __future__ import annotations

import pytest

from backend.core.exceptions import (
    ConfigurationError,
    IntencionInvalidaError,
    LLMError,
    OrganismoNotFoundError,
    SeguritoError,
    ToolExecutionError,
    ToolLoopMaxIterationsError,
    ToolLoopTimeoutError,
)


def test_all_exceptions_inherit_from_segurito_error() -> None:
    """Todas las excepciones del dominio derivan de SeguritoError.

    Esto permite a un handler genérico capturarlas todas con un solo
    `except SeguritoError`.
    """
    for exc_cls in (
        ConfigurationError,
        OrganismoNotFoundError,
        IntencionInvalidaError,
        ToolExecutionError,
        LLMError,
        ToolLoopTimeoutError,
        ToolLoopMaxIterationsError,
    ):
        assert issubclass(exc_cls, SeguritoError)


def test_organismo_not_found_carries_key() -> None:
    err = OrganismoNotFoundError("sernac")
    assert err.key == "sernac"
    assert "sernac" in str(err)


def test_intencion_invalida_carries_context() -> None:
    err = IntencionInvalidaError("FOO", ("RECLAMO", "CONSULTA"))
    assert err.intencion == "FOO"
    assert err.validas == ("RECLAMO", "CONSULTA")
    assert "FOO" in str(err)
    assert "RECLAMO" in str(err)


def test_tool_execution_error_carries_tool_name_and_reason() -> None:
    err = ToolExecutionError("buscar_servicios", "timeout")
    assert err.tool_name == "buscar_servicios"
    assert err.reason == "timeout"
    assert "buscar_servicios" in str(err)


def test_segurito_error_is_an_exception() -> None:
    """Catchable como Exception base."""
    with pytest.raises(Exception):
        raise SeguritoError("boom")
