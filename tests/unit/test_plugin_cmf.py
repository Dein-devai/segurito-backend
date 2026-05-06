"""Tests para backend.plugins.cmf — sin Chroma, sin red, sin filesystem real."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.core.exceptions import IntencionInvalidaError
from backend.core.models import ServiceItem
from backend.plugins.cmf import (
    INTENCIONES_CMF,
    PROMPT_FRAGMENT_CMF,
    VALID_INTENCIONES_CMF,
    CmfPlugin,
)


@pytest.fixture
def fake_store() -> MagicMock:
    return MagicMock()


@pytest.fixture
def plugin(fake_store: MagicMock) -> CmfPlugin:
    return CmfPlugin(data_path=Path("/tmp/none.json"), store=fake_store)


def test_intenciones_son_reclamo_consulta_tramite() -> None:
    assert set(INTENCIONES_CMF.keys()) == {"RECLAMO", "CONSULTA", "TRAMITE"}
    assert VALID_INTENCIONES_CMF == ("RECLAMO", "CONSULTA", "TRAMITE")


def test_plugin_cumple_contrato_basico(plugin: CmfPlugin) -> None:
    assert plugin.key == "cmf"
    assert plugin.collection_name == "cmf_servicios"
    assert plugin.activo is True
    assert "CMF" in plugin.prompt_fragment()


def test_tools_y_handlers_coinciden(plugin: CmfPlugin) -> None:
    """Si esto falla, el contrato del registry rechaza el plugin."""
    tool_names = {t.name for t in plugin.tools()}
    handler_names = set(plugin.tool_handlers().keys())
    assert tool_names == handler_names


def test_buscar_query_vacio_devuelve_error(plugin: CmfPlugin) -> None:
    result = plugin._handle_buscar({"query": "  ", "intencion": "RECLAMO"})
    assert "ERROR" in result


def test_buscar_intencion_invalida_lanza(plugin: CmfPlugin) -> None:
    with pytest.raises(IntencionInvalidaError):
        plugin._handle_buscar({"query": "x", "intencion": "FOO"})


def test_buscar_sin_resultados(plugin: CmfPlugin, fake_store: MagicMock) -> None:
    fake_store.search.return_value = []
    result = plugin._handle_buscar({"query": "x", "intencion": "RECLAMO"})
    assert "No se encontraron" in result


def test_buscar_con_resultados_renderiza_markdown(
    plugin: CmfPlugin, fake_store: MagicMock
) -> None:
    fake_store.search.return_value = [
        ServiceItem(
            id="art-1",
            document="contenido del servicio",
            metadata={"titulo": "Reclamo bancario", "intencion": "RECLAMO"},
            similarity=0.85,
        )
    ]
    result = plugin._handle_buscar({"query": "banco me cobró", "intencion": "RECLAMO"})
    assert "Se encontraron 1 servicio" in result
    assert "Reclamo bancario" in result
    assert "art-1" in result
    assert "0.850" in result


def test_buscar_clamps_n_results(plugin: CmfPlugin, fake_store: MagicMock) -> None:
    fake_store.search.return_value = []
    plugin._handle_buscar(
        {"query": "x", "intencion": "RECLAMO", "n_results": 99}
    )
    assert fake_store.search.call_args.kwargs["n_results"] == 5

    plugin._handle_buscar(
        {"query": "x", "intencion": "RECLAMO", "n_results": 0}
    )
    assert fake_store.search.call_args.kwargs["n_results"] == 1


def test_detalle_id_vacio(plugin: CmfPlugin) -> None:
    assert "ERROR" in plugin._handle_detalle({"service_id": ""})


def test_detalle_no_existe(plugin: CmfPlugin, fake_store: MagicMock) -> None:
    fake_store.get.return_value = None
    result = plugin._handle_detalle({"service_id": "art-999"})
    assert "No existe" in result


def test_detalle_existe(plugin: CmfPlugin, fake_store: MagicMock) -> None:
    fake_store.get.return_value = ServiceItem(
        id="art-1",
        document="contenido",
        metadata={"titulo": "Servicio X"},
    )
    result = plugin._handle_detalle({"service_id": "art-1"})
    assert "Servicio X" in result


def test_format_service_omite_campos_vacios(plugin: CmfPlugin) -> None:
    item = ServiceItem(
        id="art-1",
        document="doc",
        metadata={"titulo": "T", "intencion": "RECLAMO"},
    )
    result = plugin.format_service(item)
    assert "dirigido a" not in result
    assert "tiempo" not in result


def test_prompt_fragment_no_vacio() -> None:
    assert len(PROMPT_FRAGMENT_CMF) > 50
