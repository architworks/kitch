from __future__ import annotations

import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_unit_test_credential_value")

from app.agent import tools  # noqa: E402
from app.agent_confirmation import (  # noqa: E402
    begin_confirmation_scope, end_confirmation_scope, requested_confirmation,
)
from app import pantry_service  # noqa: E402
from app.pantry_service import _propose_inventory, PantryReconciliationError  # noqa: E402
from app.agent.tool_error_policy import recover_unknown_tool_error  # noqa: E402


class PantryProposalTests(unittest.TestCase):
    def test_set_is_absolute_and_repeated_observation_does_not_accumulate(self):
        current = [{"id": 1, "name": "Eggs", "amount": 6, "unit": "piece"}]
        operation = [{"action": "set", "id": 1, "name": "Eggs", "amount": 12, "unit": "piece"}]
        once = _propose_inventory(current, "patch", operation)
        twice = _propose_inventory(once, "patch", operation)
        self.assertEqual(once[0]["amount"], 12)
        self.assertEqual(twice[0]["amount"], 12)

    def test_add_accumulates_and_remove_deletes(self):
        current = [{"id": 1, "name": "Milk", "amount": 1, "unit": "litre"}]
        added = _propose_inventory(current, "patch", [
            {"action": "add", "id": 1, "name": "Milk", "amount": 2, "unit": "litre"},
        ])
        self.assertEqual(added[0]["amount"], 3)
        self.assertEqual(_propose_inventory(added, "patch", [{"action": "remove", "id": 1}]), [])

    def test_existing_row_add_uses_read_row_and_preserves_its_representation(self):
        current = [{"id": 1, "name": "Rice", "amount": 2, "unit": "bag"}]
        proposed = _propose_inventory(current, "patch", [
            {"action": "add", "id": 1, "name": "Rice", "amount": 1},
        ])
        self.assertEqual(proposed[0]["amount"], 3)
        self.assertEqual(proposed[0]["unit"], "bag")

    def test_set_by_new_name_creates_absolute_observation(self):
        proposed = _propose_inventory([], "patch", [
            {"action": "set", "name": "Paneer", "amount": 1, "unit": "block"},
        ])
        self.assertEqual(proposed, [{"name": "Paneer", "amount": 1.0, "unit": "block"}])

    def test_empty_replacement_means_empty_pantry(self):
        self.assertEqual(_propose_inventory([{"id": 1, "name": "Milk", "amount": 1, "unit": "litre"}], "replace", []), [])


class DestructiveConfirmationTests(unittest.IsolatedAsyncioTestCase):
    async def test_replace_pantry_creates_pending_action_without_mutating(self):
        token = begin_confirmation_scope()
        try:
            pending = {
                "id": "pending-1",
                "impact_summary": {"title": "Replace the complete pantry?", "message": "This will mark the pantry empty."},
            }
            with patch.object(tools, "db_create_pending_agent_action", return_value=pending) as create:
                result = await tools.replace_pantry_tool([], 4, "Archit")
            self.assertEqual(result["status"], "confirmation_required")
            self.assertEqual(requested_confirmation()["action_id"], "pending-1")
            create.assert_called_once()
        finally:
            end_confirmation_scope(token)


class MealRemovalToolTests(unittest.TestCase):
    def test_clear_all_resolves_saved_future_dates_and_requests_confirmation(self):
        token = begin_confirmation_scope()
        try:
            pending = {
                "id": "pending-meals",
                "impact_summary": {"title": "Remove these planned meals?", "message": "exact range"},
            }
            with (
                patch.object(tools, "calendar_context", return_value={"today": date(2026, 10, 3)}),
                patch.object(tools, "get_household_timezone", return_value="Asia/Kolkata"),
                patch.object(tools, "db_get_meal_schedule", return_value=[
                    {"plan_date": "2026-10-05"}, {"plan_date": "2026-10-12"},
                ]),
                patch.object(tools, "db_create_pending_agent_action", return_value=pending) as create,
                patch.object(tools, "db_remove_future_meal_plan_entries") as remove,
            ):
                result = tools.remove_future_meals_tool([{"action": "clear_all"}], "Archit")

            self.assertEqual(result["status"], "confirmation_required")
            create.assert_called_once()
            self.assertEqual(create.call_args.kwargs["payload"]["operations"], [{
                "action": "range", "start_date": "2026-10-05", "end_date": "2026-10-12",
            }])
            remove.assert_not_called()
            self.assertEqual(requested_confirmation()["action_id"], "pending-meals")
        finally:
            end_confirmation_scope(token)

    def test_past_removal_is_rejected_without_calling_persistence(self):
        with (
            patch.object(tools, "calendar_context", return_value={"today": date(2026, 10, 3)}),
            patch.object(tools, "get_household_timezone", return_value="Asia/Kolkata"),
            patch.object(tools, "db_remove_future_meal_plan_entries") as remove,
        ):
            result = tools.remove_future_meals_tool([{
                "action": "date", "start_date": "2026-10-02",
            }])
        self.assertEqual(result["status"], "error")
        self.assertIn("Past meal plans", result["message"])
        remove.assert_not_called()

    def test_single_slot_is_normalized_and_removed_directly(self):
        persisted = {"affected_dates": ["2026-10-05"]}
        with (
            patch.object(tools, "calendar_context", return_value={"today": date(2026, 10, 3)}),
            patch.object(tools, "get_household_timezone", return_value="Asia/Kolkata"),
            patch.object(tools, "db_remove_future_meal_plan_entries", return_value=persisted) as remove,
        ):
            result = tools.remove_future_meals_tool([{
                "action": "remove_meal", "plan_date": "2026-10-05", "meal_slot": "dinner",
            }])
        self.assertEqual(result["status"], "success")
        remove.assert_called_once_with([{
            "action": "slot", "start_date": "2026-10-05", "end_date": "2026-10-05",
            "meal_slot": "dinner",
        }])


class PantryToolInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_quantity_bearing_mutation_rejects_missing_amount_before_service(self):
        with patch("app.pantry_service.mutate_pantry") as mutate:
            result = await tools.patch_pantry_tool(
                [{"action": "set", "name": "Eggs", "unit": "piece"}],
                expected_revision=3,
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("requires", result["message"])
        mutate.assert_not_called()


class PantryTransactionBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_pantry_mutation_does_not_read_or_reconcile_cart(self):
        with (
            patch.object(pantry_service, "get_pantry_state", return_value={"revision": 2, "reviewedAt": None, "items": []}),
            patch.object(pantry_service, "get_grocery_cart") as read_cart,
            patch.object(pantry_service, "_reconcile_with_agent") as reconcile,
            patch.object(pantry_service, "apply_pantry_inventory_change", return_value={"revision": 3, "pantry": []}) as persist,
        ):
            await pantry_service.mutate_pantry(
                expected_revision=2, mode="patch",
                items=[{"action": "set", "name": "Eggs", "amount": 6, "unit": "piece"}],
            )
        read_cart.assert_not_called()
        reconcile.assert_not_called()
        persist.assert_called_once_with(
            expected_revision=2, mode="patch",
            items=[{"action": "set", "name": "Eggs", "amount": 6, "unit": "piece"}],
        )

    async def test_explicit_reconciliation_failure_does_not_update_cart(self):
        with (
            patch.object(pantry_service, "get_pantry_state", return_value={"revision": 2, "reviewedAt": None, "items": []}),
            patch.object(pantry_service, "get_grocery_cart", return_value=[{"id": 1, "name": "Eggs", "amount": 6, "unit": "piece"}]),
            patch.object(pantry_service, "_reconcile_with_agent", side_effect=PantryReconciliationError("bad result")),
            patch.object(pantry_service, "apply_pantry_cart_reconciliation") as persist,
        ):
            with self.assertRaises(PantryReconciliationError):
                await pantry_service.reconcile_native_cart_with_pantry(expected_revision=2)
        persist.assert_not_called()


class CheckedInSchemaContractTests(unittest.TestCase):
    def test_final_schema_uses_revisioned_pantry_and_purchase_allocations(self):
        schema = (ROOT / "backend/database/supabase_schema.sql").read_text()
        self.assertIn("pantry_revision BIGINT", schema)
        self.assertIn("pantry_reviewed_at", schema)
        self.assertIn("purchase_amount", schema)
        self.assertIn("pantry_allocation", schema)
        self.assertIn("apply_pantry_cart_reconciliation", schema)
        self.assertIn("claim_pending_agent_action", schema)
        self.assertIn("'executing'", schema)
        self.assertIn("plan_preexisted boolean", schema)
        self.assertIn("recipe_grocery_plan_id = p_recipe_grocery_plan_id", schema)
        cart_definition = schema.split("CREATE TABLE IF NOT EXISTS public.grocery_cart_items", 1)[1].split(");", 1)[0]
        self.assertNotIn("already_stocked", cart_definition)
        self.assertNotIn("stock_note", cart_definition)

    def test_vision_agent_has_no_mutation_tools(self):
        core = (ROOT / "backend/app/agent/core.py").read_text()
        vision = core.split("vision_scanner =", 1)[1].split("nutrition_tracker =", 1)[0]
        self.assertIn("tools=[]", vision)
        self.assertIn("output_schema=PhotoAnalysis", vision)
        self.assertIn('mode="chat"', vision)

    def test_specialists_are_task_scoped_and_one_shot_runners_use_valid_root_mode(self):
        core = (ROOT / "backend/app/agent/core.py").read_text()
        chef = core.split("chef_planner =", 1)[1].split("vision_scanner =", 1)[0]
        nutrition = core.split("nutrition_tracker =", 1)[1].split("pantry_reconciliation_agent =", 1)[0]
        recipe = core.split("recipe_grocery_planner =", 1)[1].split("kitch_coordinator =", 1)[0]
        reconciliation = core.split("pantry_reconciliation_agent =", 1)[1].split("recipe_grocery_planner =", 1)[0]
        self.assertIn('mode="task"', chef)
        self.assertIn('mode="task"', nutrition)
        self.assertIn('mode="task"', recipe)
        self.assertIn('mode="chat"', reconciliation)


class ToolErrorPolicyTests(unittest.TestCase):
    def test_unknown_tool_returns_reflection_without_masking_real_errors(self):
        unknown = type("Tool", (), {"name": "invented_tool", "description": "Tool not found"})()
        response = recover_unknown_tool_error(
            tool=unknown, args={}, tool_context=None,
            error=ValueError("Tool 'invented_tool' not found"),
        )
        self.assertEqual(response["code"], "unknown_tool")
        self.assertIn("exact registered tool name", response["message"])

        real_tool = type("Tool", (), {"name": "save", "description": "Save"})()
        self.assertIsNone(recover_unknown_tool_error(
            tool=real_tool, args={}, tool_context=None,
            error=RuntimeError("database unavailable"),
        ))


if __name__ == "__main__":
    unittest.main()
