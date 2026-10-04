"""Contracts for Kitch's household-scoped memory integration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from google.adk.memory import InMemoryMemoryService  # noqa: E402
from google.adk.memory.base_memory_service import SearchMemoryResponse  # noqa: E402
from google.adk.memory.memory_entry import MemoryEntry  # noqa: E402
from google.genai.types import Content, Part  # noqa: E402

from app.agent import memory as memory_module  # noqa: E402
from app.household_config import get_household_profile_id  # noqa: E402


class CapturingMemoryService:
    def __init__(self) -> None:
        self.writes = []
        self.searches = []
        self.responses = SearchMemoryResponse()
        self.write_error: Exception | None = None
        self.search_error: Exception | None = None

    async def add_events_to_memory(self, **kwargs):
        if self.write_error:
            raise self.write_error
        self.writes.append(kwargs)

    async def search_memory(self, **kwargs):
        if self.search_error:
            raise self.search_error
        self.searches.append(kwargs)
        return self.responses


class ToolContextFixture:
    def __init__(self, service) -> None:
        self._context = SimpleNamespace(memory_service=service)

    def get_invocation_context(self):
        return self._context


class MemoryFactoryTests(unittest.TestCase):
    def test_in_memory_is_an_explicit_non_durable_mode(self):
        runtime = memory_module.MemoryRuntime.from_environment({
            "KITCH_MEMORY_SERVICE": "in_memory",
        })
        self.assertIsInstance(runtime.service, InMemoryMemoryService)
        self.assertTrue(runtime.configured)
        self.assertFalse(runtime.durable)

    def test_vercel_never_defaults_to_process_local_memory(self):
        runtime = memory_module.MemoryRuntime.from_environment({"VERCEL": "1"})
        self.assertEqual(runtime.backend, "vertex")
        self.assertFalse(runtime.configured)
        self.assertTrue(runtime.durable)
        self.assertIsInstance(runtime.service, memory_module.UnavailableMemoryService)

    def test_vertex_missing_configuration_degrades_without_fallback(self):
        runtime = memory_module.MemoryRuntime.from_environment({
            "KITCH_MEMORY_SERVICE": "vertex",
        })
        self.assertIsInstance(runtime.service, memory_module.UnavailableMemoryService)
        self.assertFalse(runtime.configured)
        self.assertTrue(runtime.durable)
        self.assertIn("KITCH_MEMORY_BANK_ID", runtime.diagnostic)
        self.assertIn("GOOGLE_CLOUD_PROJECT", runtime.diagnostic)
        self.assertIn("GOOGLE_CLOUD_LOCATION", runtime.diagnostic)

    def test_local_vertex_uses_adc_configuration_and_normalizes_resource_name(self):
        calls = []
        sentinel = CapturingMemoryService()

        def factory(**kwargs):
            calls.append(kwargs)
            return sentinel

        runtime = memory_module.MemoryRuntime.from_environment(
            {
                "KITCH_MEMORY_SERVICE": "vertex",
                "KITCH_MEMORY_BANK_ID": "projects/p/locations/global/reasoningEngines/12345",
                "GOOGLE_CLOUD_PROJECT": "kitch-project",
                "GOOGLE_CLOUD_LOCATION": "global",
            },
            vertex_factory=factory,
        )
        self.assertIs(runtime.service, sentinel)
        self.assertEqual(calls, [{
            "project": "kitch-project",
            "location": "global",
            "agent_engine_id": "12345",
            "credentials_factory": None,
        }])

    def test_vercel_vertex_requires_workload_identity_configuration(self):
        runtime = memory_module.MemoryRuntime.from_environment({
            "VERCEL": "1",
            "KITCH_MEMORY_SERVICE": "vertex",
            "KITCH_MEMORY_BANK_ID": "12345",
            "GOOGLE_CLOUD_PROJECT": "kitch-project",
            "GOOGLE_CLOUD_LOCATION": "global",
        })
        self.assertFalse(runtime.configured)
        self.assertIn("GCP_PROJECT_NUMBER", runtime.diagnostic)
        self.assertIn("GCP_SERVICE_ACCOUNT_EMAIL", runtime.diagnostic)

    def test_vercel_vertex_supplies_request_scoped_credentials_factory(self):
        calls = []
        sentinel = CapturingMemoryService()

        def factory(**kwargs):
            calls.append(kwargs)
            return sentinel

        runtime = memory_module.MemoryRuntime.from_environment(
            {
                "VERCEL": "1",
                "KITCH_MEMORY_SERVICE": "vertex",
                "KITCH_MEMORY_BANK_ID": "12345",
                "GOOGLE_CLOUD_PROJECT": "kitch-project",
                "GOOGLE_CLOUD_LOCATION": "global",
                "GCP_PROJECT_NUMBER": "611852448175",
                "GCP_WORKLOAD_IDENTITY_POOL_ID": "vercel",
                "GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID": "vercel-kitch",
                "GCP_SERVICE_ACCOUNT_EMAIL": "kitch-service-account@example.iam.gserviceaccount.com",
            },
            vertex_factory=factory,
        )
        self.assertTrue(runtime.configured)
        self.assertIs(runtime.service, sentinel)
        self.assertTrue(callable(calls[0]["credentials_factory"]))

    def test_invalid_backend_is_not_silently_changed(self):
        runtime = memory_module.MemoryRuntime.from_environment({
            "KITCH_MEMORY_SERVICE": "something_else",
        })
        self.assertEqual(runtime.backend, "something_else")
        self.assertFalse(runtime.configured)
        self.assertIsInstance(runtime.service, memory_module.UnavailableMemoryService)

    def test_real_vertex_factory_uses_standard_vertex_even_in_ai_studio_mode(self):
        runtime = memory_module.MemoryRuntime.from_environment({
            "KITCH_MEMORY_SERVICE": "vertex",
            "KITCH_MEMORY_BANK_ID": "12345",
            "GOOGLE_CLOUD_PROJECT": "kitch-project",
            "GOOGLE_CLOUD_LOCATION": "global",
            "GOOGLE_GENAI_USE_VERTEXAI": "FALSE",
            "GOOGLE_API_KEY": "unrelated-ai-studio-key",
        })
        self.assertTrue(runtime.configured)
        self.assertEqual(getattr(runtime.service, "_project", None), "kitch-project")
        self.assertEqual(getattr(runtime.service, "_location", None), "global")
        self.assertIsNone(getattr(runtime.service, "_express_mode_api_key", None))

    def test_vercel_token_supplier_is_request_scoped(self):
        supplier = memory_module._VercelOidcTokenSupplier()
        token = memory_module.begin_memory_auth_scope("signed-vercel-token")
        try:
            self.assertEqual(supplier.get_subject_token(None, None), "signed-vercel-token")
        finally:
            memory_module.end_memory_auth_scope(token)

    def test_specialists_share_memory_tools_but_coordinator_does_not(self):
        from app.agent.core import (
            chef_planner,
            kitch_coordinator,
            recipe_grocery_planner,
        )

        def tool_names(agent):
            return {
                getattr(tool, "name", getattr(tool, "__name__", ""))
                for tool in agent.tools
            }

        expected = {"search_household_memory_tool", "update_household_memory_tool"}
        self.assertTrue(expected.issubset(tool_names(chef_planner)))
        self.assertTrue(expected.issubset(tool_names(recipe_grocery_planner)))
        self.assertTrue(expected.isdisjoint(tool_names(kitch_coordinator)))


class HouseholdMemoryToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_uses_user_event_household_scope_unique_ids_and_waits(self):
        service = CapturingMemoryService()
        context = ToolContextFixture(service)

        first = await memory_module.update_household_memory_tool(
            "The household prefers Amul milk.", context
        )
        second = await memory_module.update_household_memory_tool(
            "Forget the preference for Amul milk.", context
        )

        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "success")
        self.assertEqual(len(service.writes), 2)
        first_write, second_write = service.writes
        self.assertEqual(first_write["app_name"], "kitch")
        self.assertEqual(first_write["user_id"], get_household_profile_id())
        self.assertEqual(first_write["custom_metadata"], {"wait_for_completion": True})
        self.assertNotIn("enable_consolidation", first_write["custom_metadata"])
        self.assertNotIn("disable_consolidation", first_write["custom_metadata"])
        first_event = first_write["events"][0]
        second_event = second_write["events"][0]
        self.assertEqual(first_event.content.role, "user")
        self.assertEqual(first_event.author, "user")
        self.assertEqual(first_event.content.parts[0].text, "The household prefers Amul milk.")
        self.assertNotEqual(first_event.id, second_event.id)

    async def test_search_returns_natural_language_without_prefix_parsing(self):
        service = CapturingMemoryService()
        service.responses = SearchMemoryResponse(memories=[
            MemoryEntry(
                content=Content(
                    role="user",
                    parts=[Part(text="For milk, the household prefers Amul in one-litre packs.")],
                ),
                author="user",
                timestamp="2026-10-04T10:00:00Z",
            )
        ])
        result = await memory_module.search_household_memory_tool(
            "What milk should I buy?", ToolContextFixture(service)
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            result["memories"][0]["text"],
            "For milk, the household prefers Amul in one-litre packs.",
        )
        self.assertEqual(service.searches[0]["user_id"], get_household_profile_id())

    async def test_memory_failure_is_explicit_and_does_not_echo_credentials(self):
        service = CapturingMemoryService()
        service.write_error = RuntimeError("secret-key-value caused a 401")
        result = await memory_module.update_household_memory_tool(
            "We prefer less spicy food.", ToolContextFixture(service)
        )

        self.assertEqual(result["status"], "error")
        self.assertIn("authentication failed", result["message"].lower())
        self.assertNotIn("secret-key-value", result["message"])
        self.assertIn("not saved", result["message"].lower())

    async def test_empty_inputs_do_not_reach_memory_backend(self):
        service = CapturingMemoryService()
        context = ToolContextFixture(service)
        write = await memory_module.update_household_memory_tool("  ", context)
        search = await memory_module.search_household_memory_tool("", context)
        self.assertEqual(write["status"], "error")
        self.assertEqual(search["status"], "error")
        self.assertEqual(service.writes, [])
        self.assertEqual(service.searches, [])


if __name__ == "__main__":
    unittest.main()
