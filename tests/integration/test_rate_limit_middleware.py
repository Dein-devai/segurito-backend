"""Tests del middleware de rate limit."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SEGURITO_RL_IP_MIN", "2")
    monkeypatch.setenv("SEGURITO_RL_IP_DAY", "1000")
    from backend.api.app import create_app
    from backend.api.dependencies import reset_dependencies
    from backend.settings import get_settings

    get_settings.cache_clear()
    reset_dependencies()
    app = create_app()
    return TestClient(app)


def test_health_exempt_from_rate_limit(client: TestClient) -> None:
    """/health no debe gastar tokens del bucket."""
    for _ in range(5):
        r = client.get("/health")
        assert r.status_code == 200


def test_post_chat_rate_limited_after_capacity(client: TestClient) -> None:
    """/chat por encima del límite → 429 con Retry-After."""
    # Dos requests pasan (capacity=2).
    r1 = client.post("/chat", json={"message": "test 1"})
    r2 = client.post("/chat", json={"message": "test 2"})
    # No nos importa si 1/2 fallan por otras razones (sin api key real),
    # sólo que la 3a sea 429 por rate limit.
    assert r1.status_code in (200, 400, 502, 500)
    assert r2.status_code in (200, 400, 502, 500)

    r3 = client.post("/chat", json={"message": "test 3"})
    assert r3.status_code == 429
    assert "retry_after_s" in r3.json()
    assert r3.headers.get("Retry-After")
