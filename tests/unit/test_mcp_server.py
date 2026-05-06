"""Tests para backend.mcp_server — registry y pipeline como source of truth."""
from __future__ import annotations

import asyncio

import pytest

from backend.bootstrap import build_registry
from backend.mcp_server import build_mcp_app
from backend.prompt.pipeline import PROMPT_VERSION
from backend.registry import PluginRegistry
from backend.settings import Settings


@pytest.fixture
def registry_cmf(monkeypatch: pytest.MonkeyPatch) -> PluginRegistry:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    return build_registry(Settings())


def test_build_mcp_app_registers_tools_from_registry(
    registry_cmf: PluginRegistry,
) -> None:
    mcp = build_mcp_app(settings=Settings(), registry=registry_cmf)
    tools = asyncio.run(mcp.list_tools())
    tool_names = {t.name for t in tools}
    expected = {td.name for td in registry_cmf.all_tools()}
    assert tool_names == expected
    assert "buscar_servicios_cmf" in tool_names


def test_mcp_tools_preserve_input_schema_from_plugin(
    registry_cmf: PluginRegistry,
) -> None:
    """El schema con descripciones del ToolDef NO se debe perder en el camino."""
    mcp = build_mcp_app(settings=Settings(), registry=registry_cmf)
    tools = asyncio.run(mcp.list_tools())
    buscar = next(t for t in tools if t.name == "buscar_servicios_cmf")
    assert buscar.inputSchema["type"] == "object"
    assert "query" in buscar.inputSchema["properties"]
    assert "intencion" in buscar.inputSchema["properties"]
    # description del ToolDef preservada
    assert buscar.description and len(buscar.description) > 10


def test_mcp_prompt_es_segurito_system_prompt(
    registry_cmf: PluginRegistry,
) -> None:
    mcp = build_mcp_app(settings=Settings(), registry=registry_cmf)
    prompts = asyncio.run(mcp.list_prompts())
    names = {p.name for p in prompts}
    assert "segurito_system_prompt" in names


def test_mcp_prompt_renders_with_prompt_version(
    registry_cmf: PluginRegistry,
) -> None:
    mcp = build_mcp_app(settings=Settings(), registry=registry_cmf)
    result = asyncio.run(mcp.get_prompt("segurito_system_prompt"))
    rendered = "\n".join(
        msg.content.text  # type: ignore[union-attr]
        for msg in result.messages
        if hasattr(msg.content, "text")
    )
    assert PROMPT_VERSION in rendered
    assert "Segurito" in rendered


def test_mcp_call_tool_delegates_to_registry(
    registry_cmf: PluginRegistry,
) -> None:
    """Llamar la tool por MCP debe ejecutar el handler del plugin."""
    cmf = registry_cmf.get("cmf")
    assert cmf is not None
    captured: dict[str, object] = {}

    def spy(args: dict) -> str:
        captured.update(args)
        return "OK_SPY"

    # Sobrescribimos tool_handlers del plugin: el registry los lee fresh cada vez.
    cmf.tool_handlers = lambda: {  # type: ignore[method-assign]
        "buscar_servicios_cmf": spy,
        "obtener_detalle_servicio_cmf": spy,
    }

    mcp = build_mcp_app(settings=Settings(), registry=registry_cmf)
    result = asyncio.run(
        mcp.call_tool(
            "buscar_servicios_cmf",
            {"query": "reclamo banco", "intencion": "RECLAMO"},
        )
    )
    text = str(result)
    assert "OK_SPY" in text
    assert captured["query"] == "reclamo banco"
    assert captured["intencion"] == "RECLAMO"


def test_mcp_app_registers_multiple_organismos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si activamos SERNAC además de CMF, las tools de ambos deberían aparecer."""
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf", "sernac"]')
    settings = Settings()
    registry = build_registry(settings)
    mcp = build_mcp_app(settings=settings, registry=registry)
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    # CMF tiene 2 tools, SERNAC stub no tiene tools — total 2.
    assert "buscar_servicios_cmf" in names
    assert "obtener_detalle_servicio_cmf" in names
