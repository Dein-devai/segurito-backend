"""VectorStore parametrizado por colección.

Reemplaza el `vector_store.py` original que tenía la colección hardcoded.
Cada organismo tiene su propia instancia (su propia colección Chroma).

Patrón: el embedder y el cliente Chroma son singletons del proceso, pero la
colección se identifica por nombre.

Embeddings: usamos ``DefaultEmbeddingFunction`` de ChromaDB (ONNX MiniLM-L6).
Es ligero (~80MB), no requiere PyTorch y permite que el deploy quepa en planes
free de 512MB. Reemplazó al modelo paraphrase-multilingual-MiniLM-L12-v2 que
arrastraba ~500MB de RAM y mataba el proceso por OOM.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.core.models import ServiceItem
from backend.logging_setup import get_logger
from backend.settings import get_settings

if TYPE_CHECKING:
    import chromadb

log = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_embedding_function() -> Any:
    """Embedding function compartida del proceso (ONNX, sin PyTorch)."""
    from chromadb.utils import embedding_functions

    log.info("using ChromaDB DefaultEmbeddingFunction (ONNX MiniLM-L6)")
    return embedding_functions.DefaultEmbeddingFunction()


@lru_cache(maxsize=1)
def _get_chroma_client() -> chromadb.api.ClientAPI:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    path = get_settings().chroma_db_path
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _embed(text: str) -> list[float]:
    """Embedding para un único texto. Mantenido por compatibilidad."""
    ef = _get_embedding_function()
    return list(ef([text])[0])


class VectorStore:
    """Una instancia por colección (= por organismo).

    No se carga al construirse; la colección se materializa de forma lazy
    en la primera operación. Esto permite construir VectorStore en tests
    sin tocar Chroma.
    """

    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        self._collection: Any | None = None

    def _collection_handle(self) -> Any:
        if self._collection is None:
            client = _get_chroma_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=_get_embedding_function(),
            )
        return self._collection

    def reset(self) -> None:
        """Elimina la colección. Idempotente."""
        client = _get_chroma_client()
        try:
            client.delete_collection(self.collection_name)
            log.info("collection %s deleted", self.collection_name)
        except Exception:  # noqa: BLE001
            log.info("collection %s did not exist", self.collection_name)
        self._collection = None

    def ingest(
        self,
        items: list[dict[str, Any]],
        *,
        intencion_field: str | None = "intencion",
        valid_intenciones: tuple[str, ...] = ("RECLAMO", "CONSULTA", "TRAMITE"),
        min_doc_chars: int = 50,
    ) -> int:
        """Ingesta items en formato {id, document, metadata}.

        Filtra por longitud. Si ``intencion_field`` es None, no aplica
        filtro por intención (útil para corpus sin taxonomía de intención,
        como el corpus legal). Idempotente (upsert).
        """
        if intencion_field is None:
            valid = [
                it for it in items
                if len(it.get("document", "").strip()) >= min_doc_chars
            ]
        else:
            valid = [
                it for it in items
                if it["metadata"].get(intencion_field) in valid_intenciones
                and len(it.get("document", "").strip()) >= min_doc_chars
            ]
        log.info(
            "ingesting %d/%d items into %s",
            len(valid), len(items), self.collection_name,
        )

        if not valid:
            return int(self._collection_handle().count())

        ids = [it["id"] for it in valid]
        documents = [it["document"] for it in valid]
        metadatas = [it["metadata"] for it in valid]

        # La embedding_function de la colección calcula los vectores.
        self._collection_handle().upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        return int(self._collection_handle().count())

    def ingest_from_json(self, path: Path, **kwargs: Any) -> int:
        """Lee items de un archivo JSON y los ingesta."""
        items = json.loads(path.read_text(encoding="utf-8"))
        return self.ingest(items, **kwargs)

    def search(
        self,
        query: str,
        *,
        intencion: str | None = None,
        n_results: int = 3,
    ) -> list[ServiceItem]:
        """Búsqueda semántica con filtro opcional por intención."""
        if not query.strip():
            return []

        where = {"intencion": intencion} if intencion else None
        results = self._collection_handle().query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        ids = results.get("ids") or [[]]
        if not ids[0]:
            return []

        out: list[ServiceItem] = []
        for i in range(len(ids[0])):
            out.append(
                ServiceItem(
                    id=ids[0][i],
                    document=results["documents"][0][i],
                    metadata=dict(results["metadatas"][0][i]),
                    similarity=1.0 - float(results["distances"][0][i]),
                )
            )
        return out

    def get(self, service_id: str) -> ServiceItem | None:
        """Retorna un item por id, o None si no existe."""
        res = self._collection_handle().get(
            ids=[service_id],
            include=["documents", "metadatas"],
        )
        if not res["ids"]:
            return None
        return ServiceItem(
            id=res["ids"][0],
            document=res["documents"][0],
            metadata=dict(res["metadatas"][0]),
        )

    def count(self) -> int:
        return int(self._collection_handle().count())
