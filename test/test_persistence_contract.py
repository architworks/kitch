"""Regression tests for Kitch's fail-loud durable-storage contract."""

from __future__ import annotations

import base64
import json
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Keep backend/.env from overriding the isolated test credential.
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_SECRET_KEY"] = "sb_secret_unit_test_credential_value"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["SUPABASE_KEY"] = ""

from app.persistence import (  # noqa: E402
    PersistenceConfigurationError,
    PersistenceError,
    begin_persistence_scope,
    end_persistence_scope,
    persistence_error_from_exception,
    raise_recorded_persistence_failure,
    resolve_supabase_credentials,
)
from app import supabase_client  # noqa: E402


def legacy_jwt(role: str) -> str:
    def encoded(value: dict[str, str]) -> str:
        payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    return f"{encoded({'alg': 'HS256'})}.{encoded({'role': role})}.signature"


class FakeResponse:
    def __init__(self, data):
        self.data = data


class ProviderError(Exception):
    def __init__(self, code: str):
        super().__init__("provider payload must not leave the persistence layer")
        self.code = code


class CredentialValidationTests(unittest.TestCase):
    def base_env(self, **updates):
        env = {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SECRET_KEY": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
            "SUPABASE_KEY": "",
        }
        env.update(updates)
        return env

    def test_accepts_preferred_secret_key(self):
        _, _, key_type = resolve_supabase_credentials(
            self.base_env(
                SUPABASE_SECRET_KEY="sb_secret_valid_unit_test_credential"
            )
        )
        self.assertEqual(key_type, "secret")

    def test_accepts_legacy_service_role_key(self):
        _, _, key_type = resolve_supabase_credentials(
            self.base_env(
                SUPABASE_SERVICE_ROLE_KEY=legacy_jwt("service_role")
            )
        )
        self.assertEqual(key_type, "service_role")

    def test_rejects_missing_credential(self):
        with self.assertRaises(PersistenceConfigurationError):
            resolve_supabase_credentials(self.base_env())

    def test_rejects_missing_url(self):
        with self.assertRaises(PersistenceConfigurationError):
            resolve_supabase_credentials(
                self.base_env(
                    SUPABASE_URL="",
                    SUPABASE_SECRET_KEY=(
                        "sb_secret_valid_unit_test_credential"
                    ),
                )
            )

    def test_rejects_multiple_elevated_credentials(self):
        with self.assertRaises(PersistenceConfigurationError):
            resolve_supabase_credentials(
                self.base_env(
                    SUPABASE_SECRET_KEY=(
                        "sb_secret_valid_unit_test_credential"
                    ),
                    SUPABASE_SERVICE_ROLE_KEY=legacy_jwt("service_role"),
                )
            )

    def test_rejects_ambiguous_legacy_variable(self):
        with self.assertRaises(PersistenceConfigurationError):
            resolve_supabase_credentials(
                self.base_env(SUPABASE_KEY="legacy-value")
            )

    def test_rejects_publishable_key(self):
        with self.assertRaises(PersistenceConfigurationError):
            resolve_supabase_credentials(
                self.base_env(SUPABASE_SECRET_KEY="sb_publishable_value")
            )

    def test_rejects_anon_jwt(self):
        with self.assertRaises(PersistenceConfigurationError):
            resolve_supabase_credentials(
                self.base_env(
                    SUPABASE_SERVICE_ROLE_KEY=legacy_jwt("anon")
                )
            )

    def test_rejects_malformed_or_redacted_key(self):
        for value in ("not-a-key", "[REDACTED]", "sb_secret_"):
            with self.subTest(value=value):
                with self.assertRaises(PersistenceConfigurationError):
                    resolve_supabase_credentials(
                        self.base_env(SUPABASE_SERVICE_ROLE_KEY=value)
                    )


class PersistenceFailureTests(unittest.TestCase):
    def test_successful_empty_read_is_valid(self):
        rows = supabase_client._read_rows(
            "empty_read",
            "pantry_stock",
            lambda: FakeResponse([]),
        )
        self.assertEqual(rows, [])

    def test_timeout_is_typed_and_retryable(self):
        with self.assertRaises(PersistenceError) as caught:
            supabase_client._read_rows(
                "get_pantry_stock",
                "pantry_stock",
                lambda: (_ for _ in ()).throw(TimeoutError("timeout")),
            )
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(caught.exception.operation, "get_pantry_stock")

    def test_schema_and_authorization_codes_are_typed(self):
        for code in ("PGRST205", "42501"):
            with self.subTest(code=code):
                error = persistence_error_from_exception(
                    "write_test",
                    "grocery_cart_items",
                    ProviderError(code),
                )
                self.assertEqual(error.supabase_code, code)
                self.assertFalse(error.retryable)

    def test_missing_write_result_is_failure(self):
        with self.assertRaises(PersistenceError) as caught:
            supabase_client._confirmed_row(
                "log_macros",
                "macro_diary",
                lambda: FakeResponse([]),
            )
        self.assertEqual(
            caught.exception.supabase_code,
            "invalid_persistence_response",
        )

    def test_request_scope_rethrows_swallowed_tool_failure(self):
        token = begin_persistence_scope()
        try:
            persistence_error_from_exception(
                "save_recipe_grocery_plan",
                "recipe_grocery_plans",
                TimeoutError("timeout"),
            )
            with self.assertRaises(PersistenceError) as caught:
                raise_recorded_persistence_failure()
            self.assertEqual(
                caught.exception.operation,
                "save_recipe_grocery_plan",
            )
        finally:
            end_persistence_scope(token)

    def test_public_error_body_is_safe_and_stable(self):
        error = PersistenceError(
            operation="save_recipe_grocery_plan",
            table="recipe_grocery_plans",
            supabase_code="42501",
            retryable=False,
        )
        self.assertEqual(
            error.public_detail(),
            {
                "code": "persistence_unavailable",
                "message": (
                    "Kitch could not access durable storage. "
                    "No changes were saved."
                ),
                "operation": "save_recipe_grocery_plan",
                "retryable": False,
            },
        )


class MigrationContractTests(unittest.TestCase):
    def test_security_migration_is_transactional_and_backend_only(self):
        migration = (
            ROOT
            / "backend"
            / "database"
            / "migrations"
            / "20260726_normalize_backend_only_rls_and_atomic_persistence.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("BEGIN;", migration)
        self.assertIn("COMMIT;", migration)
        self.assertIn("ENABLE ROW LEVEL SECURITY", migration)
        self.assertIn("FROM PUBLIC, anon, authenticated", migration)
        self.assertIn("TO service_role", migration)
        self.assertIn(
            "save_recipe_grocery_plan_with_cart",
            migration,
        )
        self.assertIn("replace_planned_grocery_cart", migration)
        self.assertNotIn("auth.uid()", migration)

    def test_bootstrap_schema_matches_backend_only_policy_model(self):
        schema = (
            ROOT / "backend" / "database" / "supabase_schema.sql"
        ).read_text(encoding="utf-8")
        self.assertNotIn("auth.uid()", schema)
        self.assertIn("ENABLE ROW LEVEL SECURITY", schema)
        self.assertIn(
            "save_recipe_grocery_plan_with_cart",
            schema,
        )


if __name__ == "__main__":
    unittest.main()
