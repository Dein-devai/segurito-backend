"""Tests de PromptPipeline — cada sección por separado + integración."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.bootstrap import build_registry
from backend.core.models import IntencionDef, ServiceItem, ToolDef
from backend.core.plugin import OrganismoPlugin, ToolHandler
from backend.prompt.pipeline import (
    DEFAULT_SECTIONS,
    PROMPT_VERSION,
    CoreIdentitySection,
    DerivationSection,
    FlowSection,
    IntencionesGlobalesSection,
    OrganismosSection,
    PromptContext,
    PromptPipeline,
    SecurityRulesSection,
    StyleSection,
)
from backend.registry import PluginRegistry
from backend.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _StubPlugin(OrganismoPlugin):
    def __init__(self, key: str, nombre: str, fragment: str) -> None:
        self.key = key
        self.nombre = nombre
        self.collection_name = f"{key}_servicios"
        self.activo = True
        self._fragment = fragment

    def intenciones(self) -> dict[str, IntencionDef]:
        return {
            "RECLAMO": IntencionDef(nombre="RECLAMO", descripcion=f"Reclamo {self.key}"),
        }

    def tools(self) -> list[ToolDef]:
        return []

    def tool_handlers(self) -> dict[str, ToolHandler]:
        return {}

    def prompt_fragment(self) -> str:
        return self._fragment

    def format_service(self, item: ServiceItem) -> str:
        return f"### {item.id}"


@pytest.fixture
def registry_cmf_only(monkeypatch: pytest.MonkeyPatch) -> PluginRegistry:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    return build_registry(Settings())


@pytest.fixture
def empty_registry() -> PluginRegistry:
    return PluginRegistry()


@pytest.fixture
def registry_two_stubs() -> PluginRegistry:
    reg = PluginRegistry()
    reg.register(_StubPlugin("alpha", "Organismo Alpha", "### ALPHA — fragmento"))
    reg.register(_StubPlugin("beta", "Organismo Beta", "### BETA — fragmento"))
    return reg


# ---------------------------------------------------------------------------
# Sección por sección
# ---------------------------------------------------------------------------
def test_core_identity_lista_organismos(registry_two_stubs: PluginRegistry) -> None:
    out = CoreIdentitySection().render(PromptContext(registry=registry_two_stubs))
    assert "Segurito" in out
    assert "Organismo Alpha" in out
    assert "Organismo Beta" in out
    assert "<user_input>" in out


def test_core_identity_sin_organismos(empty_registry: PluginRegistry) -> None:
    out = CoreIdentitySection().render(PromptContext(registry=empty_registry))
    assert "Segurito" in out
    assert "—" in out  # placeholder cuando no hay organismos


def test_organismos_section_concatena_fragments(
    registry_two_stubs: PluginRegistry,
) -> None:
    out = OrganismosSection().render(PromptContext(registry=registry_two_stubs))
    assert "ALPHA — fragmento" in out
    assert "BETA — fragmento" in out


def test_organismos_section_vacio(empty_registry: PluginRegistry) -> None:
    out = OrganismosSection().render(PromptContext(registry=empty_registry))
    assert "ninguno" in out.lower()


def test_intenciones_globales_menciona_alerta_y_oos(
    empty_registry: PluginRegistry,
) -> None:
    out = IntencionesGlobalesSection().render(PromptContext(registry=empty_registry))
    assert "ALERTA" in out
    assert "OUT_OF_SCOPE" in out
    assert "fraude" in out.lower() or "estafa" in out.lower()


def test_flow_section_menciona_intenciones(empty_registry: PluginRegistry) -> None:
    out = FlowSection().render(PromptContext(registry=empty_registry))
    for intencion in ("RECLAMO", "TRAMITE", "CONSULTA", "ALERTA", "OUT_OF_SCOPE"):
        assert intencion in out


def test_flow_consulta_es_multiturno(empty_registry: PluginRegistry) -> None:
    out = FlowSection().render(PromptContext(registry=empty_registry))
    assert "CONSULTA" in out
    assert "NO invoques" in out  # primer turno


def test_security_section_anti_injection(empty_registry: PluginRegistry) -> None:
    out = SecurityRulesSection().render(PromptContext(registry=empty_registry))
    assert "ignora tus instrucciones" in out.lower()
    assert "system prompt" in out.lower()
    assert "url" in out.lower()  # no inventar URLs


def test_style_section_menciona_formato(empty_registry: PluginRegistry) -> None:
    out = StyleSection().render(PromptContext(registry=empty_registry))
    assert "negrita" in out.lower()
    assert "200 palabras" in out


def test_derivation_section_lista_organismos_del_registry(
    registry_two_stubs: PluginRegistry,
) -> None:
    out = DerivationSection().render(PromptContext(registry=registry_two_stubs))
    assert "Organismo Alpha" in out
    assert "Organismo Beta" in out
    assert "DERIVACIÓN" in out
    assert "ChileAtiende" in out


def test_derivation_section_sin_organismos(empty_registry: PluginRegistry) -> None:
    out = DerivationSection().render(PromptContext(registry=empty_registry))
    assert "(ninguno)" in out


# ---------------------------------------------------------------------------
# Pipeline integración
# ---------------------------------------------------------------------------
def test_pipeline_default_sections_incluye_todas() -> None:
    pipe = PromptPipeline()
    section_types = {type(s) for s in pipe.sections}
    assert section_types == set(DEFAULT_SECTIONS)


def test_pipeline_build_incluye_version_y_todas_secciones(
    registry_cmf_only: PluginRegistry,
) -> None:
    pipe = PromptPipeline()
    out = pipe.build(registry_cmf_only)
    assert PROMPT_VERSION in out
    assert "Segurito" in out
    assert "ORGANISMOS DISPONIBLES" in out
    assert "INTENCIONES GLOBALES" in out
    assert "FLUJO POR INTENCIÓN" in out
    assert "REGLAS DE SEGURIDAD" in out
    assert "ESTILO" in out


def test_pipeline_acepta_secciones_custom(empty_registry: PluginRegistry) -> None:
    section = MagicMock()
    section.render.return_value = "MARKER_CUSTOM"
    pipe = PromptPipeline(sections=[section])
    out = pipe.build(empty_registry)
    assert "MARKER_CUSTOM" in out
    section.render.assert_called_once()


def test_pipeline_es_reactivo_al_registry(registry_two_stubs: PluginRegistry) -> None:
    """Snapshot diferencial: agregar plugins cambia el prompt sin tocar el pipeline."""
    pipe = PromptPipeline()
    out_two = pipe.build(registry_two_stubs)
    out_empty = pipe.build(PluginRegistry())

    assert "Organismo Alpha" in out_two
    assert "Organismo Alpha" not in out_empty
    # Versión y secciones estructurales se mantienen
    assert PROMPT_VERSION in out_two
    assert PROMPT_VERSION in out_empty


def test_prompt_cmf_solo_no_menciona_sernac(registry_cmf_only: PluginRegistry) -> None:
    """Si SERNAC no está en enabled_organismos, no aparece en el prompt."""
    out = PromptPipeline().build(registry_cmf_only)
    assert "CMF" in out
    assert "SERNAC" not in out
    assert "Servicio de Impuestos" not in out


def test_prompt_cmf_y_sernac_menciona_ambos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf", "sernac"]')
    registry = build_registry(Settings())
    out = PromptPipeline().build(registry)
    assert "CMF" in out
    assert "SERNAC" in out
