"""Memoria conversacional en memoria con TTL.

CONSULTA es multi-turno: el primer turno responde sin tools, el segundo invoca
tools tras confirmación del usuario. Necesitamos persistir el contexto entre
turnos durante una ventana corta. Persistencia entre reinicios queda fuera del
PoC.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationTurn:
    role: str  # "user" | "assistant"
    content: Any  # str para user, list[ContentBlock] para assistant


@dataclass
class Conversation:
    id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    last_seen: float = field(default_factory=time.monotonic)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationStore:
    """Diccionario thread-safe con expiración por inactividad."""

    def __init__(self, ttl_seconds: int = 1800) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, Conversation] = {}
        self._lock = threading.Lock()

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [
            cid for cid, c in self._data.items() if now - c.last_seen > self._ttl
        ]
        for cid in expired:
            del self._data[cid]

    def get_or_create(self, conversation_id: str | None) -> Conversation:
        with self._lock:
            self._purge_expired()
            if conversation_id and conversation_id in self._data:
                conv = self._data[conversation_id]
                conv.last_seen = time.monotonic()
                return conv
            new_id = conversation_id or str(uuid.uuid4())
            conv = Conversation(id=new_id)
            self._data[new_id] = conv
            return conv

    def append_turn(
        self, conversation_id: str, role: str, content: Any
    ) -> None:
        with self._lock:
            if conversation_id not in self._data:
                return
            self._data[conversation_id].turns.append(
                ConversationTurn(role=role, content=content)
            )
            self._data[conversation_id].last_seen = time.monotonic()

    def reset(self, conversation_id: str) -> None:
        with self._lock:
            self._data.pop(conversation_id, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


__all__ = ["Conversation", "ConversationStore", "ConversationTurn"]
