"""Plugin transversal `legal` — Marco normativo chileno.

A diferencia de un organismo (CMF/SERNAC/SII), este plugin **no** representa
una institución sino el corpus legal que las atraviesa: leyes, circulares y
resoluciones que el agente cita para:

1. Reducir ambigüedad cuando una consulta podría caer en más de un organismo.
2. Sustentar respuestas con fuente normativa verificable.
3. Mapear cada artículo a su(s) ``organismos_competentes`` para guiar derivación.

Características:
- Sin intenciones (devuelve dict vacío). El plugin `legal` no compite con la
  taxonomía RECLAMO/CONSULTA/TRAMITE; complementa.
- Una sola tool: ``consultar_marco_legal(query, n_results)``.
- Ingest del corpus usa ``intencion_field=None`` (los artículos no llevan
  campo intencion).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.models import IntencionDef, ServiceItem, ToolDef
from backend.core.plugin import OrganismoPlugin, ToolHandler
from backend.vector_store import VectorStore

PROMPT_FRAGMENT_LEGAL = """### Marco Legal — corpus normativo chileno
Cuándo invocar la tool `consultar_marco_legal`:
- La consulta menciona una ley, artículo, decreto o circular.
- Es ambigua entre dos o más organismos (ej. cláusula abusiva en seguro → \
SERNAC y CMF; honorarios de plataforma extranjera → SII).
- Necesitas justificar a qué organismo derivar y por qué.

Reglas al usar resultados:
1. Cita SIEMPRE el artículo recuperado (ley, número y nombre).
2. Si `metadata.organismos_competentes` tiene más de uno, menciona ambos y \
explica brevemente la frontera.
3. No inventes artículos. Si la búsqueda no devuelve nada relevante, dilo."""


def _build_tool_consultar() -> ToolDef:
    return ToolDef(
        name="consultar_marco_legal",
        description=(
            "Consulta el corpus legal chileno (Ley 19.496 Consumidor, Ley "
            "21.521 Fintec, Ley 18.045 Mercado de Valores, Ley 18.010 "
            "Operaciones de Crédito, DL 824 LIR, DL 825 IVA, circulares y "
            "resoluciones SII). Devuelve los artículos top-K más relevantes "
            "con texto literal y los organismos competentes por artículo. "
            "Úsala cuando necesites identificar el organismo correcto, citar "
            "una norma o resolver ambigüedad cross-organismo."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Reformulación concisa en español de lo que necesitas "
                        "encontrar en la ley (ej. 'cláusula abusiva en seguro "
                        "de auto', 'IVA streaming extranjero', 'tasa máxima "
                        "convencional')."
                    ),
                },
                "n_results": {
                    "type": "integer",
                    "description": "Cantidad de artículos a recuperar (1-5).",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 5,
                },
            },
            "required": ["query"],
        },
    )


def _format_articulo(item: ServiceItem) -> str:
    md = item.metadata
    organismos = md.get("organismos_competentes", [])
    if isinstance(organismos, str):
        organismos = [organismos]
    parts = [
        f"### {md.get('nombre_ley', '(ley sin nombre)')} — "
        f"{md.get('articulo', '')}",
        f"- **id**: `{item.id}`",
        f"- **organismos competentes**: {', '.join(organismos) or '-'}",
    ]
    ubicacion = md.get("ubicacion")
    if ubicacion:
        parts.append(f"- **ubicación**: {ubicacion}")
    if item.similarity is not None:
        parts.append(f"- **similitud**: {item.similarity:.3f}")
    url = md.get("url_servicio_asociado")
    if url:
        parts.append(f"- **fuente**: {url}")
    texto = md.get("texto_literal") or item.document
    parts.append("")
    parts.append(f"> {texto}")
    return "\n".join(parts)


class LegalCorpusPlugin(OrganismoPlugin):
    """Plugin transversal del corpus legal chileno."""

    def __init__(
        self,
        data_path: Path,
        store: VectorStore | None = None,
    ) -> None:
        self.key = "legal"
        self.nombre = "Marco Legal Chile"
        self.data_path = data_path
        self.collection_name = "legal_articulos"
        self.activo = True
        self._store = store or VectorStore(self.collection_name)

    @property
    def store(self) -> VectorStore:
        return self._store

    def intenciones(self) -> dict[str, IntencionDef]:
        # Plugin transversal: no aporta intenciones.
        return {}

    def tools(self) -> list[ToolDef]:
        return [_build_tool_consultar()]

    def tool_handlers(self) -> dict[str, ToolHandler]:
        return {"consultar_marco_legal": self._handle_consultar}

    def prompt_fragment(self) -> str:
        return PROMPT_FRAGMENT_LEGAL

    def format_service(self, item: ServiceItem) -> str:
        return _format_articulo(item)

    # -- handlers -----------------------------------------------------------
    def _handle_consultar(self, arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip()
        n_results = int(arguments.get("n_results", 3))
        n_results = max(1, min(5, n_results))

        if not query:
            return "ERROR: argumento 'query' vacío."

        # El corpus legal no usa filtro por intención.
        results = self._store.search(query, intencion=None, n_results=n_results)
        if not results:
            return f"No se encontraron artículos legales para query={query!r}."

        header = (
            f"Se encontraron {len(results)} artículo(s) relevantes en el "
            f"corpus legal:\n\n"
        )
        return header + "\n\n---\n\n".join(
            self.format_service(r) for r in results
        )
