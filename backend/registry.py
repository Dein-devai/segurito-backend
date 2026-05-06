"""PluginRegistry — fuente única de verdad de los plugins activos.

Patrón: Registry. El resto del código pregunta al registry; nadie importa
plugins directamente. Esto permite:
- Cambiar el set de plugins activos por configuración.
- Validar el contrato al registrar (fail fast).
- Iterar tools/intenciones agregadas.
"""
from __future__ import annotations

from backend.core.exceptions import (
    IntencionInvalidaError,
    OrganismoNotFoundError,
    SeguritoError,
    ToolExecutionError,
)
from backend.core.intenciones_globales import INTENCIONES_GLOBALES
from backend.core.models import IntencionDef, ToolDef
from backend.core.plugin import OrganismoPlugin, ToolHandler


class PluginRegistry:
    """Contiene los plugins activos y expone vistas agregadas."""

    def __init__(self) -> None:
        self._plugins: dict[str, OrganismoPlugin] = {}

    def register(self, plugin: OrganismoPlugin) -> None:
        """Registra un plugin validando el contrato. Solo activos se exponen.

        Reglas:
        - key no puede colisionar con otro plugin.
        - tools() y tool_handlers() deben tener los mismos nombres.
        - intenciones() no puede pisar globales (ALERTA, OUT_OF_SCOPE).
        """
        if not plugin.activo:
            return

        if plugin.key in self._plugins:
            raise SeguritoError(
                f"Plugin con key={plugin.key!r} ya registrado"
            )

        tool_names = {t.name for t in plugin.tools()}
        handler_names = set(plugin.tool_handlers().keys())
        if tool_names != handler_names:
            raise SeguritoError(
                f"Plugin {plugin.key!r}: tools y handlers no coinciden. "
                f"tools={tool_names}, handlers={handler_names}"
            )

        for nombre in plugin.intenciones():
            if nombre in INTENCIONES_GLOBALES:
                raise SeguritoError(
                    f"Plugin {plugin.key!r}: intención {nombre!r} colisiona "
                    "con global"
                )

        self._plugins[plugin.key] = plugin

    def get(self, key: str) -> OrganismoPlugin:
        """Retorna el plugin por key o lanza OrganismoNotFoundError."""
        try:
            return self._plugins[key]
        except KeyError as exc:
            raise OrganismoNotFoundError(key) from exc

    def keys(self) -> tuple[str, ...]:
        """Keys de plugins activos, en orden de registro."""
        return tuple(self._plugins.keys())

    def all_plugins(self) -> tuple[OrganismoPlugin, ...]:
        return tuple(self._plugins.values())

    def all_tools(self) -> list[ToolDef]:
        """Todas las tools agregadas de todos los plugins activos."""
        out: list[ToolDef] = []
        for plugin in self._plugins.values():
            out.extend(plugin.tools())
        return out

    def all_tool_handlers(self) -> dict[str, ToolHandler]:
        """Dispatcher agregado: tool_name → handler.

        Falla si dos plugins exponen una tool con el mismo nombre.
        """
        out: dict[str, ToolHandler] = {}
        for plugin in self._plugins.values():
            for name, handler in plugin.tool_handlers().items():
                if name in out:
                    raise SeguritoError(
                        f"Tool duplicada {name!r} (plugin {plugin.key!r} "
                        "colisiona con otro)"
                    )
                out[name] = handler
        return out

    def all_intenciones(self) -> dict[str, IntencionDef]:
        """Globales + intenciones por plugin (sin colisión por contrato)."""
        merged: dict[str, IntencionDef] = dict(INTENCIONES_GLOBALES)
        for plugin in self._plugins.values():
            merged.update(plugin.intenciones())
        return merged

    def execute_tool(self, name: str, arguments: dict) -> str:
        """Despacho central de tools. Retorna markdown para el LLM."""
        handlers = self.all_tool_handlers()
        if name not in handlers:
            raise ToolExecutionError(name, f"tool no registrada (válidas: {list(handlers)})")
        try:
            return handlers[name](arguments)
        except IntencionInvalidaError as exc:
            return f"ERROR: {exc}"
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(name, str(exc)) from exc

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, key: object) -> bool:
        return key in self._plugins
