"""The dashboard state load returns the same shape and runs its reads in parallel."""

import asyncio
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("KITCH_DATABASE_BACKEND", "supabase")

from app import main  # noqa: E402


class StateLoadTests(unittest.TestCase):
    def test_state_shape_is_unchanged_and_reads_overlap(self):
        running = 0
        peak = 0
        lock = threading.Lock()

        def slow(value):
            def read(*args, **kwargs):
                nonlocal running, peak
                with lock:
                    running += 1
                    peak = max(peak, running)
                time.sleep(0.05)
                with lock:
                    running -= 1
                return value
            return read

        profile = {"timezone_name": "Asia/Kolkata", "pantry_revision": 3, "pantry_reviewed_at": "2026-11-01"}
        with (
            patch.object(main, "canonical_user_name", side_effect=lambda name: name),
            patch.object(main, "get_household_profile", return_value=profile),
            patch.object(main, "get_pantry_stock", side_effect=slow([{"id": 1}])),
            patch.object(main, "get_macro_diary", side_effect=slow({"entries": []})),
            patch.object(main, "build_meal_plan_week", side_effect=slow({"days": []})),
            patch.object(main, "list_recipe_grocery_plans", side_effect=slow([{"id": "plan-1"}])),
            patch.object(main, "get_household_members", side_effect=slow(["Archit"])),
            patch.object(main, "get_nutrition_targets", side_effect=slow({"calories": 2000})),
            patch.object(main, "get_grocery_cart", side_effect=slow([{"id": 7}])),
        ):
            state = asyncio.run(main.get_state_endpoint("Archit"))

        self.assertEqual(state["profile"], profile)
        self.assertEqual(state["household_members"], ["Archit"])
        self.assertEqual(state["nutrition_targets"], {"calories": 2000})
        self.assertEqual(state["pantry"], {"revision": 3, "reviewedAt": "2026-11-01", "items": [{"id": 1}]})
        self.assertEqual(state["pantry_stock"], [{"id": 1}])
        self.assertEqual(state["macro_diary"], {"entries": []})
        self.assertEqual(state["meal_plan"], {"days": []})
        self.assertEqual(state["grocery_cart"], [{"id": 7}])
        self.assertEqual(state["latest_recipe_grocery_plan"], {"id": "plan-1"})
        self.assertGreater(peak, 1, "independent reads should run at the same time")

    def test_meal_plan_can_be_skipped(self):
        with (
            patch.object(main, "canonical_user_name", side_effect=lambda name: name),
            patch.object(main, "get_household_profile", return_value={}),
            patch.object(main, "get_pantry_stock", return_value=[]),
            patch.object(main, "get_macro_diary", return_value={}),
            patch.object(main, "build_meal_plan_week") as build,
            patch.object(main, "list_recipe_grocery_plans", return_value=[]),
            patch.object(main, "get_household_members", return_value=[]),
            patch.object(main, "get_nutrition_targets", return_value={}),
            patch.object(main, "get_grocery_cart", return_value=[]),
        ):
            state = asyncio.run(main.get_state_endpoint("Archit", include_meal_plan=False))
        self.assertIsNone(state["meal_plan"])
        self.assertIsNone(state["latest_recipe_grocery_plan"])
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
