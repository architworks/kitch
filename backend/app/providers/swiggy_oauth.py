"""Household-owned delegated OAuth for Swiggy MCP."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from urllib.parse import urlencode

import httpx

from app.providers.base import ProviderOperationError
from app.providers.credential_crypto import (
    ProviderCredentialConfigurationError,
    decrypt_provider_secret,
    encrypt_provider_secret,
    validate_provider_credential_encryption,
)
from app.supabase_client import (
    consume_provider_oauth_flow,
    create_provider_oauth_flow,
    delete_provider_connection,
    delete_provider_checkout_draft,
    get_provider_connection,
    get_provider_oauth_client,
    save_provider_connection,
    save_provider_oauth_client,
    update_provider_connection_status,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _safe_registration(value: Dict[str, Any]) -> Dict[str, Any]:
    blocked = {"client_secret", "access_token", "refresh_token", "registration_access_token"}
    return {key: child for key, child in value.items() if key not in blocked}


class SwiggyOAuthBroker:
    provider_id = "swiggy_instamart"

    def __init__(self) -> None:
        self.environment = os.environ.get("SWIGGY_INSTAMART_ENV", "local").strip().lower()
        if self.environment not in {"local", "staging", "production"}:
            self.environment = "local"
        default_origin = (
            "https://mcp-staging.swiggy.com"
            if self.environment == "staging"
            else "https://mcp.swiggy.com"
        )
        self.oauth_origin = os.environ.get("SWIGGY_OAUTH_BASE_URL", default_origin).rstrip("/")
        self.redirect_uri = os.environ.get(
            "SWIGGY_OAUTH_REDIRECT_URI",
            "http://localhost:8000/api/grocery/providers/swiggy_instamart/oauth/callback",
        ).strip()
        self.scope = os.environ.get("SWIGGY_OAUTH_SCOPE", "mcp:tools").strip()

    def production_gate_error(self) -> str | None:
        if self.environment != "production":
            return None
        approved = os.environ.get("SWIGGY_INSTAMART_PRODUCTION_APPROVED", "false").lower() in {
            "1", "true", "yes"
        }
        if not approved:
            return "Swiggy Instamart production access has not been approved."
        if not self.redirect_uri.startswith("https://"):
            return "Swiggy production OAuth requires an exact HTTPS callback URI."
        return None

    def connection_status(self) -> Dict[str, Any]:
        gate_error = self.production_gate_error()
        if gate_error:
            return {"state": "gated", "message": gate_error}
        connection = get_provider_connection(self.provider_id, self.environment)
        if not connection:
            return {
                "state": "not_connected",
                "message": "Connect a household Swiggy account to use Instamart.",
            }
        expires_at = _parse_timestamp(connection.get("expires_at"))
        if connection.get("status") != "connected" or not expires_at or expires_at <= _utcnow() + timedelta(seconds=60):
            if connection.get("status") == "connected":
                update_provider_connection_status(
                    self.provider_id,
                    self.environment,
                    "reconnect_required",
                    "token_expired",
                )
            return {
                "state": "reconnect_required",
                "message": "The household Swiggy connection has expired. Reconnect to continue.",
            }
        return {
            "state": "connected",
            "message": "The household Swiggy account is connected.",
            "expires_at": expires_at.isoformat(),
        }

    def access_token(self) -> str:
        status = self.connection_status()
        if status["state"] != "connected":
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="authenticate",
                code="provider_auth_required",
                message=status["message"],
                retryable=False,
                status_code=401,
            )
        connection = get_provider_connection(self.provider_id, self.environment)
        if not connection:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="authenticate",
                code="provider_auth_required",
                message="Connect a household Swiggy account to continue.",
                status_code=401,
            )
        return decrypt_provider_secret(str(connection["access_token_ciphertext"]))

    async def start(self) -> Dict[str, Any]:
        gate_error = self.production_gate_error()
        if gate_error:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="oauth_start",
                code="provider_production_gated",
                message=gate_error,
                status_code=403,
            )
        try:
            validate_provider_credential_encryption()
        except ProviderCredentialConfigurationError as exc:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="oauth_start",
                code="provider_credential_vault_misconfigured",
                message="Kitch's provider credential vault is not configured correctly.",
                retryable=False,
                status_code=503,
            ) from exc
        client = get_provider_oauth_client(self.provider_id, self.environment)
        if not client:
            client = await self._register_client()

        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).decode("ascii").rstrip("=")
        state = secrets.token_urlsafe(32)
        create_provider_oauth_flow(
            {
                "provider": self.provider_id,
                "provider_environment": self.environment,
                "state_hash": hashlib.sha256(state.encode("utf-8")).hexdigest(),
                "code_verifier_ciphertext": encrypt_provider_secret(verifier),
                "client_id": client["client_id"],
                "redirect_uri": self.redirect_uri,
                "expires_at": (_utcnow() + timedelta(minutes=10)).isoformat(),
            }
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client["client_id"],
                "redirect_uri": self.redirect_uri,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
                "scope": self.scope,
            }
        )
        return {"authorization_url": f"{self.oauth_origin}/auth/authorize?{query}"}

    async def complete(self, code: str, state: str) -> Dict[str, Any]:
        if not code or not state:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="oauth_callback",
                code="oauth_callback_invalid",
                message="Swiggy did not return a complete OAuth authorization response.",
                status_code=422,
            )
        flow = consume_provider_oauth_flow(hashlib.sha256(state.encode("utf-8")).hexdigest())
        if not flow:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="oauth_callback",
                code="oauth_state_invalid",
                message="The Swiggy authorization attempt expired or was already used.",
                status_code=403,
            )
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": decrypt_provider_secret(flow["code_verifier_ciphertext"]),
            "redirect_uri": flow["redirect_uri"],
            "client_id": flow["client_id"],
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(f"{self.oauth_origin}/auth/token", json=payload)
                response.raise_for_status()
                token = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="oauth_callback",
                code="oauth_token_exchange_failed",
                message="Kitch could not complete the Swiggy connection.",
                retryable=True,
            ) from exc
        access_token = str(token.get("access_token") or "")
        if not access_token:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="oauth_callback",
                code="oauth_token_missing",
                message="Swiggy did not return an access token.",
            )
        expires_in = max(60, int(token.get("expires_in") or 432000))
        connection = save_provider_connection(
            self.provider_id,
            self.environment,
            {
                "access_token_ciphertext": encrypt_provider_secret(access_token),
                "token_type": token.get("token_type") or "Bearer",
                "scope": token.get("scope") or self.scope,
                "expires_at": (_utcnow() + timedelta(seconds=expires_in)).isoformat(),
                "status": "connected",
            },
        )
        return {
            "state": "connected",
            "provider": self.provider_id,
            "environment": self.environment,
            "expires_at": connection["expires_at"],
        }

    async def disconnect(self) -> None:
        connection = get_provider_connection(self.provider_id, self.environment)
        if connection:
            try:
                token = decrypt_provider_secret(str(connection["access_token_ciphertext"]))
                async with httpx.AsyncClient(timeout=15) as client:
                    await client.post(
                        f"{self.oauth_origin}/auth/logout",
                        headers={"Authorization": f"Bearer {token}"},
                    )
            except Exception:
                pass
            delete_provider_connection(self.provider_id, self.environment)
        if get_provider_checkout_draft_safe(self.provider_id, self.environment):
            delete_provider_checkout_draft(self.provider_id, self.environment)

    async def _register_client(self) -> Dict[str, Any]:
        registration_request = {
            "client_name": os.environ.get("SWIGGY_OAUTH_CLIENT_NAME", "Kitch"),
            "redirect_uris": [self.redirect_uri],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.oauth_origin}/auth/register",
                    json=registration_request,
                )
                response.raise_for_status()
                registration = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="oauth_register",
                code="oauth_registration_failed",
                message="Kitch could not register its Swiggy OAuth callback.",
                retryable=True,
            ) from exc
        client_id = str(registration.get("client_id") or "")
        if not client_id:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="oauth_register",
                code="oauth_client_id_missing",
                message="Swiggy OAuth registration did not return a client ID.",
            )
        return save_provider_oauth_client(
            self.provider_id,
            self.environment,
            client_id,
            _safe_registration(registration),
        )


def get_provider_checkout_draft_safe(provider: str, environment: str) -> Dict[str, Any] | None:
    # Local import avoids expanding the public persistence surface of the broker.
    from app.supabase_client import get_provider_checkout_draft

    return get_provider_checkout_draft(provider, environment)
