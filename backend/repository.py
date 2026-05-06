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
    tools_used_json TEXT
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
"""


class InteractionRepository:
    """Persistencia de interacciones + feedback en SQLite."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

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
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO interactions
                (id, conversation_id, ts, user_message, response, organismo,
                 intencion, servicio_id, iterations, elapsed_ms, tools_used_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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


__all__ = ["InteractionRepository"]
