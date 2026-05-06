"""Middleware HTTP que aplica rate limit por IP en cada request entrante."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.services.rate_limiter import RateLimiter, RateLimitExceeded

# Rutas exentas (health/metrics/docs deben responder siempre).
_EXEMPT_PREFIXES = ("/health", "/docs", "/openapi", "/redoc")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Aplica scopes ``ip-min`` e ``ip-day`` antes del routing."""

    def __init__(self, app: object, limiter: RateLimiter) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._limiter = limiter

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if any(request.url.path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)
        try:
            self._limiter.check_ip(_client_ip(request))
        except RateLimitExceeded as exc:
            retry = max(1, int(exc.retry_after_s))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "rate limit exceeded",
                    "scope": exc.scope,
                    "retry_after_s": retry,
                },
                headers={"Retry-After": str(retry)},
            )
        return await call_next(request)


__all__ = ["RateLimitMiddleware"]
