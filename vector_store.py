"""
Capa 2 — Base vectorial ChromaDB para servicios CMF.

- Embeddings locales con sentence-transformers (multilingual, soporte espanol).
- Filtra antes de ingestar: AMBIGUO, OUT_OF_SCOPE, OIRS, vacios (no aportan al RAG).
- Idempotente: usa upsert. Flag --reset borra y vuelve a crear la coleccion.
- Singleton del modelo SentenceTransformer (carga una sola vez por proceso).
"""
from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).parent
DEFAULT_JSON = ROOT / "cmf_services.json"
DEFAULT_DB = ROOT / "chroma_db"
COLLECTION_NAME = "cmf_servicios"
EMBED_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Etiquetas validas para el RAG (Claude solo filtra por estas)
RAG_INTENCIONES = {"RECLAMO", "CONSULTA", "TRAMITE"}


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL_NAME)


def get_embedding(text: str) -> list[float]:
    return _get_model().encode(text, normalize_embeddings=False).tolist()


@lru_cache(maxsize=1)
def _get_client() -> chromadb.api.ClientAPI:
    return chromadb.PersistentClient(
        path=str(DEFAULT_DB),
        settings=Settings(anonymized_telemetry=False),
    )


def _get_or_create_collection():
    client = _get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection() -> None:
    client = _get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Coleccion '{COLLECTION_NAME}' eliminada.")
    except Exception:
        print(f"Coleccion '{COLLECTION_NAME}' no existia.")


def ingest_services(json_path: Path = DEFAULT_JSON) -> int:
    """Ingesta los servicios CMF al store vectorial. Retorna numero ingestado."""
    collection = _get_or_create_collection()
    services = json.loads(json_path.read_text(encoding="utf-8"))

    valid = [
        s for s in services
        if s["metadata"].get("intencion") in RAG_INTENCIONES
        and len(s.get("document", "").strip()) >= 50
    ]
    print(f"Ingestando {len(valid)}/{len(services)} servicios validos...")

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    embeddings: list[list[float]] = []

    for s in valid:
        ids.append(s["id"])
        documents.append(s["document"])
        # Chroma exige escalares en metadata; nuestros campos ya lo son.
        metadatas.append(s["metadata"])
        embeddings.append(get_embedding(s["document"]))
        print(f"  + {s['id']} | {s['metadata']['intencion']:8s} | {s['metadata']['titulo'][:60]}")

    if ids:
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    total = collection.count()
    print(f"\nIngesta completa: {total} documentos en ChromaDB ({COLLECTION_NAME})")
    return total


def search_services(query: str, intencion: str, n_results: int = 3) -> list[dict[str, Any]]:
    """Busqueda semantica con metadata filter por intencion."""
    if intencion not in RAG_INTENCIONES:
        return []
    collection = _get_or_create_collection()
    query_embedding = get_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"intencion": intencion},
        include=["documents", "metadatas", "distances"],
    )

    out: list[dict[str, Any]] = []
    if not results["ids"] or not results["ids"][0]:
        return out

    for i in range(len(results["ids"][0])):
        out.append({
            "id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "similarity": 1.0 - float(results["distances"][0][i]),
        })
    return out


def get_service_by_id(service_id: str) -> dict[str, Any] | None:
    collection = _get_or_create_collection()
    res = collection.get(ids=[service_id], include=["documents", "metadatas"])
    if not res["ids"]:
        return None
    return {
        "id": res["ids"][0],
        "document": res["documents"][0],
        "metadata": res["metadatas"][0],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Vector store CMF (ChromaDB)")
    parser.add_argument("--reset", action="store_true", help="Borrar la coleccion antes de ingestar")
    args = parser.parse_args()

    if args.reset:
        reset_collection()

    ingest_services()


if __name__ == "__main__":
    main()
