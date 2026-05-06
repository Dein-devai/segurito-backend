"""Tests para InteractionRepository (SQLite)."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.repository import InteractionRepository


@pytest.fixture
def repo(tmp_path: Path) -> InteractionRepository:
    return InteractionRepository(tmp_path / "test.db")


def _save_one(
    repo: InteractionRepository,
    *,
    iid: str = "i1",
    organismo: str = "cmf",
    intencion: str = "RECLAMO",
) -> None:
    repo.save_interaction(
        interaction_id=iid,
        conversation_id="c1",
        user_message="hola",
        response="ok",
        organismo=organismo,
        intencion=intencion,
        servicio_id="art-1",
        iterations=1,
        elapsed_ms=10,
        tools_used=[{"name": "buscar_servicios_cmf", "input": {}}],
    )


def test_save_and_pending(repo: InteractionRepository) -> None:
    _save_one(repo)
    pending = repo.pending_feedback()
    assert len(pending) == 1
    assert pending[0]["id"] == "i1"


def test_save_feedback_marks_as_no_longer_pending(repo: InteractionRepository) -> None:
    _save_one(repo)
    assert repo.save_feedback("i1", helpful=True, comment=None) is True
    assert repo.pending_feedback() == []


def test_save_feedback_unknown_interaction(repo: InteractionRepository) -> None:
    assert repo.save_feedback("ghost", helpful=True, comment=None) is False


def test_metrics_aggregates_correctly(repo: InteractionRepository) -> None:
    _save_one(repo, iid="i1", organismo="cmf", intencion="RECLAMO")
    _save_one(repo, iid="i2", organismo="cmf", intencion="CONSULTA")
    _save_one(repo, iid="i3", organismo="sernac", intencion="RECLAMO")
    repo.save_feedback("i1", helpful=True, comment="ok")
    repo.save_feedback("i2", helpful=False, comment=None)

    m = repo.metrics()
    assert m["total_interactions"] == 3
    assert m["by_organismo"]["cmf"] == 2
    assert m["by_organismo"]["sernac"] == 1
    assert m["by_intencion"]["RECLAMO"] == 2
    assert m["feedback_helpful_rate"] == 0.5


def test_metrics_sin_feedback_returns_none_rate(
    repo: InteractionRepository,
) -> None:
    _save_one(repo)
    assert repo.metrics()["feedback_helpful_rate"] is None
