"""Plugin SERNAC — presencia institucional (sin tools propias).

**Pivot Capa Legal**: Las páginas internas de SERNAC (registro de reclamos,
estado de casos) están detrás de ClaveÚnica. No es viable scrapear sin
sesión. En lugar de mantener datos curados ad-hoc, este plugin:

1. Aporta sólo el ``prompt_fragment`` con canales públicos verificables
   (fono y portal) y la disclaimer sobre la barrera de autenticación.
2. **No expone tools**. La identificación legal del organismo competente
   pasa por ``LegalCorpusPlugin`` (Ley 19.496 mapea a SERNAC).
3. **No usa VectorStore**. Sin tools no hay RAG por hacer aquí.
"""
from __future__ import annotations

from pathlib import Path

from backend.core.models import IntencionDef, ServiceItem, ToolDef
from backend.core.plugin import OrganismoPlugin, ToolHandler

PROMPT_FRAGMENT_SERNAC = """### SERNAC — Servicio Nacional del Consumidor (Chile)
Mandato: derechos del consumidor (Ley 19.496) frente a cualquier proveedor de
bienes o servicios — retail, telecomunicaciones, servicios básicos, comercio
electrónico, etc. NO regula bancos/AFP/seguros (eso es CMF), ni materias
tributarias (eso es SII).

**Canales oficiales verificables** (sin sesión / sin ClaveÚnica):
- Portal: https://www.sernac.cl/
- Reclamos: https://www.sernac.cl/
- Fono Consumidor: 800 700 100

**Limitación honesta**: el flujo de ingreso de reclamo requiere ClaveÚnica
en la última etapa. No tenemos acceso a casos individuales ni a estado de
trámite. Cuando el usuario quiera presentar un reclamo, derívalo al portal
indicando los pasos generales y los datos que necesitará tener a mano.

Para identificar si SERNAC es el organismo correcto, usa
`consultar_marco_legal` (la Ley 19.496 mapea a SERNAC)."""


class SernacPlugin(OrganismoPlugin):
    """Plugin SERNAC reducido a presencia institucional."""

    def __init__(self, data_path: Path | None = None) -> None:
        self.key = "sernac"
        self.nombre = "Servicio Nacional del Consumidor"
        # data_path se acepta por compatibilidad con bootstrap, pero no se usa.
        self.data_path = data_path or Path("data/sernac")
        self.collection_name = "sernac_servicios"  # placeholder, no se ingesta
        self.activo = True

    def intenciones(self) -> dict[str, IntencionDef]:
        return {}

    def tools(self) -> list[ToolDef]:
        return []

    def tool_handlers(self) -> dict[str, ToolHandler]:
        return {}

    def prompt_fragment(self) -> str:
        return PROMPT_FRAGMENT_SERNAC

    def format_service(self, item: ServiceItem) -> str:  # pragma: no cover
        # Sin tools no hay items que renderizar; método por contrato.
        return f"(SernacPlugin no produce items: id={item.id})"
