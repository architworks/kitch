"""Focused tests for chat-owned native cart changes and Instamart sync routing."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_SECRET_KEY"] = "sb_secret_unit_test_credential_value"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["SUPABASE_KEY"] = ""

from app.agent import tools  # noqa: E402


class NativeGroceryCartMutationTests(unittest.TestCase):
    def test_add_creates_a_manual_standalone_row(self):
        saved = {
            "id": "chocolate-1",
            "name": "Dairy Milk chocolate",
            "amount": 1.0,
            "unit": "bar",
            "category": "Snacks",
            "source": "manual",
        }
        changes = [
            {
                "action": "add",
                "name": "Dairy Milk chocolate",
                "amount": 1,
                "unit": "bar",
                "category": "Snacks",
            }
        ]
        with patch.object(
            tools,
            "db_apply_native_grocery_cart_changes",
            return_value=[saved],
        ) as apply:
            result = tools.modify_native_grocery_cart_tool([
                changes[0]
            ])

        self.assertEqual(result["status"], "success")
        self.assertFalse(result["provider_cart_changed"])
        self.assertEqual(result["grocery_cart"], [saved])
        apply.assert_called_once_with(changes)

    def test_multiple_changes_are_sent_to_one_atomic_persistence_call(self):
        changes = [
            {"action": "add", "name": "Eggs", "amount": 6, "unit": "piece"},
            {"action": "remove", "item_id": "00000000-0000-0000-0000-000000000001"},
        ]
        with patch.object(
            tools,
            "db_apply_native_grocery_cart_changes",
            return_value=[],
        ) as apply:
            result = tools.modify_native_grocery_cart_tool(changes)

        self.assertEqual(result["status"], "success")
        self.assertIn("atomically", result["message"])
        apply.assert_called_once_with(changes)

    def test_invalid_change_collection_never_calls_persistence(self):
        with patch.object(tools, "db_apply_native_grocery_cart_changes") as apply:
            result = tools.modify_native_grocery_cart_tool(["not-an-object"])

        self.assertEqual(result["status"], "error")
        apply.assert_not_called()


class InstamartChatSyncToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_combined_request_mutates_native_cart_before_existing_sync_path(self):
        service = AsyncMock()
        service.sync_from_chat.return_value = {
            "status": "success",
            "native_cart_changed": True,
            "address_selection": "last_selected",
            "review": {
                "matched_items": [{"native_item": {"id": "chocolate-1"}}],
                "unavailable_items": [],
                "selected_address_id": "address-1",
                "message": "Instamart cart confirmed.",
            },
        }
        fake_main = ModuleType("app.main")
        fake_main.grocery_checkout_service = service
        changes = [{
            "action": "add",
            "name": "Dairy Milk chocolate",
            "amount": 1,
            "unit": "bar",
        }]

        with patch.dict(sys.modules, {"app.main": fake_main}):
            result = await tools.sync_instamart_cart_tool(
                user_request="Add one Dairy Milk chocolate and sync to Instamart",
                native_cart_changes=changes,
            )

        service.sync_from_chat.assert_awaited_once_with(
            cart_item_ids=[],
            selected_address_id="",
            user_instruction="Add one Dairy Milk chocolate and sync to Instamart",
            native_cart_changes=changes,
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["native_cart_changed"])
        self.assertEqual(result["ui_action"], "UPDATE_PROVIDER_CART")

    async def test_native_changes_are_never_applied_inside_the_coordinator_tool(self):
        service = AsyncMock()
        service.sync_from_chat.return_value = {
            "status": "partial",
            "native_cart_changed": True,
            "provider_cart_changed": False,
            "review": None,
            "message": "Native cart updated; provider sync failed.",
        }
        fake_main = ModuleType("app.main")
        fake_main.grocery_checkout_service = service
        changes = [{"action": "remove", "name": "milk"}]
        with patch.dict(sys.modules, {"app.main": fake_main}):
            result = await tools.sync_instamart_cart_tool(
                user_request="Remove milk and sync to Instamart",
                native_cart_changes=changes,
            )

        service.sync_from_chat.assert_awaited_once_with(
            cart_item_ids=[],
            selected_address_id="",
            user_instruction="Remove milk and sync to Instamart",
            native_cart_changes=changes,
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["ui_action"], "UPDATE_GROCERY_CART")
        self.assertFalse(result["provider_cart_changed"])


class AgentTopologyContractTests(unittest.TestCase):
    def test_existing_sync_bridge_is_kept_and_no_second_coordinator_tool_is_added(self):
        core = (ROOT / "backend" / "app" / "agent" / "core.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("sync_instamart_cart_tool", core)
        self.assertIn("modify_native_grocery_cart_tool", core)
        self.assertNotIn("mutate_native_and_sync", core)
        self.assertIn("native_cart_changes on the SAME sync_instamart_cart_tool call", core)

    def test_atomic_native_cart_migration_is_backend_only(self):
        migration = (
            ROOT
            / "backend"
            / "database"
            / "migrations"
            / "20260816_atomic_native_grocery_cart_changes.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("BEGIN;", migration)
        self.assertIn("COMMIT;", migration)
        self.assertIn("apply_native_grocery_cart_changes", migration)
        self.assertIn("FROM PUBLIC, anon, authenticated", migration)
        self.assertIn("TO service_role", migration)


if __name__ == "__main__":
    unittest.main()
