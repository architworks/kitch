"""Security regressions: agent conversation state never crosses households.

Finding #2 (security audit 2026-10-17): chat sessions were keyed by member
display name, and household facts lived in ADK app: state shared by every
household on the server, so a same-named member in another household could
read the first household's conversation.
"""

import asyncio
import types
import unittest
from unittest.mock import patch

from google.adk.sessions import InMemorySessionService

from app import main
from app.auth import HouseholdIdentity, begin_identity_scope, end_identity_scope


def _identity(household_id: str, profile_id: str, name: str) -> HouseholdIdentity:
    return HouseholdIdentity(
        google_subject=f"subject-{household_id}",
        email=f"{household_id}@example.com",
        household_id=household_id,
        owner_profile_id=profile_id,
        members=({"id": profile_id, "name": name},),
        profile_id=profile_id,
        role="owner",
    )


class AgentIsolationTests(unittest.TestCase):
    def _scope(self, identity: HouseholdIdentity, name: str):
        token = begin_identity_scope(identity)
        try:
            return main._agent_scope(name)
        finally:
            end_identity_scope(token)

    def test_same_member_name_in_two_households_gets_separate_sessions(self):
        first = self._scope(_identity("household-a", "profile-a", "Asha"), "Asha")
        second = self._scope(_identity("household-b", "profile-b", "Asha"), "Asha")
        self.assertNotEqual(first, second)
        self.assertEqual(first, ("household-a:profile-a", "kitch_chat:household-a:profile-a"))

    def test_household_facts_are_session_state_not_shared_app_state(self):
        service = InMemorySessionService()

        async def run():
            for identity in (
                _identity("household-a", "profile-a", "Asha"),
                _identity("household-b", "profile-b", "Asha"),
            ):
                token = begin_identity_scope(identity)
                try:
                    user_id, session_id = main._agent_scope("Asha")
                    with patch.object(main, "session_service", service), patch.object(
                        main, "get_household_members",
                        return_value=[{"id": identity.profile_id, "name": f"Asha of {identity.household_id}"}],
                    ):
                        await main.get_or_create_session("Asha", session_id, 1, user_id=user_id)
                finally:
                    end_identity_scope(token)
            return service

        asyncio.run(run())
        self.assertEqual(service.app_state.get("kitch", {}), {})
        a = asyncio.run(service.get_session(
            app_name="kitch", user_id="household-a:profile-a",
            session_id="kitch_chat:household-a:profile-a",
        ))
        b = asyncio.run(service.get_session(
            app_name="kitch", user_id="household-b:profile-b",
            session_id="kitch_chat:household-b:profile-b",
        ))
        self.assertEqual(a.state["household_members"], "Asha of household-a")
        self.assertEqual(b.state["household_members"], "Asha of household-b")

    def test_leaving_or_deleting_forgets_the_members_chat_history(self):
        service = InMemorySessionService()
        fake_core = types.SimpleNamespace(session_service=service)

        async def run():
            for user_id in ("household-a:profile-a", "household-a:profile-b", "household-b:profile-a"):
                await service.create_session(
                    app_name="kitch", user_id=user_id, session_id=f"kitch_chat:{user_id}",
                    state={"user:profile_name": "Asha"},
                )
            with patch.dict("sys.modules", {"app.agent.core": fake_core}):
                removed = await main._purge_agent_state("household-a", ["profile-a"])
            remaining = {
                user_id: len((await service.list_sessions(app_name="kitch", user_id=user_id)).sessions)
                for user_id in ("household-a:profile-a", "household-a:profile-b", "household-b:profile-a")
            }
            return removed, remaining

        removed, remaining = asyncio.run(run())
        self.assertEqual(removed, 1)
        self.assertEqual(remaining, {
            "household-a:profile-a": 0,
            "household-a:profile-b": 1,
            "household-b:profile-a": 1,
        })
        self.assertNotIn("household-a:profile-a", service.user_state.get("kitch", {}))

    def test_member_memory_cleanup_matches_full_and_first_names(self):
        from app.agent.memory import _mentions

        self.assertTrue(_mentions("Asha Rao is allergic to peanuts.", "Asha Rao"))
        self.assertTrue(_mentions("Asha dislikes okra.", "Asha Rao"))
        self.assertFalse(_mentions("Ashanti prefers basmati rice.", "Asha Rao"))
        self.assertFalse(_mentions("The household likes dal.", "Asha Rao"))


if __name__ == "__main__":
    unittest.main()
