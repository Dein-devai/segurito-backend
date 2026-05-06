"""Router de autenticación — Google OAuth opcional.

Se monta solo si `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `JWT_SECRET`
están configurados (ver `backend/api/app.py`).

Flujo:
1. `GET /auth/google/login` → redirige a Google con `state` aleatorio.
2. `GET /auth/google/callback` → intercambia code por tokens, valida id_token,
   set httpOnly cookie con JWT y redirige a `FRONTEND_URL/auth/callback`.
3. `GET /auth/me` → devuelve user actual o 401.
4. `POST /auth/logout` → limpia cookie.
"""
from __future__ import annotations

import json
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from backend.api.dependencies import get_settings_dep
from backend.logging_setup import get_logger
from backend.settings import Settings

log = get_logger(__name__)
router = APIRouter(prefix="/auth")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

JWT_COOKIE = "segurito_jwt"
STATE_COOKIE = "segurito_oauth_state"


# ---------------------------------------------------------------------------
# JWT mini (HS256) — evitamos dependencia extra
# ---------------------------------------------------------------------------


def _b64u_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return urlsafe_b64decode(data + pad)


def _jwt_encode(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64u_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64u_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing = f"{h}.{p}".encode()
    sig = hmac_new(secret.encode(), signing, sha256).digest()
    return f"{h}.{p}.{_b64u_encode(sig)}"


def _jwt_decode(token: str, secret: str) -> dict | None:
    try:
        h, p, s = token.split(".")
        signing = f"{h}.{p}".encode()
        expected = _b64u_encode(hmac_new(secret.encode(), signing, sha256).digest())
        if not compare_digest(expected, s):
            return None
        payload = json.loads(_b64u_decode(p))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:  # noqa: BLE001 — JWT malformed
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cookie_kwargs(settings: Settings, secure: bool | None = None) -> dict:
    """Cookies cross-site (Vercel ↔ Render) requieren SameSite=None + Secure."""
    if secure is None:
        # Si redirect_uri es https → producción → Secure obligatorio.
        secure = settings.oauth_redirect_uri.startswith("https://")
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "none" if secure else "lax",
        "path": "/",
    }


def _redirect_uri(settings: Settings, request: Request) -> str:
    if settings.oauth_redirect_uri:
        return settings.oauth_redirect_uri
    # Fallback dev: usa el host del request.
    return str(request.url_for("google_callback"))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/config")
def auth_config(settings: Settings = Depends(get_settings_dep)) -> dict:
    """Permite al frontend saber si Google OAuth está habilitado."""
    return {
        "google_enabled": bool(
            settings.google_client_id and settings.google_client_secret
        ),
    }


@router.get("/google/login")
def google_login(
    request: Request, settings: Settings = Depends(get_settings_dep)
) -> RedirectResponse:
    if not (settings.google_client_id and settings.google_client_secret):
        raise HTTPException(
            status_code=503,
            detail="Google OAuth no configurado en el backend.",
        )
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": _redirect_uri(settings, request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        **_cookie_kwargs(settings),
    )
    return resp


@router.get("/google/callback", name="google_callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    cookie_state: str | None = Cookie(default=None, alias=STATE_COOKIE),
    settings: Settings = Depends(get_settings_dep),
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail=f"oauth error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code/state")
    if not cookie_state or not compare_digest(state, cookie_state):
        raise HTTPException(status_code=400, detail="state mismatch")

    redirect_uri = _redirect_uri(settings, request)
    try:
        with httpx.Client(timeout=10.0) as client:
            tok = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            tok.raise_for_status()
            access_token = tok.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="no access_token")
            ui = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ui.raise_for_status()
            info = ui.json()
    except httpx.HTTPError as exc:
        log.warning("google oauth failed: %s", exc)
        raise HTTPException(status_code=502, detail="google oauth failed") from exc

    sub = info.get("sub")
    email = info.get("email")
    if not sub or not email:
        raise HTTPException(status_code=400, detail="userinfo incompleto")

    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "name": info.get("name") or email,
        "picture": info.get("picture"),
        "iat": now,
        "exp": now + settings.jwt_ttl_seconds,
    }
    jwt = _jwt_encode(payload, settings.jwt_secret)

    # Redirige al frontend tras setear cookie de sesión.
    target = settings.frontend_url.rstrip("/") + "/auth/callback"
    resp = RedirectResponse(target, status_code=302)
    resp.set_cookie(
        JWT_COOKIE,
        jwt,
        max_age=settings.jwt_ttl_seconds,
        **_cookie_kwargs(settings),
    )
    resp.delete_cookie(STATE_COOKIE, path="/")
    return resp


@router.get("/me")
def me(
    jwt: str | None = Cookie(default=None, alias=JWT_COOKIE),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    if not jwt:
        raise HTTPException(status_code=401, detail="no session")
    payload = _jwt_decode(jwt, settings.jwt_secret)
    if not payload:
        raise HTTPException(status_code=401, detail="invalid session")
    return {
        "id": payload["sub"],
        "email": payload["email"],
        "name": payload.get("name"),
        "picture": payload.get("picture"),
    }


@router.post("/logout")
def logout(
    response: Response, settings: Settings = Depends(get_settings_dep)
) -> dict:
    response.delete_cookie(JWT_COOKIE, path="/")
    return {"ok": True}


def get_current_user_optional(
    jwt: str | None = Cookie(default=None, alias=JWT_COOKIE),
    settings: Settings = Depends(get_settings_dep),
) -> dict | None:
    """Dependencia útil para `/chat`: retorna user o None (anónimo)."""
    if not jwt or not settings.jwt_secret:
        return None
    return _jwt_decode(jwt, settings.jwt_secret)


__all__ = ["router", "get_current_user_optional"]
