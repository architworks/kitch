"""Nutrition diary timing and schema contracts."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_SECRET_KEY"] = "sb_secret_unit_test_credential_value"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["SUPABASE_KEY"] = ""

from app import supabase_client  # noqa: E402
from app.agent import tools as agent_tools  # noqa: E402


class NutritionMealTimingTests(unittest.TestCase):
    def infer(self, hour: int, explicit: str = "") -> str:
        with patch.object(
            supabase_client, "get_household_timezone", return_value="Asia/Kolkata"
        ):
            return supabase_client.infer_nutrition_meal_type(
                datetime(2026, 10, 3, hour, 0), explicit
            )

    def test_household_time_assigns_each_meal_group(self):
        self.assertEqual(self.infer(5), "breakfast")
        self.assertEqual(self.infer(11), "lunch")
        self.assertEqual(self.infer(16), "snack")
        self.assertEqual(self.infer(19), "dinner")
        self.assertEqual(self.infer(2), "dinner")

    def test_explicit_meal_context_overrides_time(self):
        self.assertEqual(self.infer(22, "breakfast"), "breakfast")

    def test_agent_nutrition_write_uses_server_scoped_active_user(self):
        context = SimpleNamespace(state={"user:profile_name": "Naman"})
        with patch.object(agent_tools, "db_log_macros") as save:
            agent_tools.log_macros_tool(
                "Archit", "pear", 100, 1, 25, 0,
                meal_type="lunch", tool_context=context,
            )
        self.assertEqual(save.call_args.args[0], "Naman")

    def test_migration_adds_dated_editable_nutrition_fields(self):
        migration = (
            ROOT / "backend" / "database" / "migrations"
            / "20261003_nutrition_tracker_redesign.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("RENAME COLUMN logged_at TO consumed_at", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS meal_type", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS quantity", migration)
        self.assertIn("'breakfast', 'lunch', 'snack', 'dinner'", migration)


if __name__ == "__main__":
    unittest.main()
