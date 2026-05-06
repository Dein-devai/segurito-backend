"""Tests integración FastAPI con dependencias overrides."""
from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock

import anthropic
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.dependencies import get_anthropic_dep, reset_dependencies
from backend.settings import Settings


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    reset_dependencies()
    app = create_app(Settings())

    fake = MagicMock()
    fake.messages.create.return_value = MagicMock(
        content=[anthropic.types.TextBlock(text="ok", type="text", citations=None)],
        stop_reason="end_turn",
    )
    app.dependency_overrides[get_anthropic_dep] = lambda: fake

    with TestClient(app) as c:
        yield c
    reset_dependencies()


def test_health_endpoint(app_client: TestClient) -> None:
    r = app_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "cmf" in body["organismos"]
    assert body["prompt_version"]


def test_metrics_endpoint_vacio(app_client: TestClient) -> None:
    r = app_client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["total_interactions"] == 0


def test_chat_endpoint_responde_y_persiste(app_client: TestClient) -> None:
    r = app_client.post("/chat", json={"message": "hola"})
    assert r.status_code == 200
    body = r.json()
    assert body["response"] == "ok"
    assert body["conversation_id"]
    assert body["interaction_id"]

    # Métrica refleja la interacción.
    m = app_client.get("/metrics").json()
    assert m["total_interactions"] == 1


def test_chat_endpoint_rechaza_mensaje_largo(app_client: TestClient) -> None:
    r = app_client.post("/chat", json={"message": "x" * 5000})
    assert r.status_code == 422


def test_feedback_endpoint(app_client: TestClient) -> None:
    r = app_client.post("/chat", json={"message": "hola"})
    iid = r.json()["interaction_id"]

    fb = app_client.post(
        "/feedback",
        json={"interaction_id": iid, "helpful": True, "comment": None},
    )
    assert fb.status_code == 200
    assert fb.json()["ok"] is True


def test_feedback_404_si_no_existe(app_client: TestClient) -> None:
    r = app_client.post(
        "/feedback",
        json={"interaction_id": "ghost", "helpful": True, "comment": None},
    )
    assert r.status_code == 404
