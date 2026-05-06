"""Repositorio de interacciones.

Patrón Repository: separa la lógica de chat de la persistencia. La PoC arranca
con SQLite (file-based, suficiente para análisis de feedback) y el contrato
permite migrar a Postgres sin tocar el ChatService.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    ts TEXT NOT NULL,
    user_message TEXT NOT NULL,
    response TEXT NOT NULL,
    organismo TEXT,
    intencion TEXT,
    servicio_id TEXT,
    iterations INTEGER NOT NULL DEFAULT 0,
    elapsed_ms INTEGER NOT NULL DEFAULT 0,
    tools_used_json TEXT,
    model_used TEXT,
    total_input_tokens INTEGER NOT NULL DEFAULT 0,
    total_output_tokens INTEGER NOT NULL DEFAULT 0,
    total_cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    total_cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost_usd REAL NOT NULL DEFAULT 0.0,
    reasoning_json TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    interaction_id TEXT PRIMARY KEY,
    helpful INTEGER NOT NULL,
    comment TEXT,
    ts TEXT NOT NULL,
    FOREIGN KEY(interaction_id) REFERENCES interactions(id)
);

CREATE INDEX IF NOT EXISTS idx_interactions_organismo ON interactions(organismo);
CREATE INDEX IF NOT EXISTS idx_interactions_intencion ON interactions(intencion);
CREATE INDEX IF NOT EXISTS idx_interactions_ts ON interactions(ts);
CREATE INDEX IF NOT EXISTS idx_interactions_conv ON interactions(conversation_id);
"""

# Columnas añadidas tras el schema original; se aplican vía ALTER TABLE
# para evitar romper bases de datos en producción.
_ADDITIVE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("model_used", "TEXT"),
    ("total_input_tokens", "INTEGER NOT NULL DEFAULT 0"),
    ("total_output_tokens", "INTEGER NOT NULL DEFAULT 0"),
    ("total_cache_read_tokens", "INTEGER NOT NULL DEFAULT 0"),
    ("total_cache_creation_tokens", "INTEGER NOT NULL DEFAULT 0"),
    ("total_cost_usd", "REAL NOT NULL DEFAULT 0.0"),
    ("reasoning_json", "TEXT"),
    ("error", "TEXT"),
)


