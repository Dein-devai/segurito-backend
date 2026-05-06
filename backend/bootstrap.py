"""Bootstrap del PluginRegistry desde Settings.

Encapsula el descubrimiento de plugins activos. Cambiar plugins se hace
únicamente vía variable de entorno SEGURITO_ENABLED_ORGANISMOS — no se
toca código.
"""
from __future__ import annotations

from backend.core.exceptions import ConfigurationError
from backend.core.plugin import OrganismoPlugin
from backend.plugins.cmf import CmfPlugin
from backend.plugins.legal import LegalCorpusPlugin
from backend.plugins.sernac import SernacPlugin
from backend.plugins.sii import SiiPlugin
from backend.registry import PluginRegistry
from backend.settings import Settings


def _build_plugin(key: str, settings: Settings) -> OrganismoPlugin:
    """Mapping key → instancia. Aquí está la única tabla que conoce nombres."""
    if key == "cmf":
        return CmfPlugin(data_path=settings.data_dir / "cmf" / "services.json")
    if key == "legal":
        return LegalCorpusPlugin(
            data_path=settings.data_dir / "legal" / "articulos.json"
        )
    if key == "sernac":
        return SernacPlugin(data_path=settings.data_dir / "sernac")
    if key == "sii":
        return SiiPlugin(data_path=settings.data_dir / "sii")
    raise ConfigurationError(f"Plugin desconocido: {key!r}")


def build_registry(settings: Settings) -> PluginRegistry:
    """Construye un PluginRegistry según `settings.enabled_organismos`.

    Si una key aparece en `enabled_organismos`, el plugin se fuerza a activo
    y se registra. El flag `activo` del plugin es valor por defecto (los
    stubs vienen con activo=False), pero la config manda.
    """
    registry = PluginRegistry()
    for key in settings.enabled_organismos:
        plugin = _build_plugin(key, settings)
        plugin.activo = True
        registry.register(plugin)
    return registry
