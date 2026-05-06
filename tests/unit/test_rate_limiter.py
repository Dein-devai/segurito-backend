"""Tests para backend.services.rate_limiter."""
from __future__ import annotations

import time

import pytest

from backend.services.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    TokenBucket,
)
from backend.settings import Settings


def test_token_bucket_consume_until_empty() -> None:
    b = TokenBucket(capacity=3, refill_per_s=0.1)
    assert b.try_consume()[0] is True
    assert b.try_consume()[0] is True
    assert b.try_consume()[0] is True
    ok, retry = b.try_consume()
    assert ok is False
    assert retry > 0


def test_token_bucket_refills_over_time() -> None:
    b = TokenBucket(capacity=2, refill_per_s=10.0)
    b.try_consume()
    b.try_consume()
    assert b.try_consume()[0] is False
    time.sleep(0.15)  # 0.15s × 10 = 1.5 token
    ok, _ = b.try_consume()
    assert ok is True


def test_token_bucket_invalid_args() -> None:
    with pytest.raises(ValueError):
        TokenBucket(capacity=0, refill_per_s=1.0)
    with pytest.raises(ValueError):
        TokenBucket(capacity=1, refill_per_s=0)


def test_rate_limiter_check_ip_min(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEGURITO_RL_IP_MIN", "2")
    monkeypatch.setenv("SEGURITO_RL_IP_DAY", "1000")
    from backend.settings import get_settings
    get_settings.cache_clear()
    rl = RateLimiter(get_settings())

    rl.check_ip("1.2.3.4")
    rl.check_ip("1.2.3.4")
    with pytest.raises(RateLimitExceeded) as exc:
        rl.check_ip("1.2.3.4")
    assert exc.value.scope in ("ip-min", "ip-day")


def test_rate_limiter_isolates_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEGURITO_RL_IP_MIN", "1")
    monkeypatch.setenv("SEGURITO_RL_IP_DAY", "1000")
    from backend.settings import get_settings
    get_settings.cache_clear()
    rl = RateLimiter(get_settings())

    rl.check_ip("a")
    rl.check_ip("b")  # otra key, no afectada
    with pytest.raises(RateLimitExceeded):
        rl.check_ip("a")


def test_rate_limiter_check_model_opus_per_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEGURITO_RL_OPUS_MIN_GLOBAL", "1000")
    monkeypatch.setenv("SEGURITO_RL_OPUS_CONV", "1")
    from backend.settings import get_settings
    get_settings.cache_clear()
    rl = RateLimiter(get_settings())

    rl.check_model("claude-opus-4-6", conversation_id="conv-1")
    with pytest.raises(RateLimitExceeded) as exc:
        rl.check_model("claude-opus-4-6", conversation_id="conv-1")
    assert exc.value.scope == "opus-conv"


def test_rate_limiter_check_model_haiku_no_limit() -> None:
    """Haiku no tiene scope configurado → no levanta nada."""
    rl = RateLimiter(Settings())
    for _ in range(50):
        rl.check_model("claude-haiku-4-5")


def test_rate_limiter_unknown_scope_raises() -> None:
    rl = RateLimiter(Settings())
    with pytest.raises(ValueError):
        rl._config("scope-fantasma")


def test_rate_limit_exceeded_carries_scope_and_retry() -> None:
    exc = RateLimitExceeded(scope="ip-min", key="1.2.3.4", retry_after_s=12.5)
    assert exc.scope == "ip-min"
    assert exc.key == "1.2.3.4"
    assert exc.retry_after_s == 12.5
    assert "ip-min" in str(exc)
