"""Encryption for delegated provider credentials and transient PKCE secrets."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class ProviderCredentialConfigurationError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = os.environ.get("PROVIDER_CREDENTIAL_ENCRYPTION_KEY", "").strip()
    if not key:
        raise ProviderCredentialConfigurationError(
            "PROVIDER_CREDENTIAL_ENCRYPTION_KEY is required when delegated provider OAuth is enabled."
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise ProviderCredentialConfigurationError(
            "PROVIDER_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key."
        ) from exc


def validate_provider_credential_encryption() -> None:
    """Fail without reading, returning, or logging any credential value."""
    _fernet()


def encrypt_provider_secret(value: str) -> str:
    if not value:
        raise ValueError("A non-empty provider secret is required.")
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_provider_secret(value: str) -> str:
    if not value:
        raise ValueError("An encrypted provider secret is required.")
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ProviderCredentialConfigurationError(
            "The stored provider credential cannot be decrypted with the configured key."
        ) from exc
