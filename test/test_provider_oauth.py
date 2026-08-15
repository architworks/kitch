"""Security tests for household-owned provider OAuth."""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.providers.base import ProviderOperationError  # noqa: E402
from app.providers.credential_crypto import (  # noqa: E402
    decrypt_provider_secret,
    encrypt_provider_secret,
)
from app.providers.swiggy_oauth import SwiggyOAuthBroker  # noqa: E402


class ProviderOAuthTests(unittest.TestCase):
    def setUp(self):
        self.old_env = dict(os.environ)
        os.environ["PROVIDER_CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        os.environ["SWIGGY_INSTAMART_ENV"] = "local"
        os.environ["SWIGGY_OAUTH_REDIRECT_URI"] = (
            "http://localhost:8000/api/grocery/providers/swiggy_instamart/oauth/callback"
        )

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)

    def test_credentials_are_encrypted_and_round_trip(self):
        encrypted = encrypt_provider_secret("provider-token")
        self.assertNotIn("provider-token", encrypted)
        self.assertEqual(decrypt_provider_secret(encrypted), "provider-token")

    def test_pkce_start_stores_only_hashed_state_and_encrypted_verifier(self):
        captured = {}
        with (
            patch("app.providers.swiggy_oauth.get_provider_oauth_client", return_value={"client_id": "client-1"}),
            patch("app.providers.swiggy_oauth.create_provider_oauth_flow", side_effect=lambda value: captured.update(value) or value),
        ):
            result = asyncio.run(SwiggyOAuthBroker().start())
        query = parse_qs(urlparse(result["authorization_url"]).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertNotEqual(query["state"][0], captured["state_hash"])
        self.assertNotIn(query["state"][0], captured["code_verifier_ciphertext"])
        self.assertTrue(decrypt_provider_secret(captured["code_verifier_ciphertext"]))

    def test_expired_connection_requires_reauthentication(self):
        expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        with (
            patch("app.providers.swiggy_oauth.get_provider_connection", return_value={"status": "connected", "expires_at": expired}),
            patch("app.providers.swiggy_oauth.update_provider_connection_status") as update_status,
        ):
            status = SwiggyOAuthBroker().connection_status()
        self.assertEqual(status["state"], "reconnect_required")
        update_status.assert_called_once()

    def test_replayed_or_expired_oauth_state_is_rejected(self):
        with patch("app.providers.swiggy_oauth.consume_provider_oauth_flow", return_value=None):
            with self.assertRaises(ProviderOperationError) as caught:
                asyncio.run(SwiggyOAuthBroker().complete("code", "used-state"))
        self.assertEqual(caught.exception.code, "oauth_state_invalid")

    def test_connection_start_fails_safely_without_credential_vault_key(self):
        os.environ.pop("PROVIDER_CREDENTIAL_ENCRYPTION_KEY", None)
        with self.assertRaises(ProviderOperationError) as caught:
            asyncio.run(SwiggyOAuthBroker().start())
        self.assertEqual(caught.exception.code, "provider_credential_vault_misconfigured")
        self.assertNotIn("Fernet", caught.exception.message)


if __name__ == "__main__":
    unittest.main()
