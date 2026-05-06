"""Tests para backend.registry — usa plugins fake.

Estos tests validan que el contrato OrganismoPlugin es testeable sin
ningún dependency real (Chroma, Anthropic, archivos JSON). Si en el futuro
testear un plugin se vuelve "difícil", es señal de que el contrato está mal.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.exceptions import (
    OrganismoNotFoundError,
    SeguritoError,
    ToolExecutionError,
)
from backend.core.models import IntencionDef, ServiceItem, ToolDef
from backend.core.plugin import OrganismoPlugin, ToolHandler
from backend.registry import PluginRegistry


def _make_fake_plugin(
    key: str = "fake",
    activo: bool = True,
    extra_tool: bool = False,
    intenciones_extra: dict[str, IntencionDef] | None = None,
    handler_breaks: bool = False,
) -> OrganismoPlugin:
    """Fábrica de plugin fake parametrizable."""

    class _Fake(OrganismoPlugin):
        def __init__(self) -> None:
            self.key = key
            self.nombre = f"Fake {key}"
            self.data_path = Path("/tmp/none.json")
            self.collection_name = f"{key}_test"
            self.activo = activo

        def intenciones(self) -> dict[str, IntencionDef]:
            base = {
                "RECLAMO": IntencionDef(nombre="RECLAMO", descripcion="r"),
            }
            if intenciones_extra:
                base.update(intenciones_extra)
            return base

        def tools(self) -> list[ToolDef]:
            tools = [
                ToolDef(
                    name=f"buscar_{key}",
                    description="d",
                    input_schema={"type": "object", "properties": {}},
                ),
            ]
            if extra_tool:
                tools.append(
                    ToolDef(
                        name=f"extra_{key}",
                        description="d2",
                        input_schema={"type": "object", "properties": {}},
                    )
                )
            return tools

        def tool_handlers(self) -> dict[str, ToolHandler]:
            def _h(args: dict) -> str:
                if handler_breaks:
                    raise RuntimeError("boom")
                return f"resultado para {args!r}"

            handlers: dict[str, ToolHandler] = {f"buscar_{key}": _h}
            if extra_tool:
                handlers[f"extra_{key}"] = _h
            return handlers

        def prompt_fragment(self) -> str:
            return f"Fragmento de {key}"

        def format_service(self, item: ServiceItem) -> str:
            return f"### {item.id}"

    return _Fake()


def test_registry_starts_empty() -> None:
    r = PluginRegistry()
    assert len(r) == 0
    assert r.keys() == ()


def test_register_active_plugin() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="cmf"))
    assert "cmf" in r
    assert len(r) == 1
    assert r.get("cmf").key == "cmf"


def test_register_inactive_plugin_is_skipped() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="sii", activo=False))
    assert len(r) == 0
    assert "sii" not in r


def test_register_duplicate_key_raises() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="cmf"))
    with pytest.raises(SeguritoError, match="ya registrado"):
        r.register(_make_fake_plugin(key="cmf"))


def test_register_with_mismatched_tools_and_handlers_raises() -> None:
    """Si tools() y tool_handlers() no coinciden, falla al registrar."""
    bad = _make_fake_plugin(key="bad")
    # Inyectamos un handler que no corresponde a ninguna tool
    bad.tool_handlers = lambda: {"otro_nombre": lambda a: "x"}  # type: ignore[method-assign]

    r = PluginRegistry()
    with pytest.raises(SeguritoError, match="no coinciden"):
        r.register(bad)


def test_register_intencion_colliding_with_global_raises() -> None:
    r = PluginRegistry()
    plugin = _make_fake_plugin(
        key="cmf",
        intenciones_extra={
            "ALERTA": IntencionDef(nombre="ALERTA", descripcion="x"),
        },
    )
    with pytest.raises(SeguritoError, match="colisiona con global"):
        r.register(plugin)


def test_get_unknown_raises_organismo_not_found() -> None:
    r = PluginRegistry()
    with pytest.raises(OrganismoNotFoundError):
        r.get("inexistente")


def test_all_tools_aggregates_from_all_plugins() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="cmf"))
    r.register(_make_fake_plugin(key="sernac", extra_tool=True))

    names = sorted(t.name for t in r.all_tools())
    assert names == ["buscar_cmf", "buscar_sernac", "extra_sernac"]


def test_all_tool_handlers_aggregates() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="cmf"))
    r.register(_make_fake_plugin(key="sernac"))
    handlers = r.all_tool_handlers()
    assert set(handlers.keys()) == {"buscar_cmf", "buscar_sernac"}


def test_all_tool_handlers_detects_collision() -> None:
    """Si dos plugins exponen la misma tool, se detecta al agregar."""
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="a"))
    p2 = _make_fake_plugin(key="b")
    # Forzamos que p2 use el mismo nombre que p1
    p2.tools = lambda: [  # type: ignore[method-assign]
        ToolDef(
            name="buscar_a",
            description="d",
            input_schema={"type": "object", "properties": {}},
        )
    ]
    p2.tool_handlers = lambda: {"buscar_a": lambda a: "x"}  # type: ignore[method-assign]
    r.register(p2)

    with pytest.raises(SeguritoError, match="duplicada"):
        r.all_tool_handlers()


def test_all_intenciones_includes_globals_and_plugins() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="cmf"))
    intenciones = r.all_intenciones()
    assert "ALERTA" in intenciones
    assert "OUT_OF_SCOPE" in intenciones
    assert "RECLAMO" in intenciones


def test_execute_tool_dispatches_to_handler() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="cmf"))
    result = r.execute_tool("buscar_cmf", {"query": "test"})
    assert "test" in result


def test_execute_tool_unknown_raises_tool_execution_error() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="cmf"))
    with pytest.raises(ToolExecutionError, match="no registrada"):
        r.execute_tool("inexistente", {})


def test_execute_tool_wraps_handler_exception() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="cmf", handler_breaks=True))
    with pytest.raises(ToolExecutionError, match="boom"):
        r.execute_tool("buscar_cmf", {})


def test_keys_preserves_registration_order() -> None:
    r = PluginRegistry()
    r.register(_make_fake_plugin(key="cmf"))
    r.register(_make_fake_plugin(key="sernac"))
    r.register(_make_fake_plugin(key="sii"))
    assert r.keys() == ("cmf", "sernac", "sii")
