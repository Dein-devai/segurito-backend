"""Contrato `OrganismoPlugin`.

Cada organismo (CMF, SERNAC, SII, ...) implementa esta interfaz. El sistema
no conoce CMF en particular: opera contra el contrato.

Patrón: Strategy. Cada plugin es una estrategia intercambiable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from backend.core.models import IntencionDef, ServiceItem, ToolDef

#: Handler que ejecuta una tool. Recibe argumentos parseados, devuelve markdown.
ToolHandler = Callable[[dict], str]


class OrganismoPlugin(ABC):
    """Contrato que cada organismo debe cumplir.

    El plugin encapsula:
    - Identidad (key, nombre).
    - Etiquetas de intención específicas (además de las globales).
    - Tools que aporta al agente.
    - Fragmento de system prompt que se compone con el resto.
    - Datos (path al JSON / colección Chroma).
    """

    #: Identificador corto, lowercase. Ej: "cmf", "sernac", "sii".
    key: str

    #: Nombre humano para presentar en prompts y respuestas.
    nombre: str

    #: Path al archivo JSON con los servicios curados.
    data_path: Path

    #: Nombre de la colección Chroma. Convención: "{key}_servicios".
    collection_name: str

    #: Activo en runtime. Plugins en stub se construyen pero no se exponen.
    activo: bool = True

    @abstractmethod
    def intenciones(self) -> dict[str, IntencionDef]:
        """Intenciones que este plugin reconoce. Se mergean con globales."""
        ...

    @abstractmethod
    def tools(self) -> list[ToolDef]:
        """Tools que el plugin expone al agente."""
        ...

    @abstractmethod
    def tool_handlers(self) -> dict[str, ToolHandler]:
        """Mapping nombre_tool → handler. Debe cubrir todas las tools()."""
        ...

    @abstractmethod
    def prompt_fragment(self) -> str:
        """Fragmento del system prompt que aporta este plugin.

        Se inyecta en la sección "Organismos" del prompt pipeline.
        """
        ...

    @abstractmethod
    def format_service(self, item: ServiceItem) -> str:
        """Renderiza un ServiceItem como markdown para el LLM."""
        ...

    def ingest_data(self) -> int | None:
        """Hook opcional: ingesta `data_path` en la colección si está vacía.

        Devuelve el conteo final de la colección, o None si el plugin no
        usa VectorStore. Default: no-op (plugins sin RAG lo omiten).
        """
        return None

    def __repr__(self) -> str:
        estado = "activo" if self.activo else "stub"
        return f"<{self.__class__.__name__} key={self.key!r} ({estado})>"
