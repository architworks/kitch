import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import (
    HouseholdIdentity,
    begin_identity_scope,
    end_identity_scope,
    issue_session,
    read_session,
    verify_google_credential,
)
from app.household_config import canonical_user_name, get_household_profile_id, get_user_id
from app import main
from app.main import app
from app.sqlite_supabase import SQLiteKitchClient


class HostedSessionTests(unittest.TestCase):
    def test_session_check_does_not_initialize_agent_or_checkout_runtime(self):
        backend_dir = Path(__file__).resolve().parents[1] / "backend"
        script = """
import os
import sys
os.environ["KITCH_DATABASE_BACKEND"] = "supabase"
os.environ["KITCH_AUTH_SESSION_SECRET"] = "s" * 40
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    response = client.get("/api/auth/session")
    assert response.status_code == 200, response.text
for module in (
    "app.agent.core",
    "app.agent.memory",
    "app.agent.tools",
    "app.grocery_checkout",
    "google.adk",
):
    assert module not in sys.modules, module
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_cors_preflight_does_not_require_a_household_session(self):
        with patch.dict(os.environ, {
            "KITCH_DATABASE_BACKEND": "supabase",
            "KITCH_AUTH_SESSION_SECRET": "s" * 40,
        }):
            origin = main.allowed_origins[0]
            with TestClient(app) as client:
                response = client.options("/api/chat", headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            origin,
        )

    def test_google_sign_in_returns_complete_household_and_cookie_supports_session_reload(self):
        household = {
            "google_subject": "google-user-1",
            "email": "owner@example.com",
            "household_id": "household-a",
            "owner_profile_id": "owner-a",
            "members": [{"id": "owner-a", "name": "Owner"}],
        }
        claims = {
            "sub": "google-user-1",
            "email": "owner@example.com",
            "email_verified": True,
            "name": "Owner",
        }
        environment = {
            "KITCH_DATABASE_BACKEND": "supabase",
            "KITCH_AUTH_SESSION_SECRET": "s" * 40,
        }
        with patch.dict(os.environ, environment), patch(
            "app.main.verify_google_credential", return_value=claims,
        ), patch(
            "app.main.ensure_google_household", return_value=household,
        ) as ensure_household, patch(
            "app.main.get_legal_consent", return_value={"terms_version": main.LEGAL_TERMS_VERSION},
        ), patch("app.main.get_household_account_context", return_value=household):
            with TestClient(app) as client:
                signed_in = client.post("/api/auth/google", json={
                    "credential": "credential",
                    "timezone": "Asia/Kolkata",
                })
                self.assertEqual(signed_in.status_code, 200)
                self.assertEqual(signed_in.json()["household"], household)
                self.assertFalse(signed_in.json()["consent_required"])
                self.assertIn("kitch_session=", signed_in.headers["set-cookie"])

                session = client.get("/api/auth/session")
                self.assertEqual(session.status_code, 200)
                self.assertTrue(session.json()["authenticated"])
                self.assertEqual(session.json()["household"]["members"], household["members"])
                ensure_household.assert_called_once()

    def _consent_fixtures(self):
        household = {
            "google_subject": "google-user-1",
            "email": "owner@example.com",
            "household_id": "household-a",
            "owner_profile_id": "owner-a",
            "members": [{"id": "owner-a", "name": "Owner"}],
        }
        claims = {"sub": "google-user-1", "email": "owner@example.com", "name": "Owner"}
        environment = {
            "KITCH_DATABASE_BACKEND": "supabase",
            "KITCH_AUTH_SESSION_SECRET": "s" * 40,
        }
        return household, claims, environment

    def test_owner_without_consent_is_gated_until_accepting_the_current_notice(self):
        household, claims, environment = self._consent_fixtures()
        with patch.dict(os.environ, environment), patch(
            "app.main.verify_google_credential", return_value=claims,
        ), patch(
            "app.main.ensure_google_household", return_value=household,
        ), patch("app.main.get_legal_consent", return_value={}), patch(
            "app.main.record_legal_consent", return_value={},
        ) as record, patch("app.main.get_household_account_context", return_value=household):
            with TestClient(app) as client:
                signed_in = client.post("/api/auth/google", json={"credential": "c"})
                self.assertTrue(signed_in.json()["consent_required"])
                record.assert_not_called()

                blocked = client.get("/api/pantry")
                self.assertEqual(blocked.status_code, 403)
                self.assertEqual(blocked.json()["detail"]["code"], "consent_required")
                self.assertTrue(client.get("/api/auth/session").json()["consent_required"])

                incomplete = client.post("/api/legal/consent", json={
                    "version": main.LEGAL_TERMS_VERSION, "accepted": True, "age_confirmed": False,
                })
                self.assertEqual(incomplete.status_code, 422)

                accepted = client.post("/api/legal/consent", json={
                    "version": main.LEGAL_TERMS_VERSION, "accepted": True, "age_confirmed": True,
                })
                self.assertEqual(accepted.status_code, 200)
                record.assert_called_once_with("google-user-1", main.LEGAL_TERMS_VERSION)
                self.assertNotEqual(client.get("/api/pantry").status_code, 403)

    def test_consent_given_at_sign_in_is_recorded_without_a_second_prompt(self):
        household, claims, environment = self._consent_fixtures()
        with patch.dict(os.environ, environment), patch(
            "app.main.verify_google_credential", return_value=claims,
        ), patch(
            "app.main.ensure_google_household", return_value=household,
        ), patch("app.main.record_legal_consent", return_value={}) as record:
            with TestClient(app) as client:
                signed_in = client.post("/api/auth/google", json={
                    "credential": "c",
                    "consent": {"version": main.LEGAL_TERMS_VERSION, "accepted": True, "age_confirmed": True},
                })
                self.assertFalse(signed_in.json()["consent_required"])
                record.assert_called_once()

    def test_account_deletion_removes_household_memory_and_signs_out(self):
        household, claims, environment = self._consent_fixtures()

        class FakeMemory:
            def begin_memory_auth_scope(self, token):
                return None

            def end_memory_auth_scope(self, token):
                pass

            async def purge_household_memory(self, user_id):
                self.user_id = user_id
                return "purged"

        memory = FakeMemory()
        with patch.dict(os.environ, environment), patch(
            "app.main.verify_google_credential", return_value=claims,
        ), patch(
            "app.main.ensure_google_household", return_value=household,
        ), patch("app.main.get_legal_consent", return_value={}), patch(
            "app.main.delete_household_account", return_value=True,
        ) as delete_account, patch(
            "app.main._memory_runtime", return_value=memory,
        ), patch("app.main.provider_registry.get", return_value=object()):
            with TestClient(app) as client:
                client.post("/api/auth/google", json={"credential": "c"})
                deleted = client.delete("/api/account")
                self.assertEqual(deleted.status_code, 200)
                self.assertEqual(deleted.json(), {"deleted": True, "memory": "purged"})
                delete_account.assert_called_once_with("google-user-1")
                self.assertEqual(memory.user_id, "owner-a")
                self.assertFalse(client.get("/api/auth/session").json()["authenticated"])

    def test_invite_link_joins_an_existing_household_as_a_member(self):
        household, claims, environment = self._consent_fixtures()
        joined = {**household, "google_subject": "google-user-2", "email": "friend@example.com",
                  "profile_id": "member-b", "role": "member",
                  "members": household["members"] + [{"id": "member-b", "name": "Friend"}]}
        friend = {"sub": "google-user-2", "email": "friend@example.com", "name": "Friend"}
        with patch.dict(os.environ, environment), patch(
            "app.main.verify_google_credential", return_value=friend,
        ), patch("app.main.ensure_google_household") as ensure_household, patch(
            "app.main.join_household_with_invite", return_value=joined,
        ) as join, patch("app.main.record_legal_consent", return_value={}):
            with TestClient(app) as client:
                signed_in = client.post("/api/auth/google", json={
                    "credential": "c",
                    "join": {"token": "invite-token", "profile_id": None},
                    "consent": {"version": main.LEGAL_TERMS_VERSION, "accepted": True, "age_confirmed": True},
                })
                self.assertEqual(signed_in.status_code, 200)
                self.assertEqual(signed_in.json()["household"]["role"], "member")
                ensure_household.assert_not_called()
                self.assertEqual(join.call_args.args[3], main._invite_hash("invite-token"))

                # Members cannot place orders, connect Swiggy or manage invites.
                self.assertEqual(client.post(
                    "/api/grocery/providers/swiggy_instamart/checkout/place-order", json={},
                ).status_code, 403)
                self.assertEqual(client.post("/api/household/invite").status_code, 403)

    def test_stale_invite_link_explains_itself(self):
        _, claims, environment = self._consent_fixtures()
        with patch.dict(os.environ, environment), patch(
            "app.main.verify_google_credential", return_value=claims,
        ), patch(
            "app.main.join_household_with_invite",
            side_effect=main.HouseholdJoinError("invite_invalid"),
        ), patch("app.main.get_invite_preview", return_value=None):
            with TestClient(app) as client:
                self.assertEqual(client.get("/api/invites/old-token").status_code, 410)
                failed = client.post("/api/auth/google", json={"credential": "c", "join": {"token": "old"}})
                self.assertEqual(failed.status_code, 410)
                self.assertEqual(failed.json()["detail"]["code"], "invite_invalid")

    def test_owner_setup_saves_members_and_headcount(self):
        household, claims, environment = self._consent_fixtures()
        configured = {**household, "setup_completed": True,
                      "members": household["members"] + [{"id": "m2", "name": "Rohan"}]}
        with patch.dict(os.environ, environment), patch(
            "app.main.verify_google_credential", return_value=claims,
        ), patch("app.main.ensure_google_household", return_value={**household, "setup_completed": False}), patch(
            "app.main.get_legal_consent", return_value={"terms_version": main.LEGAL_TERMS_VERSION},
        ), patch("app.main.complete_household_setup", return_value=configured) as setup:
            with TestClient(app) as client:
                client.post("/api/auth/google", json={"credential": "c"})
                saved = client.post("/api/household/setup", json={
                    "owner_name": "Owner", "members": ["Rohan", " "], "household_size": 1,
                })
                self.assertEqual(saved.status_code, 200)
                # Headcount never drops below the people named.
                setup.assert_called_once_with("google-user-1", "Owner", ["Rohan"], 2)
                self.assertTrue(saved.json()["household"]["setup_completed"])

    def test_signed_session_rejects_tampering_and_expiry(self):
        with patch.dict(os.environ, {"KITCH_AUTH_SESSION_SECRET": "s" * 40}):
            token = issue_session({
                "sub": "google-user-1",
                "email": "owner@example.com",
                "name": "Owner",
            })
            self.assertEqual(read_session(token)["sub"], "google-user-1")
            self.assertIsNone(read_session(token + "x"))

            encoded, signature = token.split(".", 1)
            payload = read_session(token)
            self.assertGreater(payload["exp"], int(time.time()))
            self.assertIsNone(read_session(f"{encoded[:-1]}x.{signature}"))

    def test_google_credential_requires_configured_audience_and_verified_email(self):
        claims = {
            "sub": "google-user-1", "email": "owner@example.com",
            "email_verified": True,
        }
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "client-id"}), patch(
            "app.auth.id_token.verify_oauth2_token", return_value=claims,
        ) as verifier:
            self.assertEqual(verify_google_credential("credential"), claims)
            self.assertEqual(verifier.call_args.args[2], "client-id")

        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "client-id"}), patch(
            "app.auth.id_token.verify_oauth2_token",
            return_value={**claims, "email_verified": False},
        ):
            with self.assertRaises(HTTPException) as caught:
                verify_google_credential("credential")
            self.assertEqual(caught.exception.status_code, 401)

    def test_request_identity_cannot_select_an_outside_member(self):
        identity = HouseholdIdentity(
            google_subject="google-user-1",
            email="owner@example.com",
            household_id="household-a",
            owner_profile_id="owner-a",
            members=(
                {"id": "owner-a", "name": "Owner A"},
                {"id": "member-a", "name": "Member A"},
            ),
        )
        token = begin_identity_scope(identity)
        try:
            self.assertEqual(get_household_profile_id(), "owner-a")
            self.assertEqual(get_user_id("Member A"), "member-a")
            self.assertEqual(get_user_id("Member from household B"), "owner-a")
            self.assertEqual(canonical_user_name("Member from household B"), "Owner A")
        finally:
            end_identity_scope(token)


class HouseholdMemberIdentityTests(unittest.TestCase):
    def test_rename_preserves_profile_and_nutrition_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            client = SQLiteKitchClient(os.path.join(directory, "kitch.sqlite3"))
            household = client.bootstrap_household(["Alex", "Sam"], "Asia/Kolkata")
            member = household["members"][1]

            response = (
                client.table("profiles")
                .update({"full_name": "Samantha"})
                .eq("id", member["id"])
                .execute()
            )

            self.assertEqual(response.data[0]["id"], member["id"])
            self.assertEqual(response.data[0]["full_name"], "Samantha")
            target = (
                client.table("nutrition_targets")
                .select("profile_id")
                .eq("profile_id", member["id"])
                .execute()
            )
            self.assertEqual(target.data[0]["profile_id"], member["id"])


if __name__ == "__main__":
    unittest.main()
