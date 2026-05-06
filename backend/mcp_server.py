"""Servidor MCP — fuente de verdad para tools y prompts de Segurito.

Diseño:
- Las tools provienen del `PluginRegistry` (cada plugin define `ToolDef` +
  handler, ESA es la fuente de verdad de schemas).
- El system prompt proviene del `PromptPipeline`.
- FastAPI consumirá las MISMAS tool functions en F5 a través del registry,
  no se duplica nada.

Transports soportados: stdio (default) y streamable-http.
"""
from __future__ import annotations

import argparse
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import Prompt
from mcp.server.fastmcp.tools.base import Tool
from mcp.server.fastmcp.utilities.func_metadata import func_metadata

from backend.bootstrap import build_registry
from backend.logging_setup import configure_logging, get_logger
from backend.prompt.pipeline import PROMPT_VERSION, PromptPipeline
from backend.registry import PluginRegistry
from backend.settings import Settings, get_settings

log = get_logger(__name__)

MCP_NAME = "segurito"
MCP_INSTRUCTIONS = (
    "Servidor MCP de Segurito: orienta a ciudadanos chilenos sobre servicios "
    "de organismos del Estado. Expone tools por organismo y un prompt de sistema "
    "versionado."
)


class _RegistryDelegatingTool(Tool):
    """Tool MCP que delega en `PluginRegistry.execute_tool`.

    Reemplaza `Tool.run` para evitar que `func_metadata` valide la signatura
    Python (un wrapper `**kwargs` no concuerda con el JSON Schema declarado);
    confiamos en el `input_schema` del plugin como contrato y la validación
    semántica que cada handler hace al recibir los args.
    """

    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    async def run(
        self,
        arguments: dict[str, Any],
        context: Any | None = None,
        convert_result: bool = False,
    ) -> Any:
        assert self.meta is not None  # noqa: S101 — invariante de construcción
        registry: PluginRegistry = self.meta["registry"]
        return registry.execute_tool(self.name, arguments)


def _build_tool(registry: PluginRegistry, tool_def: Any) -> Tool:
    """Construye un Tool MCP a partir de un `ToolDef` del plugin."""
    async def placeholder() -> str:  # nunca se llama; run() está override
        raise NotImplementedError

    return _RegistryDelegatingTool(
        fn=placeholder,
        name=tool_def.name,
        title=None,
        description=tool_def.description,
        parameters=tool_def.input_schema,
        fn_metadata=func_metadata(placeholder),
        is_async=True,
        context_kwarg=None,
        annotations=None,
        meta={"registry": registry},
    )


def _register_tools(mcp: FastMCP, registry: PluginRegistry) -> None:
    """Inserta tools manualmente con el `input_schema` del ToolDef como source.

    No usamos `@mcp.tool()` porque eso regenera el schema desde la signatura
    Python; nosotros queremos preservar el JSON Schema con descripciones que
    el plugin definió.
    """
    for tool_def in registry.all_tools():
        tool = _build_tool(registry, tool_def)
        mcp._tool_manager._tools[tool.name] = tool
        log.info("registered MCP tool: %s", tool.name)


def _register_prompts(mcp: FastMCP, registry: PluginRegistry) -> None:
    """Expone el system prompt del pipeline como prompt MCP."""
    pipeline = PromptPipeline()

    def _system_prompt() -> str:
        return pipeline.build(registry)

    prompt = Prompt.from_function(
        _system_prompt,
        name="segurito_system_prompt",
        title=f"Segurito system prompt ({PROMPT_VERSION})",
        description=(
            "System prompt completo de Segurito, generado dinámicamente desde "
            "los plugins activos del registry."
        ),
    )
    mcp.add_prompt(prompt)
    log.info("registered MCP prompt: segurito_system_prompt")


def build_mcp_app(
    settings: Settings | None = None,
    registry: PluginRegistry | None = None,
) -> FastMCP:
    """Construye el server MCP listo para `.run(transport=...)`."""
    settings = settings or get_settings()
    registry = registry or build_registry(settings)

    mcp = FastMCP(
        name=MCP_NAME,
        instructions=MCP_INSTRUCTIONS,
        host=settings.mcp_host,
        port=settings.mcp_port,
    )
    _register_tools(mcp, registry)
    _register_prompts(mcp, registry)
    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="segurito-mcp")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="Transport MCP. stdio para Claude Desktop, streamable-http para red.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    mcp = build_mcp_app(settings)
    log.info(
        "starting MCP server transport=%s host=%s port=%s",
        args.transport,
        settings.mcp_host,
        settings.mcp_port,
    )
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
