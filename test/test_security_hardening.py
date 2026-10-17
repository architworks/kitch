"""Security regressions from the 2026-10-17 audit that are not auth or agent
session isolation (those live in test_household_auth and test_agent_isolation).
"""

from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import supabase_client  # noqa: E402


class _FakeRpc:
    def __init__(self, calls: list):
        self.calls = calls

    def rpc(self, name, params):
        self.calls.append((name, params))
        row = {"id": params["p_plan_id"], "profile_id": params["p_profile_id"], "recipe_cards": [],
               "ingredients": [], "pantry_considerations": [], "scope": {}}
        return types.SimpleNamespace(execute=lambda: types.SimpleNamespace(data={"plan": row, "cart": []}))


class RecipePlanOwnershipTests(unittest.TestCase):
    """Finding #8: a model-supplied plan id could overwrite another household's plan."""

    def _save(self, owned_plan):
        calls: list = []
        with patch.object(supabase_client, "supabase", _FakeRpc(calls)), patch.object(
            supabase_client, "get_household_profile_id", return_value="household-a-owner",
        ), patch.object(supabase_client, "get_recipe_grocery_plan", return_value=owned_plan):
            supabase_client.save_recipe_grocery_plan(
                {"id": "11111111-1111-1111-1111-111111111111", "request": "dal",
                 "recipeCards": [{"title": "Dal"}], "ingredients": []},
            )
        return calls[0][1]

    def test_foreign_plan_id_is_saved_as_a_new_plan(self):
        params = self._save(owned_plan=None)
        self.assertNotEqual(params["p_plan_id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(params["p_profile_id"], "household-a-owner")

    def test_own_plan_id_is_updated_in_place(self):
        params = self._save(owned_plan={"id": "11111111-1111-1111-1111-111111111111"})
        self.assertEqual(params["p_plan_id"], "11111111-1111-1111-1111-111111111111")


class DateRangeBoundTests(unittest.TestCase):
    """Findings #4, #7, #14, #20, #22: tiny requests expanded millions of days."""

    def test_day_by_day_expansion_is_capped(self):
        from datetime import date
        from app.planning_calendar import MAX_DATE_RANGE_DAYS, dates_between

        self.assertEqual(len(dates_between(date(2026, 1, 1), date(2026, 12, 31))), 365)
        with self.assertRaises(ValueError):
            dates_between(date(2026, 1, 1), date(4026, 1, 1))
        self.assertEqual(MAX_DATE_RANGE_DAYS, 366)

    def test_nutrition_dashboard_rejects_a_huge_range_before_reading(self):
        with patch.object(supabase_client, "get_macro_diary") as diary:
            with self.assertRaises(ValueError):
                supabase_client.get_nutrition_dashboard("Asha", "2026-01-01", "9999-12-31")
            diary.assert_not_called()

    def test_meal_removal_rejects_huge_or_too_many_ranges_before_the_database(self):
        with patch.object(supabase_client, "supabase") as database:
            with self.assertRaises(ValueError):
                supabase_client.remove_future_meal_plan_entries([
                    {"action": "range", "start_date": "2026-11-01", "end_date": "9999-12-31"},
                ])
            with self.assertRaises(ValueError):
                supabase_client.remove_future_meal_plan_entries([
                    {"action": "date", "start_date": "2026-11-01"} for _ in range(40)
                ])
            database.rpc.assert_not_called()

    def test_meal_plan_replacement_rejects_a_huge_range(self):
        with patch.object(supabase_client, "get_household_timezone", return_value="UTC"), patch.object(
            supabase_client, "supabase",
        ) as database:
            with self.assertRaises(ValueError):
                supabase_client.replace_meal_plan_range("2030-01-01", "9999-12-31", [])
            database.rpc.assert_not_called()


class ZeptoHouseholdScopeTests(unittest.TestCase):
    """Finding #11: a global Zepto credential must never be shared by households."""

    def test_zepto_cannot_be_enabled_on_hosted_multi_household_kitch(self):
        from app.providers.zepto import ZeptoProviderAdapter

        with patch.dict(os.environ, {
            "KITCH_DATABASE_BACKEND": "supabase", "ZEPTO_MCP_ENABLED": "true",
            "ZEPTO_MCP_ACCESS_TOKEN": "shared-token",
        }):
            adapter = ZeptoProviderAdapter()
            self.assertFalse(adapter.enabled)
            self.assertEqual(adapter.status()["state"], "disabled")

    def test_zepto_still_works_for_a_single_local_household(self):
        from app.providers.zepto import ZeptoProviderAdapter

        with patch.dict(os.environ, {
            "KITCH_DATABASE_BACKEND": "sqlite", "ZEPTO_MCP_ENABLED": "true",
            "ZEPTO_MCP_ACCESS_TOKEN": "local-token",
        }):
            self.assertTrue(ZeptoProviderAdapter().enabled)


if __name__ == "__main__":
    unittest.main()
