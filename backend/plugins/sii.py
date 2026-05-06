"""Plugin SII — presencia institucional (sin tools propias).

**Pivot Capa Legal**: Las consultas relevantes del SII (declaraciones,
boletas, estado tributario) viven detrás de ClaveTributaria. No es viable
scrapear sin sesión. En lugar de mantener datos curados ad-hoc, este plugin:

1. Aporta sólo el ``prompt_fragment`` con canales públicos verificables
   (fono, portal SII y ChileAtiende) y la disclaimer sobre autenticación.
2. **No expone tools**. La identificación tributaria legal pasa por
   ``LegalCorpusPlugin`` (DL 824 LIR, DL 825 IVA y resoluciones SII mapean
   a SII).
3. **No usa VectorStore**. Sin tools no hay RAG por hacer aquí.
"""
from __future__ import annotations

from pathlib import Path

from backend.core.models import IntencionDef, ServiceItem, ToolDef
from backend.core.plugin import OrganismoPlugin, ToolHandler

PROMPT_FRAGMENT_SII = """### SII — Servicio de Impuestos Internos (Chile)
Mandato: tributación nacional — Impuesto a la Renta (DL 824), IVA (DL 825),
boletas y facturas electrónicas, Operación Renta, RUT, inicio de actividades,
término de giro, regímenes simplificados (Pro Pyme), criptoactivos. NO regula
bancos/AFP/mercado de valores (eso es CMF), ni derechos del consumidor frente
a un proveedor (eso es SERNAC).

**Canales oficiales verificables** (información pública, sin sesión):
- Portal: https://www.sii.cl/
- Mesa de ayuda SII: 22 395 1115
- ChileAtiende (consultas generales): https://www.chileatiende.gob.cl/ — fono 101

**Limitación honesta**: las operaciones individuales (declaraciones, F22,
F29, certificados con RUT) requieren ClaveTributaria o ClaveÚnica. No
tenemos acceso a información tributaria personal. Cuando el usuario quiera
hacer una declaración o ver su estado, derívalo al portal indicando los
pasos generales y los datos que necesitará.

Para identificar si SII es el organismo correcto, usa
`consultar_marco_legal` (DL 824, DL 825 y circulares/resoluciones SII
mapean a SII)."""


class SiiPlugin(OrganismoPlugin):
    """Plugin SII reducido a presencia institucional."""

    def __init__(self, data_path: Path | None = None) -> None:
        self.key = "sii"
        self.nombre = "Servicio de Impuestos Internos"
        self.data_path = data_path or Path("data/sii")
        self.collection_name = "sii_servicios"  # placeholder, no se ingesta
        self.activo = True

    def intenciones(self) -> dict[str, IntencionDef]:
        return {}

    def tools(self) -> list[ToolDef]:
        return []

    def tool_handlers(self) -> dict[str, ToolHandler]:
        return {}

    def prompt_fragment(self) -> str:
        return PROMPT_FRAGMENT_SII

    def format_service(self, item: ServiceItem) -> str:  # pragma: no cover
        return f"(SiiPlugin no produce items: id={item.id})"
