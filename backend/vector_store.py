"""VectorStore sobre Supabase Postgres + pgvector + Voyage embeddings.

Reemplaza la implementación anterior basada en ChromaDB. Ventajas:
- Sin onnxruntime/torch en el proceso web → footprint <100 MB.
- Persistencia gestionada por Supabase: no hay reindex en cold start.
- Embeddings vía Voyage AI (HTTP), nada en RAM.

Compatibilidad: la clase ``VectorStore`` conserva la interfaz pública usada
por los plugins (search/get/ingest/count/reset). Internamente expone un
``_collection`` con métodos query/get/upsert/count que mimetizan la API de
chromadb.Collection — los tests con MagicMock siguen funcionando sin cambios.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from backend.core.models import ServiceItem
from backend.logging_setup import get_logger
from backend.settings import get_settings

log = get_logger(__name__)


# --- Voyage embeddings -------------------------------------------------------

def _embed_batch(texts: list[str], *, input_type: str = "document") -> list[list[float]]:
    """Calcula embeddings de una lista de textos vía Voyage AI."""
    if not texts:
        return []
    settings = get_settings()
    api_key = settings.voyage_api_key or os.getenv("VOYAGE_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "VOYAGE_API_KEY no configurada. Embeddings RAG no disponibles."
        )
    payload = {
        "input": texts,
        "model": settings.embed_model_name,
        "input_type": input_type,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(settings.voyage_api_url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return [item["embedding"] for item in data["data"]]


def _embed(text: str, *, input_type: str = "query") -> list[float]:
    """Embedding de un único texto. Por defecto modo query."""
    return _embed_batch([text], input_type=input_type)[0]


def _vector_literal(vec: list[float]) -> str:
    """pgvector accepts the textual form '[v1,v2,...]'."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


# --- Postgres pool -----------------------------------------------------------

@lru_cache(maxsize=1)
def _get_pool() -> Any:
    """Pool de conexiones psycopg para Supabase."""
    from psycopg_pool import ConnectionPool

    url = get_settings().supabase_db_url
    if not url:
        raise RuntimeError("SUPABASE_DB_URL no configurada.")
    log.info("opening Supabase pgvector pool")
    pool = ConnectionPool(
        conninfo=url,
        min_size=1,
        max_size=4,
        kwargs={"autocommit": True},
        open=True,
    )
    return pool


# --- Adapter Chroma-like sobre la tabla rag_documents -----------------------

class _PgVectorCollection:
    """Mimetiza la interfaz de chromadb.Collection usada por VectorStore."""

    def __init__(self, name: str) -> None:
        self.name = name

    @staticmethod
    def _where_clause(where: dict | None) -> tuple[str, list[Any]]:
        if not where:
            return "", []
        clauses, params = [], []
        for k, v in where.items():
            clauses.append("metadata->>%s = %s")
            params.extend([k, v])
        return " AND " + " AND ".join(clauses), params

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        embeddings: list[list[float]],
    ) -> None:
        sql = (
            "INSERT INTO rag_documents (collection, id, document, metadata, embedding) "
            "VALUES (%s, %s, %s, %s::jsonb, %s::vector) "
            "ON CONFLICT (collection, id) DO UPDATE SET "
            "  document = EXCLUDED.document, "
            "  metadata = EXCLUDED.metadata, "
            "  embedding = EXCLUDED.embedding"
        )
        with _get_pool().connection() as conn, conn.cursor() as cur:
            for rid, doc, meta, emb in zip(ids, documents, metadatas, embeddings):
                cur.execute(
                    sql,
                    (self.name, rid, doc, json.dumps(meta), _vector_literal(emb)),
                )

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict | None = None,
        include: list[str] | None = None,  # noqa: ARG002
    ) -> dict:
        if not query_embeddings:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        emb_lit = _vector_literal(query_embeddings[0])
        where_sql, where_params = self._where_clause(where)
        sql = (
            "SELECT id, document, metadata, embedding <=> %s::vector AS distance "
            "FROM rag_documents WHERE collection = %s"
            f"{where_sql} "
            "ORDER BY embedding <=> %s::vector "
            "LIMIT %s"
        )
        params: list[Any] = [emb_lit, self.name, *where_params, emb_lit, n_results]
        with _get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        ids = [r[0] for r in rows]
        docs = [r[1] for r in rows]
        metas = [r[2] for r in rows]
        dists = [float(r[3]) for r in rows]
        return {
            "ids": [ids],
            "documents": [docs],
            "metadatas": [metas],
            "distances": [dists],
        }

    def get(
        self,
        *,
        ids: list[str],
        include: list[str] | None = None,  # noqa: ARG002
    ) -> dict:
        if not ids:
            return {"ids": [], "documents": [], "metadatas": []}
        sql = (
            "SELECT id, document, metadata FROM rag_documents "
            "WHERE collection = %s AND id = ANY(%s)"
        )
        with _get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (self.name, ids))
            rows = cur.fetchall()
        return {
            "ids": [r[0] for r in rows],
            "documents": [r[1] for r in rows],
            "metadatas": [r[2] for r in rows],
        }

    def count(self) -> int:
        sql = "SELECT count(*) FROM rag_documents WHERE collection = %s"
        with _get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (self.name,))
            row = cur.fetchone()
        return int(row[0]) if row else 0


# --- VectorStore (interfaz pública) -----------------------------------------

class VectorStore:
    """Una instancia por colección lógica (= por organismo)."""

    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        self._collection: Any | None = None

    def _collection_handle(self) -> Any:
        if self._collection is None:
            self._collection = _PgVectorCollection(self.collection_name)
        return self._collection

    def reset(self) -> None:
        try:
            with _get_pool().connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM rag_documents WHERE collection = %s",
                    (self.collection_name,),
                )
            log.info("collection %s deleted", self.collection_name)
        except Exception as exc:  # noqa: BLE001
            log.warning("collection %s reset failed: %s", self.collection_name, exc)
        self._collection = None

    def ingest(
        self,
        items: list[dict[str, Any]],
        *,
        intencion_field: str | None = "intencion",
        valid_intenciones: tuple[str, ...] = ("RECLAMO", "CONSULTA", "TRAMITE"),
        min_doc_chars: int = 50,
    ) -> int:
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
        embeddings = _embed_batch(documents, input_type="document")

        self._collection_handle().upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return int(self._collection_handle().count())

    def ingest_from_json(self, path: Path, **kwargs: Any) -> int:
        items = json.loads(path.read_text(encoding="utf-8"))
        return self.ingest(items, **kwargs)

    def search(
        self,
        query: str,
        *,
        intencion: str | None = None,
        n_results: int = 3,
    ) -> list[ServiceItem]:
        if not query.strip():
            return []
        where = {"intencion": intencion} if intencion else None
        try:
            results = self._collection_handle().query(
                query_embeddings=[_embed(query, input_type="query")],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("search failed (%s); returning empty", exc)
            return []

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
        try:
            res = self._collection_handle().get(
                ids=[service_id],
                include=["documents", "metadatas"],
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("get failed (%s)", exc)
            return None
        if not res["ids"]:
            return None
        return ServiceItem(
            id=res["ids"][0],
            document=res["documents"][0],
            metadata=dict(res["metadatas"][0]),
        )

    def count(self) -> int:
        try:
            return int(self._collection_handle().count())
        except Exception:  # noqa: BLE001
            return 0
