"""Inicializa Supabase: aplica migración pgvector + ingesta corpus.

Uso (ejecutar UNA vez localmente, con env vars seteadas):

    $env:SUPABASE_DB_URL="postgresql://postgres:<PASS>@db.<ref>.supabase.co:5432/postgres"
    $env:VOYAGE_API_KEY="<voyage-key>"
    python scripts/bootstrap_supabase.py
"""
from __future__ import annotations

from pathlib import Path

import psycopg

from backend.plugins.cmf import CmfPlugin, VALID_INTENCIONES_CMF
from backend.plugins.legal import LegalCorpusPlugin
from backend.settings import get_settings


def apply_migration() -> None:
    sql = Path("migrations/001_pgvector.sql").read_text(encoding="utf-8")
    url = get_settings().supabase_db_url
    if not url:
        raise SystemExit("SUPABASE_DB_URL no está seteada")
    print("applying migration...")
    with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql)
    print("migration ok")


def ingest_corpus() -> None:
    data_dir = get_settings().data_dir
    cmf = CmfPlugin(data_path=data_dir / "cmf" / "services.json")
    legal = LegalCorpusPlugin(data_path=data_dir / "legal" / "articulos.json")

    if cmf.data_path.exists():
        print(f"ingesting CMF from {cmf.data_path}...")
        n = cmf.store.ingest_from_json(
            cmf.data_path,
            intencion_field="intencion",
            valid_intenciones=VALID_INTENCIONES_CMF,
        )
        print(f"  -> {n} items in {cmf.collection_name}")

    if legal.data_path.exists():
        print(f"ingesting LEGAL from {legal.data_path}...")
        n = legal.store.ingest_from_json(legal.data_path, intencion_field=None)
        print(f"  -> {n} items in {legal.collection_name}")


if __name__ == "__main__":
    apply_migration()
    ingest_corpus()
    print("done")
