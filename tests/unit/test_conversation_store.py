"""Tests para ConversationStore."""
from __future__ import annotations

import time

from backend.services.conversation_store import ConversationStore


def test_get_or_create_genera_id_si_no_se_pasa() -> None:
    store = ConversationStore(ttl_seconds=60)
    conv = store.get_or_create(None)
    assert conv.id
    assert len(store) == 1


def test_get_or_create_devuelve_existente() -> None:
    store = ConversationStore(ttl_seconds=60)
    a = store.get_or_create(None)
    b = store.get_or_create(a.id)
    assert a.id == b.id
    assert len(store) == 1


def test_append_turn_persiste_historial() -> None:
    store = ConversationStore(ttl_seconds=60)
    conv = store.get_or_create(None)
    store.append_turn(conv.id, "user", "hola")
    store.append_turn(conv.id, "assistant", "buenas")
    again = store.get_or_create(conv.id)
    assert len(again.turns) == 2
    assert again.turns[0].content == "hola"


def test_ttl_expira_conversaciones(monkeypatch) -> None:
    store = ConversationStore(ttl_seconds=1)
    conv = store.get_or_create(None)
    # forzamos last_seen al pasado
    store._data[conv.id].last_seen = time.monotonic() - 10
    new = store.get_or_create(None)
    assert new.id != conv.id
    assert conv.id not in store._data


def test_reset_borra_conversacion() -> None:
    store = ConversationStore(ttl_seconds=60)
    conv = store.get_or_create(None)
    store.reset(conv.id)
    assert len(store) == 0
