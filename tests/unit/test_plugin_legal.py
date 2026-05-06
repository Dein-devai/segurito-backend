"""Tests para backend.plugins.legal — corpus legal como router transversal."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.core.models import ServiceItem
from backend.plugins.legal import (
    PROMPT_FRAGMENT_LEGAL,
    LegalCorpusPlugin,
)


@pytest.fixture
def fake_store() -> MagicMock:
    return MagicMock()


@pytest.fixture
def plugin(fake_store: MagicMock) -> LegalCorpusPlugin:
    return LegalCorpusPlugin(
        data_path=Path("/tmp/articulos.json"), store=fake_store
    )


def test_plugin_cumple_contrato_basico(plugin: LegalCorpusPlugin) -> None:
    assert plugin.key == "legal"
    assert plugin.activo is True
    assert plugin.collection_name == "legal_articulos"


def test_intenciones_son_vacias(plugin: LegalCorpusPlugin) -> None:
    """LegalCorpusPlugin es transversal: no aporta intenciones propias."""
    assert plugin.intenciones() == {}


def test_tools_y_handlers_coinciden(plugin: LegalCorpusPlugin) -> None:
    tools = plugin.tools()
    handlers = plugin.tool_handlers()
    assert {t.name for t in tools} == {"consultar_marco_legal"}
    assert set(handlers.keys()) == {t.name for t in tools}


def test_consultar_query_vacio_devuelve_error(plugin: LegalCorpusPlugin) -> None:
    out = plugin.tool_handlers()["consultar_marco_legal"]({"query": "   "})
    assert "ERROR" in out and "query" in out


def test_consultar_sin_resultados(
    plugin: LegalCorpusPlugin, fake_store: MagicMock
) -> None:
    fake_store.search.return_value = []
    out = plugin.tool_handlers()["consultar_marco_legal"]({"query": "xyz"})
    assert "No se encontraron" in out
    # Crucial: el corpus legal NO filtra por intencion.
    fake_store.search.assert_called_once_with("xyz", intencion=None, n_results=3)


def test_consultar_con_resultados_renderiza_articulo(
    plugin: LegalCorpusPlugin, fake_store: MagicMock
) -> None:
    fake_store.search.return_value = [
        ServiceItem(
            id="ley-19496-art16",
            document="Ley 19.496 — Art. 16\n...",
            metadata={
                "id_ley": "19496",
                "nombre_ley": "Protección de los Derechos de los Consumidores",
                "articulo": "Art. 16",
                "ubicacion": "Título III, Párrafo 4",
                "texto_literal": "No producirán efecto alguno...",
                "url_servicio_asociado": "https://www.bcn.cl/leychile/?idNorma=61438",
                "organismos_competentes": ["SERNAC", "CMF"],
            },
            similarity=0.91,
        )
    ]
    out = plugin.tool_handlers()["consultar_marco_legal"](
        {"query": "clausula abusiva seguro", "n_results": 1}
    )
    assert "Art. 16" in out
    assert "ley-19496-art16" in out
    # Caso multi-organismo: deben aparecer ambos.
    assert "SERNAC" in out and "CMF" in out
    assert "0.910" in out  # similitud formateada
    assert "https://www.bcn.cl/" in out
    assert "No producirán efecto" in out


def test_consultar_clamps_n_results(
    plugin: LegalCorpusPlugin, fake_store: MagicMock
) -> None:
    fake_store.search.return_value = []
    plugin.tool_handlers()["consultar_marco_legal"](
        {"query": "x", "n_results": 99}
    )
    fake_store.search.assert_called_once_with("x", intencion=None, n_results=5)


def test_consultar_organismos_como_string_se_normaliza(
    plugin: LegalCorpusPlugin, fake_store: MagicMock
) -> None:
    """Si por error metadata trae un string, no debe explotar."""
    fake_store.search.return_value = [
        ServiceItem(
            id="x",
            document="x",
            metadata={
                "nombre_ley": "Foo",
                "articulo": "Art. 1",
                "organismos_competentes": "SERNAC",  # string, no list
            },
        )
    ]
    out = plugin.tool_handlers()["consultar_marco_legal"]({"query": "q"})
    assert "SERNAC" in out


def test_prompt_fragment_no_vacio() -> None:
    assert "consultar_marco_legal" in PROMPT_FRAGMENT_LEGAL
    assert "ambigua" in PROMPT_FRAGMENT_LEGAL.lower() or "ambig" in PROMPT_FRAGMENT_LEGAL.lower()


def test_corpus_articulos_json_es_valido() -> None:
    """El JSON real del corpus debe poder cargarse y tener el shape esperado."""
    import json

    path = Path("data/legal/articulos.json")
    items = json.loads(path.read_text(encoding="utf-8"))
    assert len(items) >= 20
    for it in items:
        assert {"id", "document", "metadata"}.issubset(it.keys())
        md = it["metadata"]
        assert "organismos_competentes" in md
        assert isinstance(md["organismos_competentes"], list)
        assert len(md["organismos_competentes"]) >= 1
        for org in md["organismos_competentes"]:
            assert org in {"SERNAC", "CMF", "SII"}
        assert "texto_literal" in md
        assert "nombre_ley" in md and "articulo" in md
