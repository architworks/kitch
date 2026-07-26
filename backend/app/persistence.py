"""Safe persistence configuration, errors, and request-scope failure tracking."""

from __future__ import annotations

import base64
import json
import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Mapping


logger = logging.getLogger("kitch.persistence")

PERSISTENCE_MESSAGE = (
    "Kitch could not access durable storage. No changes were saved."
)


class PersistenceConfigurationError(RuntimeError):
    """Raised when durable storage cannot be configured safely."""


@dataclass
class PersistenceError(RuntimeError):
    """A safe, structured failure from durable storage."""

    operation: str
    table: str
    supabase_code: str = "unknown"
    retryable: bool = True

    def __post_init__(self) -> None:
        RuntimeError.__init__(
            self,
            f"Persistence operation {self.operation!r} failed on {self.table!r} "
            f"({self.supabase_code}).",
        )

    def public_detail(self) -> dict[str, Any]:
        return {
            "code": "persistence_unavailable",
            "message": PERSISTENCE_MESSAGE,
            "operation": self.operation,
            "retryable": self.retryable,
        }


_request_failures: ContextVar[list[PersistenceError] | None] = ContextVar(
    "kitch_persistence_failures",
    default=None,
)


def begin_persistence_scope() -> Token:
    """Start tracking persistence failures for one API request."""
    return _request_failures.set([])


def end_persistence_scope(token: Token) -> None:
    _request_failures.reset(token)


def record_persistence_failure(error: PersistenceError) -> None:
    failures = _request_failures.get()
    if failures is not None:
        failures.append(error)


def raise_recorded_persistence_failure() -> None:
    """Fail the request even if an agent framework swallowed a tool exception."""
    failures = _request_failures.get()
    if failures:
        raise failures[0]


def _decode_legacy_jwt_role(key: str) -> str | None:
    parts = key.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + ("=" * (-len(parts[1]) % 4))
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    role = data.get("role")
    return role if isinstance(role, str) else None


def resolve_supabase_credentials(
    environ: Mapping[str, str],
) -> tuple[str, str, str]:
    """Return URL, elevated key, and key type without exposing the credential."""
    url = str(environ.get("SUPABASE_URL") or "").strip()
    ambiguous_key = str(environ.get("SUPABASE_KEY") or "").strip()
    secret_key = str(environ.get("SUPABASE_SECRET_KEY") or "").strip()
    service_role_key = str(
        environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    ).strip()

    if ambiguous_key:
        raise PersistenceConfigurationError(
            "SUPABASE_KEY is no longer accepted. Set SUPABASE_SECRET_KEY "
            "(preferred) or SUPABASE_SERVICE_ROLE_KEY (temporary legacy support)."
        )
    if not url:
        raise PersistenceConfigurationError("SUPABASE_URL is required.")
    if secret_key and service_role_key:
        raise PersistenceConfigurationError(
            "Set only one of SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY."
        )

    key = secret_key or service_role_key
    if not key:
        raise PersistenceConfigurationError(
            "An elevated Supabase backend credential is required. Set "
            "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY."
        )

    if key.startswith("sb_publishable_"):
        raise PersistenceConfigurationError(
            "A Supabase publishable key cannot be used by the backend."
        )
    if key.startswith("sb_secret_"):
        if not secret_key:
            raise PersistenceConfigurationError(
                "Store sb_secret_ credentials in SUPABASE_SECRET_KEY."
            )
        if len(key) < 24 or any(
            marker in key.lower()
            for marker in ("redacted", "your-", "example", "placeholder")
        ):
            raise PersistenceConfigurationError(
                "The configured Supabase secret key is malformed or redacted."
            )
        return url, key, "secret"

    role = _decode_legacy_jwt_role(key)
    if role == "anon":
        raise PersistenceConfigurationError(
            "A legacy Supabase anon key cannot be used by the backend."
        )
    if role != "service_role":
        raise PersistenceConfigurationError(
            "The configured Supabase credential is malformed or is not elevated."
        )
    if not service_role_key:
        raise PersistenceConfigurationError(
            "Store the legacy service_role JWT in SUPABASE_SERVICE_ROLE_KEY."
        )
    return url, key, "service_role"


def persistence_error_from_exception(
    operation: str,
    table: str,
    error: Exception,
) -> PersistenceError:
    """Convert a provider exception to a safe error without leaking its payload."""
    code = getattr(error, "code", None)
    if not code:
        error_dict = getattr(error, "json", None)
        if isinstance(error_dict, dict):
            code = error_dict.get("code")
    code = str(code or type(error).__name__ or "unknown")

    non_retryable_codes = {
        "42501",
        "PGRST204",
        "PGRST205",
        "invalid_persistence_response",
    }
    wrapped = PersistenceError(
        operation=operation,
        table=table,
        supabase_code=code,
        retryable=code not in non_retryable_codes,
    )
    record_persistence_failure(wrapped)
    logger.error(
        "Durable storage operation failed: operation=%s table=%s code=%s retryable=%s",
        wrapped.operation,
        wrapped.table,
        wrapped.supabase_code,
        wrapped.retryable,
    )
    return wrapped


def malformed_persistence_response(
    operation: str,
    table: str,
) -> PersistenceError:
    error = PersistenceError(
        operation=operation,
        table=table,
        supabase_code="invalid_persistence_response",
        retryable=False,
    )
    record_persistence_failure(error)
    logger.error(
        "Durable storage returned an invalid response: operation=%s table=%s",
        operation,
        table,
    )
    return error
