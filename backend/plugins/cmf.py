"""Plugin del organismo CMF — Comisión para el Mercado Financiero (Chile).

Encapsula:
- Intenciones específicas de CMF (RECLAMO, CONSULTA, TRAMITE).
- Tools `buscar_servicios_cmf`, `obtener_detalle_servicio_cmf`.
- Fragmento del system prompt que describe el dominio CMF.
- Path al JSON con servicios curados.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.exceptions import IntencionInvalidaError
from backend.core.models import IntencionDef, ServiceItem, ToolDef
from backend.core.plugin import OrganismoPlugin, ToolHandler
from backend.vector_store import VectorStore

INTENCIONES_CMF: dict[str, IntencionDef] = {
    "RECLAMO": IntencionDef(
        nombre="RECLAMO",
        descripcion=(
            "El usuario tiene un problema o disputa concreta con una entidad "
            "fiscalizada por la CMF (banco, AFP, aseguradora, etc.) y busca que "
            "alguien lo resuelva."
        ),
    ),
    "RECLAMO_PRODUCTO": IntencionDef(
        nombre="RECLAMO_PRODUCTO",
        descripcion=(
            "Problemas con productos financieros: cobros indebidos, cargos no "
            "reconocidos, tarjetas de crédito, cuentas corrientes, mutuarias."
        ),
    ),
    "RECLAMO_SERVICIO": IntencionDef(
        nombre="RECLAMO_SERVICIO",
        descripcion=(
            "Problemas con servicios: negativa de pago de seguros, malas prácticas "
            "de cobranza, incumplimiento de póliza, AFP que no devuelve aportes."
        ),
    ),
    "RECLAMO_INFORMACION": IntencionDef(
        nombre="RECLAMO_INFORMACION",
        descripcion=(
            "Falta de información, publicidad engañosa, términos no explicados, "
            "documentación incompleta por parte de la entidad financiera."
        ),
    ),
    "CONSULTA": IntencionDef(
        nombre="CONSULTA",
        descripcion=(
            "El usuario solo necesita información — no tiene problema, solo "
            "quiere saber algo (acciones, deudas, seguros, precios SOAP, "
            "estado de trámite)."
        ),
    ),
    "TRAMITE": IntencionDef(
        nombre="TRAMITE",
        descripcion=(
            "El usuario quiere obtener un documento o certificado emitido por "
            "la CMF (informe de deudas, certificado corredores, alzamiento de "
            "hipoteca, suscripción a alertas)."
        ),
    ),
}

VALID_INTENCIONES_CMF: tuple[str, ...] = tuple(INTENCIONES_CMF.keys())

PROMPT_FRAGMENT_CMF = """### CMF — Comisión para el Mercado Financiero (Chile)
Mandato: bancos, AFP, aseguradoras, mutuarias, mercado de valores, corredores.

Cuando la consulta sea sobre estos productos, usa las tools del plugin CMF:
- `buscar_servicios_cmf(query, intencion, n_results)` para encontrar servicios oficiales.
- `obtener_detalle_servicio_cmf(service_id)` para ficha completa de un servicio.

Intenciones reconocidas: RECLAMO, RECLAMO_PRODUCTO, RECLAMO_SERVICIO, RECLAMO_INFORMACION, CONSULTA, TRAMITE.

