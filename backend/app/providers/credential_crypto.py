"""Encryption for delegated provider credentials and transient PKCE secrets."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3

from cryptography.fernet import Fernet, InvalidToken


class ProviderCredentialConfigurationError(RuntimeError):
    pass


def _local_path(configured: str) -> Path:
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    return path


def _local_encrypted_records_exist() -> bool:
    database_path = _local_path(
        os.environ.get("KITCH_SQLITE_PATH", ".kitch/kitch.sqlite3")
    )
    if not database_path.exists():
        return False
    try:
        connection = sqlite3.connect(
            f"file:{database_path}?mode=ro", uri=True, timeout=2
        )
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name IN ('provider_connections','provider_oauth_flows')"
                ).fetchall()
            }
            for table in tables:
                if connection.execute(
                    f'SELECT 1 FROM "{table}" LIMIT 1'
                ).fetchone():
                    return True
            return False
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ProviderCredentialConfigurationError(
            "Kitch could not safely inspect local encrypted provider state."
        ) from exc


def _fernet() -> Fernet:
    key = os.environ.get("PROVIDER_CREDENTIAL_ENCRYPTION_KEY", "").strip()
    database_backend = str(
        os.environ.get("KITCH_DATABASE_BACKEND", "supabase") or "supabase"
    ).strip().lower()
    if not key and database_backend == "sqlite":
        configured = os.environ.get(
            "KITCH_LOCAL_PROVIDER_KEY_PATH", ".kitch/provider-credentials.key"
        )
        path = _local_path(configured)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            if _local_encrypted_records_exist():
                raise ProviderCredentialConfigurationError(
                    "The local provider encryption key is missing while encrypted "
                    "provider records still exist. Restore the original key before reconnecting."
                )
            generated = Fernet.generate_key()
            path.write_bytes(generated + b"\n")
            try:
                path.chmod(0o600)
            except OSError:
                pass
        key = path.read_text(encoding="ascii").strip()
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
