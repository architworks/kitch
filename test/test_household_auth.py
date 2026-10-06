import os
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
from app.main import app
from app.sqlite_supabase import SQLiteKitchClient


class HostedSessionTests(unittest.TestCase):
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
        ):
            with TestClient(app) as client:
                signed_in = client.post("/api/auth/google", json={
                    "credential": "credential",
                    "timezone": "Asia/Kolkata",
                })
                self.assertEqual(signed_in.status_code, 200)
                self.assertEqual(signed_in.json()["household"], household)
                self.assertIn("kitch_session=", signed_in.headers["set-cookie"])

                session = client.get("/api/auth/session")
                self.assertEqual(session.status_code, 200)
                self.assertTrue(session.json()["authenticated"])
                self.assertEqual(session.json()["household"]["members"], household["members"])

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