Sub-intenciones de reclamo:
- **RECLAMO_PRODUCTO**: cobros indebidos, cargos no reconocidos, problemas con tarjetas de crédito, cuentas corrientes, mutuarias.
- **RECLAMO_SERVICIO**: seguros que no pagan, malas prácticas de cobranza, incumplimiento de póliza, AFP que no devuelve aportes.
- **RECLAMO_INFORMACION**: publicidad engañosa, falta de transparencia, términos no explicados, documentación incompleta."""


def _format_service_cmf(item: ServiceItem) -> str:
    """Markdown de un servicio CMF."""
    md = item.metadata
    parts = [
        f"### {md.get('titulo', '(sin título)')}",
        f"- **id**: `{item.id}`",
        f"- **intención**: {md.get('intencion', '-')}",
    ]
    if item.similarity is not None:
        parts.append(f"- **similitud**: {item.similarity:.3f}")
    for key, label in (
        ("dirigido_a", "dirigido a"),
        ("documentos_requeridos", "documentos requeridos"),
        ("tiempo", "tiempo"),
        ("costo", "costo"),
        ("url", "url"),
    ):
        value = md.get(key)
        if value:
            parts.append(f"- **{label}**: {value}")
    parts.append("")
    parts.append(item.document)
    return "\n".join(parts)


def _build_tool_buscar() -> ToolDef:
    return ToolDef(
        name="buscar_servicios_cmf",
        description=(
            "Busca servicios oficiales del portal CMF (Comisión para el "
            "Mercado Financiero de Chile) relevantes para la consulta del "
            "usuario. Antes de invocar, infiere la intención del usuario y "
            "pásala como argumento. Intenciones válidas: RECLAMO, CONSULTA, "
            "TRAMITE."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Reformulación concisa en español de la necesidad del "
                        "usuario, optimizada para búsqueda semántica."
                    ),
                },
                "intencion": {
                    "type": "string",
                    "enum": list(VALID_INTENCIONES_CMF),
                    "description": "Categoría inferida.",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Cantidad máxima (1-5).",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 5,
                },
            },
            "required": ["query", "intencion"],
        },
    )


def _build_tool_detalle() -> ToolDef:
    return ToolDef(
        name="obtener_detalle_servicio_cmf",
        description=(
            "Devuelve la ficha completa de un servicio CMF a partir de su id "
            "(ej. 'art-79775'). Usar cuando se necesite más detalle del que "
            "entrega buscar_servicios_cmf."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "Identificador, formato 'art-<numero>'.",
                },
            },
            "required": ["service_id"],
        },
    )


class CmfPlugin(OrganismoPlugin):
    """Plugin CMF activo en producción."""

    def __init__(
        self,
        data_path: Path,
        store: VectorStore | None = None,
    ) -> None:
        self.key = "cmf"
        self.nombre = "Comisión para el Mercado Financiero"
        self.data_path = data_path
        self.collection_name = "cmf_servicios"
        self.activo = True
        self._store = store or VectorStore(self.collection_name)

    @property
    def store(self) -> VectorStore:
        return self._store

    def intenciones(self) -> dict[str, IntencionDef]:
        return INTENCIONES_CMF

    def tools(self) -> list[ToolDef]:
        return [_build_tool_buscar(), _build_tool_detalle()]

    def tool_handlers(self) -> dict[str, ToolHandler]:
        return {
            "buscar_servicios_cmf": self._handle_buscar,
            "obtener_detalle_servicio_cmf": self._handle_detalle,
        }

    def prompt_fragment(self) -> str:
        return PROMPT_FRAGMENT_CMF

    def format_service(self, item: ServiceItem) -> str:
        return _format_service_cmf(item)

    # -- handlers -----------------------------------------------------------
    def _handle_buscar(self, arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip()
        intencion = str(arguments.get("intencion", "")).strip().upper()
        n_results = int(arguments.get("n_results", 3))
        n_results = max(1, min(5, n_results))

        if not query:
            return "ERROR: argumento 'query' vacío."
        if intencion not in VALID_INTENCIONES_CMF:
            raise IntencionInvalidaError(intencion, VALID_INTENCIONES_CMF)

        results = self._store.search(query, intencion=intencion, n_results=n_results)
        if not results:
            return (
                f"No se encontraron servicios CMF para intención={intencion} "
                f"y query={query!r}."
            )
        header = (
            f"Se encontraron {len(results)} servicio(s) CMF "
            f"(intención={intencion}):\n\n"
        )
        return header + "\n\n---\n\n".join(self.format_service(r) for r in results)

    def _handle_detalle(self, arguments: dict[str, Any]) -> str:
        service_id = str(arguments.get("service_id", "")).strip()
        if not service_id:
            return "ERROR: argumento 'service_id' vacío."
        item = self._store.get(service_id)
        if item is None:
            return f"No existe el servicio con id={service_id!r}."
        return self.format_service(item)