class InteractionRepository:
    """Persistencia de interacciones + feedback en SQLite."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            # WAL: lecturas (dashboard) no bloquean escrituras (POST /chat).
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(_SCHEMA)
            self._migrate(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        existing = {
            r["name"] for r in conn.execute("PRAGMA table_info(interactions)")
        }
        for col, ddl in _ADDITIVE_COLUMNS:
            if col not in existing:
                conn.execute(f"ALTER TABLE interactions ADD COLUMN {col} {ddl}")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def checkpoint(self) -> None:
        """Fuerza wal_checkpoint(TRUNCATE) — útil antes de respaldar el .db."""
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def save_interaction(
        self,
        *,
        interaction_id: str,
        conversation_id: str,
        user_message: str,
        response: str,
        organismo: str | None,
        intencion: str | None,
        servicio_id: str | None,
        iterations: int,
        elapsed_ms: int,
        tools_used: list[dict[str, Any]],
        model_used: str | None = None,
        total_input_tokens: int = 0,
        total_output_tokens: int = 0,
        total_cache_read_tokens: int = 0,
        total_cache_creation_tokens: int = 0,
        total_cost_usd: float = 0.0,
        reasoning: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO interactions
                (id, conversation_id, ts, user_message, response, organismo,
                 intencion, servicio_id, iterations, elapsed_ms, tools_used_json,
                 model_used, total_input_tokens, total_output_tokens,
                 total_cache_read_tokens, total_cache_creation_tokens,
                 total_cost_usd, reasoning_json, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    interaction_id,
                    conversation_id,
                    datetime.now(UTC).isoformat(),
                    user_message,
                    response,
                    organismo,
                    intencion,
                    servicio_id,
                    iterations,
                    elapsed_ms,
                    json.dumps(tools_used, ensure_ascii=False),
                    model_used,
                    total_input_tokens,
                    total_output_tokens,
                    total_cache_read_tokens,
                    total_cache_creation_tokens,
                    total_cost_usd,
                    json.dumps(reasoning or [], ensure_ascii=False),
                    error,
                ),
            )

    def save_feedback(
        self, interaction_id: str, helpful: bool, comment: str | None
    ) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM interactions WHERE id = ?", (interaction_id,)
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                """INSERT OR REPLACE INTO feedback
                (interaction_id, helpful, comment, ts) VALUES (?, ?, ?, ?)""",
                (
                    interaction_id,
                    int(helpful),
                    comment,
                    datetime.now(UTC).isoformat(),
                ),
            )
            return True

    def pending_feedback(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT i.* FROM interactions i
                LEFT JOIN feedback f ON f.interaction_id = i.id
                WHERE f.interaction_id IS NULL
                ORDER BY i.ts DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def metrics(self) -> dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM interactions"
            ).fetchone()["n"]
            by_org = {
                r["organismo"] or "unknown": r["n"]
                for r in conn.execute(
                    "SELECT organismo, COUNT(*) AS n FROM interactions "
                    "GROUP BY organismo"
                )
            }
            by_int = {
                r["intencion"] or "unknown": r["n"]
                for r in conn.execute(
                    "SELECT intencion, COUNT(*) AS n FROM interactions "
                    "GROUP BY intencion"
                )
            }
            fb = conn.execute(
                "SELECT COUNT(*) AS n, SUM(helpful) AS yes FROM feedback"
            ).fetchone()
            rate = None
            if fb["n"]:
                rate = float(fb["yes"]) / float(fb["n"])
            return {
                "total_interactions": total,
                "by_organismo": by_org,
                "by_intencion": by_int,
                "feedback_helpful_rate": rate,
            }

    # ---------------------- Admin/Dashboard queries -----------------------
    def list_interactions(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        organismo: str | None = None,
        intencion: str | None = None,
        conversation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if organismo:
            clauses.append("organismo = ?")
            params.append(organismo)
        if intencion:
            clauses.append("intencion = ?")
            params.append(intencion)
        if conversation_id:
            clauses.append("conversation_id = ?")
            params.append(conversation_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT i.*, f.helpful AS feedback_helpful, f.comment AS feedback_comment
            FROM interactions i
            LEFT JOIN feedback f ON f.interaction_id = i.id
            {where}
            ORDER BY i.ts DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_interaction(self, interaction_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT i.*, f.helpful AS feedback_helpful,
                          f.comment AS feedback_comment
                   FROM interactions i
                   LEFT JOIN feedback f ON f.interaction_id = i.id
                   WHERE i.id = ?""",
                (interaction_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT conversation_id,
                          COUNT(*) AS turns,
                          MIN(ts) AS started_at,
                          MAX(ts) AS last_at,
                          SUM(total_cost_usd) AS total_cost_usd,
                          SUM(total_input_tokens) AS total_input_tokens,
                          SUM(total_output_tokens) AS total_output_tokens,
                          AVG(elapsed_ms) AS avg_elapsed_ms,
                          MAX(organismo) AS organismo,
                          MAX(intencion) AS intencion
                   FROM interactions
                   WHERE conversation_id IS NOT NULL
                   GROUP BY conversation_id
                   ORDER BY last_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_conversation_turns(
        self, conversation_id: str
    ) -> list[dict[str, Any]]:
        return self.list_interactions(
            conversation_id=conversation_id, limit=500, offset=0
        )

    def summary(self) -> dict[str, Any]:
        """KPIs para el header del dashboard."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS total,
                          SUM(total_cost_usd) AS cost,
                          AVG(elapsed_ms) AS avg_elapsed,
                          SUM(total_input_tokens) AS in_tok,
                          SUM(total_output_tokens) AS out_tok,
                          SUM(total_cache_read_tokens) AS cache_read,
                          SUM(total_cache_creation_tokens) AS cache_create,
                          COUNT(DISTINCT conversation_id) AS conversations
                   FROM interactions"""
            ).fetchone()
            today = conn.execute(
                """SELECT COUNT(*) AS total,
                          SUM(total_cost_usd) AS cost
                   FROM interactions
                   WHERE substr(ts,1,10) = substr(?,1,10)""",
                (datetime.now(UTC).isoformat(),),
            ).fetchone()
            cache_read = (row["cache_read"] or 0) if row else 0
            in_tok = (row["in_tok"] or 0) if row else 0
            cache_hit_rate = (
                cache_read / (cache_read + in_tok) if (cache_read + in_tok) else 0.0
            )
            return {
                "total_interactions": row["total"] or 0,
                "total_conversations": row["conversations"] or 0,
                "total_cost_usd": float(row["cost"] or 0.0),
                "avg_latency_ms": int(row["avg_elapsed"] or 0),
                "total_input_tokens": int(in_tok),
                "total_output_tokens": int(row["out_tok"] or 0),
                "cache_hit_rate": round(cache_hit_rate, 3),
                "today_interactions": today["total"] or 0,
                "today_cost_usd": float(today["cost"] or 0.0),
            }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for key in ("tools_used_json", "reasoning_json"):
            if key in d and d[key]:
                try:
                    d[key.replace("_json", "")] = json.loads(d[key])
                except (TypeError, ValueError):
                    d[key.replace("_json", "")] = []
            else:
                d[key.replace("_json", "")] = []
            d.pop(key, None)
        return d


__all__ = ["InteractionRepository"]
