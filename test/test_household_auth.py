import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

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
            "profile_id": "owner-a",
            "role": "owner",
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
        stored = {"context": household}

        def delete_and_forget(subject):
            stored["context"] = None
            return True

        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", side_effect=lambda subject: stored["context"],
        ), patch(
            "app.main.verify_google_credential", return_value=claims,
        ), patch(
            "app.main.ensure_google_household", return_value=household,
        ), patch("app.main.get_legal_consent", return_value={}), patch(
            "app.main.delete_household_account", side_effect=delete_and_forget,
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
        ) as join, patch("app.main.record_legal_consent", return_value={}), patch(
            "app.main.get_household_account_context", return_value=joined,
        ):
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

    def _member_session(self, environment, member):
        """A browser cookie issued while the account was a household member."""
        with patch.dict(os.environ, environment):
            return issue_session(
                {"sub": member["google_subject"], "email": member["email"], "name": "Friend"},
                member, consent=main.LEGAL_TERMS_VERSION,
            )

    def _member_fixture(self, household):
        return {**household, "google_subject": "google-user-2", "email": "friend@example.com",
                "profile_id": "member-b", "role": "member",
                "members": household["members"] + [{"id": "member-b", "name": "Friend"}]}

    def test_renaming_a_member_cannot_grant_owner_powers(self):
        """Security finding #1: rename + consent used to mint an owner cookie."""
        household, _, environment = self._consent_fixtures()
        member = self._member_fixture(household)
        cookie = self._member_session(environment, member)
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=member,
        ), patch(
            "app.main.update_household_member",
            return_value={"id": "member-b", "full_name": "Friend Renamed"},
        ), patch("app.main.get_household_members", return_value=member["members"]), patch(
            "app.main.record_legal_consent", return_value={},
        ), patch("app.main.set_household_invite") as set_invite:
            with TestClient(app) as client:
                client.cookies.set("kitch_session", cookie)
                renamed = client.patch("/api/household/members/member-b", json={"name": "Friend Renamed"})
                self.assertEqual(renamed.status_code, 200)
                accepted = client.post("/api/legal/consent", json={
                    "version": main.LEGAL_TERMS_VERSION, "accepted": True, "age_confirmed": True,
                })
                self.assertEqual(accepted.status_code, 200)
                self.assertEqual(client.post("/api/household/invite").status_code, 403)
                self.assertEqual(client.delete("/api/household/invite").status_code, 403)
                set_invite.assert_not_called()

    def test_role_comes_from_the_database_not_the_cookie(self):
        """A cookie that claims owner is ignored when the account is a member."""
        household, _, environment = self._consent_fixtures()
        member = self._member_fixture(household)
        forged_owner_cookie = self._member_session(environment, {**member, "role": "owner"})
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=member,
        ), patch("app.main.set_household_invite") as set_invite:
            with TestClient(app) as client:
                client.cookies.set("kitch_session", forged_owner_cookie)
                self.assertEqual(client.post("/api/household/invite").status_code, 403)
                set_invite.assert_not_called()

    def test_cookie_stops_working_after_the_member_leaves(self):
        """Security finding #3: a saved cookie used to keep household access."""
        household, _, environment = self._consent_fixtures()
        member = self._member_fixture(household)
        cookie = self._member_session(environment, member)
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=None,
        ), patch("app.main.ensure_google_household") as ensure_household, patch(
            "app.main.get_pantry_state",
        ) as pantry:
            with TestClient(app) as client:
                client.cookies.set("kitch_session", cookie)
                replay = client.get("/api/pantry")
                self.assertEqual(replay.status_code, 401)
                self.assertEqual(replay.json()["detail"]["code"], "session_revoked")
                consent = client.post("/api/legal/consent", json={
                    "version": main.LEGAL_TERMS_VERSION, "accepted": True, "age_confirmed": True,
                })
                self.assertEqual(consent.status_code, 401)
                pantry.assert_not_called()
                ensure_household.assert_not_called()

                # The app's own session check reports signed-out and clears
                # the stale cookie, so the sign-in screen shows.
                session = client.get("/api/auth/session")
                self.assertEqual(session.status_code, 200)
                self.assertFalse(session.json()["authenticated"])
                self.assertIn('kitch_session=""', session.headers["set-cookie"])

    def test_cookie_follows_the_account_to_its_current_household(self):
        """An account that moved households cannot reach the old one."""
        household, _, environment = self._consent_fixtures()
        member = self._member_fixture(household)
        cookie = self._member_session(environment, member)
        moved = {**member, "household_id": "household-c", "owner_profile_id": "owner-c",
                 "profile_id": "owner-c", "role": "owner",
                 "members": [{"id": "owner-c", "name": "Friend"}]}
        seen = []
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=moved,
        ), patch(
            "app.main.get_pantry_state",
            side_effect=lambda: seen.append(main.require_identity().household_id) or {"items": []},
        ):
            with TestClient(app) as client:
                client.cookies.set("kitch_session", cookie)
                self.assertEqual(client.get("/api/pantry").status_code, 200)
        self.assertEqual(seen, ["household-c"])

    def test_owner_hands_the_household_to_a_signed_in_member(self):
        household, _, environment = self._consent_fixtures()
        member = self._member_fixture(household)
        owner_cookie = self._member_session(environment, {**household, "google_subject": "google-user-1",
                                                          "email": "owner@example.com"})
        owner_context = {**household, "members": member["members"]}
        disconnected = []

        class FakeOAuth:
            async def disconnect(self):
                disconnected.append(True)

        adapter = main.InstamartProviderAdapter.__new__(main.InstamartProviderAdapter)
        adapter.oauth = FakeOAuth()
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=owner_context,
        ), patch("app.main.provider_registry.get", return_value=adapter), patch(
            "app.main.transfer_household_ownership",
            return_value={**owner_context, "role": "member"},
        ) as transfer:
            with TestClient(app) as client:
                client.cookies.set("kitch_session", owner_cookie)
                refused = client.post("/api/household/owner", json={"profile_id": "someone-else"})
                self.assertEqual(refused.status_code, 422)
                handed = client.post("/api/household/owner", json={"profile_id": "member-b"})
                self.assertEqual(handed.status_code, 200)
                self.assertEqual(handed.json()["household"]["role"], "member")
        transfer.assert_called_once_with("google-user-1", "member-b")
        self.assertEqual(disconnected, [True])

    def test_members_cannot_hand_over_ownership(self):
        household, _, environment = self._consent_fixtures()
        member = self._member_fixture(household)
        cookie = self._member_session(environment, member)
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=member,
        ), patch("app.main.transfer_household_ownership") as transfer:
            with TestClient(app) as client:
                client.cookies.set("kitch_session", cookie)
                self.assertEqual(client.post("/api/household/owner", json={"profile_id": "owner-a"}).status_code, 403)
        transfer.assert_not_called()

    def test_owner_removes_a_member_who_joined_by_mistake(self):
        household, _, environment = self._consent_fixtures()
        member = self._member_fixture(household)
        owner_cookie = self._member_session(environment, household)
        owner_context = {**household, "members": member["members"]}
        purged = []

        async def fake_purge(household_id, profile_ids):
            purged.append((household_id, list(profile_ids)))
            return 1

        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=owner_context,
        ), patch(
            "app.main.remove_household_member",
            return_value={"removed_profile_id": "member-b", "had_account": True, "profile_removed": True},
        ) as remove, patch("app.main._purge_agent_state", side_effect=fake_purge):
            with TestClient(app) as client:
                client.cookies.set("kitch_session", owner_cookie)
                removed = client.delete("/api/household/members/member-b")
                self.assertEqual(removed.status_code, 200)
        remove.assert_called_once_with("google-user-1", "member-b")
        self.assertEqual(purged, [("household-a", ["member-b"])])

    def test_ambiguous_nutrition_target_name_is_a_validation_error_not_a_write(self):
        household, _, environment = self._consent_fixtures()
        household = {**household, "members": [
            {"id": "owner-a", "name": "Straße"},
            {"id": "member-b", "name": "Strasse"},
        ]}
        cookie = self._member_session(environment, household)
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=household,
        ), patch("app.main.update_nutrition_targets") as update:
            with TestClient(app, raise_server_exceptions=False) as client:
                client.cookies.set("kitch_session", cookie)
                response = client.patch("/api/nutrition/targets/STRASSE", json={"calories": 2000})
                self.assertEqual(response.status_code, 422)
                self.assertIn("ambiguous", response.json()["detail"])
        update.assert_not_called()

    def test_ambiguous_member_name_in_chat_is_a_validation_error(self):
        household, _, environment = self._consent_fixtures()
        household = {**household, "members": [
            {"id": "owner-a", "name": "Straße"},
            {"id": "member-b", "name": "Strasse"},
        ]}
        cookie = self._member_session(environment, household)
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=household,
        ), patch("app.main.get_household_profile", return_value={"household_size": 2}):
            with TestClient(app, raise_server_exceptions=False) as client:
                client.cookies.set("kitch_session", cookie)
                response = client.post("/api/chat", json={
                    "message": "hi", "active_user": "STRASSE",
                    "planner_context": {"visible_week_start": "", "selected_date": ""},
                    "pantry_stock": [], "grocery_list": [],
                })
                self.assertEqual(response.status_code, 422)

    def _chat_with_tool_responses(self, tool_responses, message="what's in my cart?"):
        """Run one chat turn whose agent returns the given tool responses."""
        from contextlib import ExitStack
        from types import SimpleNamespace

        household, _, environment = self._consent_fixtures()
        cookie = self._member_session(environment, household)

        def event(response=None, final_text=None):
            part = SimpleNamespace(
                function_response=SimpleNamespace(response=response) if response is not None else None,
                text=final_text,
            )
            return SimpleNamespace(
                content=SimpleNamespace(parts=[part]),
                is_final_response=lambda: final_text is not None,
            )

        class Runner:
            async def run_async(self, **_):
                for response in tool_responses:
                    yield event(response=response)
                yield event(final_text="Here you go.")

        patches = {
            "get_household_account_context": household,
            "get_household_profile": {"household_size": 1},
            "get_or_create_session": None,
            "get_meal_plan_snapshot": {},
            "get_pantry_stock": [],
            "get_grocery_cart": [],
            "get_macro_diary": [],
            "get_latest_recipe_grocery_plan_metadata": None,
            "get_provider_checkout_draft": None,
            "requested_confirmation": None,
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, environment))
            for name, value in patches.items():
                target = f"app.main.{name}"
                if name == "get_or_create_session":
                    stack.enter_context(patch(target, AsyncMock(return_value=None)))
                else:
                    stack.enter_context(patch(target, return_value=value))
            stack.enter_context(patch("app.main.runner", Runner()))
            stack.enter_context(patch(
                "app.main.provider_registry.descriptor",
                return_value={"environment": "production"},
            ))
            with TestClient(app, raise_server_exceptions=False) as client:
                client.cookies.set("kitch_session", cookie)
                response = client.post("/api/chat", json={
                    "message": message, "active_user": "Owner",
                    "planner_context": {"visible_week_start": "", "selected_date": ""},
                    "pantry_stock": [], "grocery_list": [],
                })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_chat_reply_names_the_grocery_app_whose_content_it_carries(self):
        body = self._chat_with_tool_responses([
            {"status": "success", "provider": "swiggy_instamart", "items": []},
        ])
        self.assertEqual(body["provider_sources"], ["swiggy_instamart"])

    def test_chat_reply_without_grocery_app_content_has_no_attribution(self):
        body = self._chat_with_tool_responses([
            {"status": "success", "pantry": []},
            {"status": "error", "provider": "swiggy_instamart", "code": "provider_auth_required"},
        ])
        self.assertEqual(body["provider_sources"], [])

    def test_chat_reply_attributes_another_grocery_app_only_to_itself(self):
        body = self._chat_with_tool_responses([
            {"status": "success", "provider": "zepto", "items": []},
        ])
        self.assertEqual(body["provider_sources"], ["zepto"])

    def test_instamart_cancellation_guidance_is_attributed_to_instamart(self):
        body = self._chat_with_tool_responses([], message="cancel my instamart order")
        self.assertEqual(body["provider_sources"], ["swiggy_instamart"])

    def test_members_cannot_remove_anyone(self):
        household, _, environment = self._consent_fixtures()
        member = self._member_fixture(household)
        cookie = self._member_session(environment, member)
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=member,
        ), patch("app.main.remove_household_member") as remove:
            with TestClient(app) as client:
                client.cookies.set("kitch_session", cookie)
                self.assertEqual(client.delete("/api/household/members/owner-a").status_code, 403)
        remove.assert_not_called()

    def test_member_removal_explains_what_cannot_be_removed(self):
        household, _, environment = self._consent_fixtures()
        owner_cookie = self._member_session(environment, household)
        with patch.dict(os.environ, environment), patch(
            "app.main.get_household_account_context", return_value=household,
        ), patch(
            "app.main.remove_household_member", side_effect=main.MemberRemovalError("household_anchor"),
        ):
            with TestClient(app) as client:
                client.cookies.set("kitch_session", owner_cookie)
                refused = client.delete("/api/household/members/owner-a")
                self.assertEqual(refused.status_code, 422)
                self.assertEqual(refused.json()["detail"]["code"], "household_anchor")

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
        ), patch("app.main.complete_household_setup", return_value=configured) as setup, patch(
            "app.main.get_household_account_context", return_value=household,
        ):
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
    def test_exact_names_with_equal_casefold_do_not_share_nutrition_identity(self):
        identity = HouseholdIdentity(
            google_subject="owner", email="owner@example.test", household_id="household",
            owner_profile_id="first", members=(
                {"id": "first", "name": "Straße"},
                {"id": "second", "name": "Strasse"},
            ),
        )
        with patch.dict(os.environ, {"KITCH_DATABASE_BACKEND": "supabase"}):
            token = begin_identity_scope(identity)
            try:
                self.assertEqual(get_user_id("Straße"), "first")
                self.assertEqual(get_user_id("Strasse"), "second")
                self.assertEqual(canonical_user_name("Strasse"), "Strasse")
                for resolve in (get_user_id, canonical_user_name):
                    with self.assertRaisesRegex(ValueError, "ambiguous"):
                        resolve("STRASSE")
            finally:
                end_identity_scope(token)

    def test_unambiguous_case_and_space_variations_still_resolve(self):
        identity = HouseholdIdentity(
            google_subject="owner", email="owner@example.test", household_id="household",
            owner_profile_id="first", members=(
                {"id": "first", "name": "Alex"}, {"id": "second", "name": "Sam"},
            ),
        )
        with patch.dict(os.environ, {"KITCH_DATABASE_BACKEND": "supabase"}):
            token = begin_identity_scope(identity)
            try:
                self.assertEqual(get_user_id("  sAM  "), "second")
                self.assertEqual(canonical_user_name("  sAM  "), "Sam")
            finally:
                end_identity_scope(token)

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
