"""Rate limiter token-bucket multi-scope.

Diseño:
- ``TokenBucket`` puro (sin I/O): refill por segundo, ``try_consume`` atómico.
- ``RateLimiter`` agrupa buckets por *scope+key*. Scopes pre-configurados a
  partir de ``Settings`` para los 5 niveles del PoC:

  1. ``ip-min``         → ``rate_limit_per_ip_per_min``
  2. ``ip-day``         → ``rate_limit_per_ip_per_day``
  3. ``conv-hour``      → ``rate_limit_per_conversation_per_hour``
  4. ``model-min``      → uno por modelo (sonnet, opus globales)
  5. ``opus-conv``      → ``rate_limit_opus_per_conversation``

Si un scope se agota se levanta ``RateLimitExceeded`` con ``retry_after_s``.
In-memory, thread-safe. Para producción → Redis con la misma API.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from backend.settings import Settings


class RateLimitExceeded(Exception):  # noqa: N818 — nombre del dominio, no del patrón Error
    """Se excedió un límite. ``retry_after_s`` orienta al cliente."""

    def __init__(self, scope: str, key: str, retry_after_s: float) -> None:
        super().__init__(f"rate limit exceeded scope={scope} key={key}")
        self.scope = scope
        self.key = key
        self.retry_after_s = retry_after_s


@dataclass
class _Bucket:
    capacity: float
    refill_per_s: float
    tokens: float
    last: float


class TokenBucket:
    """Token-bucket clásico, thread-safe."""

    def __init__(self, capacity: int, refill_per_s: float) -> None:
        if capacity <= 0 or refill_per_s <= 0:
            raise ValueError("capacity y refill_per_s deben ser > 0")
        self._b = _Bucket(
            capacity=float(capacity),
            refill_per_s=float(refill_per_s),
            tokens=float(capacity),
            last=time.monotonic(),
        )
        self._lock = Lock()

    def try_consume(self, n: float = 1.0) -> tuple[bool, float]:
        """Intenta consumir ``n`` tokens. Devuelve (ok, retry_after_s)."""
        with self._lock:
            now = time.monotonic()
            elapsed = max(0.0, now - self._b.last)
            self._b.tokens = min(
                self._b.capacity, self._b.tokens + elapsed * self._b.refill_per_s
            )
            self._b.last = now
            if self._b.tokens >= n:
                self._b.tokens -= n
                return True, 0.0
            missing = n - self._b.tokens
            retry = missing / self._b.refill_per_s
            return False, retry

    @property
    def tokens(self) -> float:
        with self._lock:
            return self._b.tokens


class RateLimiter:
    """Multi-scope: cada (scope, key) tiene su propio bucket lazy."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._buckets: dict[tuple[str, str], TokenBucket] = {}
        self._lock = Lock()

    # --- factory por scope ---------------------------------------------

    def _config(self, scope: str) -> tuple[int, float]:
        s = self._settings
        if scope == "ip-min":
            return s.rate_limit_per_ip_per_min, s.rate_limit_per_ip_per_min / 60.0
        if scope == "ip-day":
            return s.rate_limit_per_ip_per_day, s.rate_limit_per_ip_per_day / 86_400.0
        if scope == "conv-hour":
            return (
                s.rate_limit_per_conversation_per_hour,
                s.rate_limit_per_conversation_per_hour / 3600.0,
            )
        if scope == "model-min:claude-sonnet-4-5":
            return s.rate_limit_sonnet_per_min, s.rate_limit_sonnet_per_min / 60.0
        if scope == "model-min:claude-opus-4-6":
            return (
                s.rate_limit_opus_per_min_global,
                s.rate_limit_opus_per_min_global / 60.0,
            )
        if scope == "opus-conv":
            return (
                s.rate_limit_opus_per_conversation,
                s.rate_limit_opus_per_conversation / 3600.0,
            )
        raise ValueError(f"scope desconocido: {scope}")

    def _bucket(self, scope: str, key: str) -> TokenBucket | None:
        try:
            cap, refill = self._config(scope)
        except ValueError:
            # Modelos sin rate limit configurado (ej: haiku) → no limitamos.
            return None
        if cap <= 0:
            return None
        with self._lock:
            existing = self._buckets.get((scope, key))
            if existing is not None:
                return existing
            bucket = TokenBucket(capacity=cap, refill_per_s=refill)
            self._buckets[(scope, key)] = bucket
            return bucket

    # --- API pública ---------------------------------------------------

    def check(self, scope: str, key: str) -> None:
        """Consume 1 token o levanta RateLimitExceeded."""
        bucket = self._bucket(scope, key)
        if bucket is None:
            return
        ok, retry = bucket.try_consume(1.0)
        if not ok:
            raise RateLimitExceeded(scope=scope, key=key, retry_after_s=retry)

    def check_model(self, model: str, conversation_id: str | None = None) -> None:
        """Aplica límites globales por modelo + per-conv para Opus."""
        self.check(f"model-min:{model}", "global")
        if model == self._settings.model_escalation and conversation_id:
            self.check("opus-conv", conversation_id)

    def check_ip(self, ip: str) -> None:
        self.check("ip-min", ip)
        self.check("ip-day", ip)

    def check_conversation(self, conversation_id: str) -> None:
        self.check("conv-hour", conversation_id)


__all__ = ["RateLimitExceeded", "RateLimiter", "TokenBucket"]
