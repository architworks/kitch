"""Regression tests for date-specific household meal planning."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_unit_test_credential_value")

from app.planning_calendar import (  # noqa: E402
    calendar_context,
    monday_for,
)
from app import supabase_client  # noqa: E402
from app.schemas import ChatRequest  # noqa: E402


class PlanningCalendarTests(unittest.TestCase):
    def test_household_context_has_exact_current_and_next_week_ranges(self):
        context = calendar_context(
            "Asia/Kolkata",
            datetime(2026, 8, 12, 9, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
        )
        self.assertEqual(context["today"].isoformat(), "2026-08-12")
        self.assertEqual(context["tomorrow"].isoformat(), "2026-08-13")
        self.assertEqual(context["current_week_start"].isoformat(), "2026-08-10")
        self.assertEqual(context["current_week_end"].isoformat(), "2026-08-16")
        self.assertEqual(context["next_week_start"].isoformat(), "2026-08-17")
        self.assertEqual(context["next_week_end"].isoformat(), "2026-08-23")

    def test_week_start_is_monday_for_every_date(self):
        context_date = datetime(2026, 8, 12).date()
        self.assertEqual(monday_for(context_date).isoformat(), "2026-08-10")
        self.assertEqual(context_date.strftime("%A"), "Wednesday")

    def test_week_payload_contains_empty_dates_and_next_chronological_meal(self):
        fixed_context = calendar_context(
            "Asia/Kolkata",
            datetime(2026, 8, 12, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        )
        saved_rows = [
            {
                "plan_date": "2026-08-13",
                "weekday": "Thursday",
                "breakfast": "Avocado Toast",
                "lunch": "Quinoa Salad",
                "dinner": "Lemon Herb Paneer",
            }
        ]
        with (
            patch.object(supabase_client, "get_household_timezone", return_value="Asia/Kolkata"),
            patch.object(supabase_client, "calendar_context", return_value=fixed_context),
            patch.object(supabase_client, "get_meal_schedule", side_effect=[saved_rows, saved_rows]),
        ):
            payload = supabase_client.build_meal_plan_week("2026-08-10")

        self.assertEqual(len(payload["days"]), 7)
        self.assertEqual(payload["days"][0]["plan_date"], "2026-08-10")
        self.assertEqual(payload["days"][0]["breakfast"], "")
        self.assertEqual(payload["next_planned_date"], "2026-08-13")
        self.assertEqual(payload["next_meal"]["meal_name"], "Avocado Toast")

    def test_chat_contract_uses_planner_context_not_client_plan_state(self):
        payload = ChatRequest(
            message="Plan tomorrow",
            active_user="Archit",
            diet_preference="balanced",
            household_size=3,
            planner_context={
                "visible_week_start": "2026-08-10",
                "selected_date": "2026-08-12",
            },
            pantry_stock=[],
            grocery_list=[],
        )
        self.assertEqual(payload.planner_context.selected_date, "2026-08-12")
        self.assertNotIn("weekly_plan", payload.model_dump())

    def test_range_replacement_rejects_past_dates_before_calling_supabase(self):
        fixed_context = calendar_context(
            "Asia/Kolkata",
            datetime(2026, 8, 12, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        )
        with (
            patch.object(supabase_client, "get_household_timezone", return_value="Asia/Kolkata"),
            patch.object(supabase_client, "calendar_context", return_value=fixed_context),
            patch.object(supabase_client, "_read_rows") as read_rows,
        ):
            with self.assertRaisesRegex(ValueError, "Past meal-plan dates"):
                supabase_client.replace_meal_plan_range(
                    "2026-08-11",
                    "2026-08-11",
                    [{
                        "plan_date": "2026-08-11",
                        "breakfast": "Oats",
                        "lunch": "Dal",
                        "dinner": "Paneer",
                    }],
                )
        read_rows.assert_not_called()

    def test_multi_edit_rejects_any_past_date_atomically(self):
        fixed_context = calendar_context(
            "Asia/Kolkata",
            datetime(2026, 8, 12, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        )
        with (
            patch.object(supabase_client, "get_household_timezone", return_value="Asia/Kolkata"),
            patch.object(supabase_client, "calendar_context", return_value=fixed_context),
            patch.object(supabase_client, "_read_rows") as read_rows,
        ):
            with self.assertRaisesRegex(ValueError, "Past meal-plan dates"):
                supabase_client.apply_meal_plan_edits([
                    {"plan_date": "2026-08-13", "meal_slot": "dinner", "meal_name": "Tofu Curry"},
                    {"plan_date": "2026-08-11", "meal_slot": "lunch", "meal_name": "Salad"},
                ])
        read_rows.assert_not_called()

    def test_retention_deletes_only_dates_before_household_today(self):
        fixed_context = calendar_context(
            "Asia/Kolkata",
            datetime(2026, 8, 12, 0, 5, tzinfo=ZoneInfo("Asia/Kolkata")),
        )
        builder = MagicMock()
        builder.delete.return_value = builder
        builder.eq.return_value = builder
        builder.lt.return_value = builder
        builder.execute.return_value = SimpleNamespace(
            data=[{"plan_date": "2026-08-11"}],
        )
        client = MagicMock()
        client.table.return_value = builder

        with (
            patch.object(supabase_client, "supabase", client),
            patch.object(supabase_client, "get_household_timezone", return_value="Asia/Kolkata"),
            patch.object(supabase_client, "calendar_context", return_value=fixed_context),
            patch.object(supabase_client, "get_household_profile_id", return_value="household-id"),
        ):
            deleted_count = supabase_client.delete_past_meal_plans()

        self.assertEqual(deleted_count, 1)
        client.table.assert_called_once_with("meal_plans")
        builder.eq.assert_called_once_with("profile_id", "household-id")
        builder.lt.assert_called_once_with("plan_date", "2026-08-12")


class DatedMealPlanMigrationTests(unittest.TestCase):
    def test_destructive_migration_has_clean_date_contract_and_transactions(self):
        migration = (
            ROOT
            / "backend"
            / "database"
            / "migrations"
            / "20260812_date_specific_meal_plans.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("DROP TABLE IF EXISTS public.meal_plans CASCADE", migration)
        self.assertIn("plan_date DATE NOT NULL", migration)
        self.assertIn("UNIQUE (profile_id, plan_date)", migration)
        self.assertIn("replace_meal_plan_range", migration)
        self.assertIn("apply_meal_plan_edits", migration)
        self.assertIn("ENABLE ROW LEVEL SECURITY", migration)
        self.assertNotIn("breakfast_recipe_id", migration)
        self.assertNotIn("snack_recipe_id", migration)


if __name__ == "__main__":
    unittest.main()
