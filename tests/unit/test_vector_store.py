"""Tests para backend.vector_store — sin Chroma real, sin descargar modelo.

Se mockea la colección directamente vía el atributo `_collection`. Esto valida
la lógica de filtrado/transformación sin pegarle a infraestructura.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.core.models import ServiceItem
from backend.vector_store import VectorStore


@pytest.fixture
def fake_collection() -> MagicMock:
    """Mock que simula un chromadb Collection."""
    return MagicMock()


@pytest.fixture
def store(fake_collection: MagicMock) -> VectorStore:
    """VectorStore con colección pre-inyectada (no toca Chroma real)."""
    s = VectorStore(collection_name="test_servicios")
    s._collection = fake_collection
    return s


@pytest.fixture(autouse=True)
def stub_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reemplaza _embed por una función trivial — no carga el modelo real."""
    monkeypatch.setattr(
        "backend.vector_store._embed",
        lambda text: [float(len(text))] * 3,
    )


def test_search_returns_empty_on_blank_query(store: VectorStore) -> None:
    assert store.search("   ") == []


def test_search_returns_service_items(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    fake_collection.query.return_value = {
        "ids": [["art-1", "art-2"]],
        "documents": [["doc 1", "doc 2"]],
        "metadatas": [[{"intencion": "RECLAMO"}, {"intencion": "RECLAMO"}]],
        "distances": [[0.1, 0.3]],
    }

    results = store.search("query", intencion="RECLAMO", n_results=2)

    assert len(results) == 2
    assert isinstance(results[0], ServiceItem)
    assert results[0].id == "art-1"
    assert results[0].similarity == pytest.approx(0.9)
    assert results[1].similarity == pytest.approx(0.7)


def test_search_passes_intencion_filter(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    fake_collection.query.return_value = {
        "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
    }

    store.search("q", intencion="TRAMITE")

    call_kwargs = fake_collection.query.call_args.kwargs
    assert call_kwargs["where"] == {"intencion": "TRAMITE"}


def test_search_without_intencion_passes_no_filter(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    fake_collection.query.return_value = {
        "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
    }

    store.search("q")

    assert fake_collection.query.call_args.kwargs["where"] is None


def test_search_returns_empty_when_no_results(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    fake_collection.query.return_value = {
        "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
    }
    assert store.search("nada", intencion="RECLAMO") == []


def test_get_returns_none_for_missing(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    fake_collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
    assert store.get("art-999") is None


def test_get_returns_service_item(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    fake_collection.get.return_value = {
        "ids": ["art-1"],
        "documents": ["doc"],
        "metadatas": [{"k": "v"}],
    }
    item = store.get("art-1")
    assert item is not None
    assert item.id == "art-1"
    assert item.metadata == {"k": "v"}


def test_ingest_filters_invalid_intenciones(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    fake_collection.count.return_value = 1
    items: list[dict[str, Any]] = [
        {
            "id": "a", "document": "x" * 100,
            "metadata": {"intencion": "RECLAMO"},
        },
        {
            "id": "b", "document": "y" * 100,
            "metadata": {"intencion": "OUT_OF_SCOPE"},  # filtrado
        },
        {
            "id": "c", "document": "short",  # filtrado por longitud
            "metadata": {"intencion": "RECLAMO"},
        },
    ]

    store.ingest(items)

    upsert_args = fake_collection.upsert.call_args.kwargs
    assert upsert_args["ids"] == ["a"]


def test_ingest_without_intencion_filter_keeps_all(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    """Cuando intencion_field=None, sólo aplica filtro de longitud."""
    fake_collection.count.return_value = 2
    items: list[dict[str, Any]] = [
        {
            "id": "ley-1",
            "document": "x" * 100,
            "metadata": {"id_ley": "19496"},  # sin campo "intencion"
        },
        {
            "id": "ley-2",
            "document": "y" * 100,
            "metadata": {"id_ley": "21521"},
        },
        {
            "id": "ley-short",
            "document": "short",  # filtrado por longitud
            "metadata": {"id_ley": "18045"},
        },
    ]

    store.ingest(items, intencion_field=None)

    upsert_args = fake_collection.upsert.call_args.kwargs
    assert upsert_args["ids"] == ["ley-1", "ley-2"]


def test_ingest_empty_does_not_upsert(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    fake_collection.count.return_value = 0
    store.ingest([])
    fake_collection.upsert.assert_not_called()


def test_ingest_from_json(
    store: VectorStore, fake_collection: MagicMock, tmp_path
) -> None:
    import json

    fake_collection.count.return_value = 1
    path = tmp_path / "items.json"
    path.write_text(
        json.dumps([
            {
                "id": "a",
                "document": "x" * 100,
                "metadata": {"intencion": "RECLAMO"},
            }
        ]),
        encoding="utf-8",
    )

    store.ingest_from_json(path)
    fake_collection.upsert.assert_called_once()


def test_count_proxies_to_collection(
    store: VectorStore, fake_collection: MagicMock
) -> None:
    fake_collection.count.return_value = 42
    assert store.count() == 42
