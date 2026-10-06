"""Hosted Google authentication and request-scoped household identity."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


SESSION_COOKIE = "kitch_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class HouseholdIdentity:
    google_subject: str
    email: str
    household_id: str
    owner_profile_id: str
    members: tuple[dict[str, str], ...]


_identity: ContextVar[HouseholdIdentity | None] = ContextVar(
    "kitch_household_identity", default=None
)


def auth_required() -> bool:
    return os.environ.get("KITCH_DATABASE_BACKEND", "supabase").strip().lower() == "supabase"


def current_identity() -> HouseholdIdentity | None:
    return _identity.get()


def require_identity() -> HouseholdIdentity:
    identity = current_identity()
    if identity is None:
        raise RuntimeError("Authenticated household identity is unavailable.")
    return identity


def begin_identity_scope(identity: HouseholdIdentity) -> Token:
    return _identity.set(identity)


def end_identity_scope(token: Token) -> None:
    _identity.reset(token)


def _session_secret() -> bytes:
    value = os.environ.get("KITCH_AUTH_SESSION_SECRET", "").strip()
    if len(value) < 32:
        raise RuntimeError("KITCH_AUTH_SESSION_SECRET must contain at least 32 characters.")
    return value.encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_session(claims: dict[str, Any]) -> str:
    now = int(time.time())
    payload = {
        "sub": str(claims["sub"]),
        "email": str(claims.get("email") or ""),
        "name": str(claims.get("name") or "Kitch household"),
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(hmac.new(_session_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def read_session(value: str | None) -> dict[str, Any] | None:
    if not value or "." not in value:
        return None
    encoded, supplied = value.split(".", 1)
    expected = _b64encode(hmac.new(_session_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(supplied, expected):
        return None
    try:
        payload = json.loads(_b64decode(encoded).decode("utf-8"))
        if int(payload.get("exp") or 0) <= int(time.time()):
            return None
        if not payload.get("sub") or not payload.get("email"):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def verify_google_credential(credential: str) -> dict[str, Any]:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    if not client_id:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID is not configured.")
    try:
        claims = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    except Exception as error:
        raise HTTPException(status_code=401, detail={
            "code": "google_sign_in_invalid",
            "message": "Google could not verify this sign-in.",
        }) from error
    if claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail={
            "code": "google_email_unverified",
            "message": "Use a verified Google account to sign in.",
        })
    return claims


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=os.environ.get("VERCEL", "").lower() == "1",
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=os.environ.get("VERCEL", "").lower() == "1",
        samesite="lax",
        path="/",
    )


def session_from_request(request: Request) -> dict[str, Any] | None:
    if not auth_required():
        return None
    return read_session(request.cookies.get(SESSION_COOKIE))

