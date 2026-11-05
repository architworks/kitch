"""Deleting a native cart row is idempotent: a repeat finds it gone, not an error."""

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("KITCH_DATABASE_BACKEND", "supabase")

from app import main, supabase_client  # noqa: E402


class GroceryCartDeleteTests(unittest.TestCase):
    def test_deleting_a_row_that_is_already_gone_is_not_a_storage_failure(self):
        with (
            patch.object(supabase_client, "get_household_profile_id", return_value="profile-1"),
            patch.object(supabase_client, "_execute", return_value=[]),
        ):
            self.assertFalse(supabase_client.delete_grocery_cart_item("407"))
        with (
            patch.object(supabase_client, "get_household_profile_id", return_value="profile-1"),
            patch.object(supabase_client, "_execute", return_value=[{"id": 407}]),
        ):
            self.assertTrue(supabase_client.delete_grocery_cart_item("407"))

    def test_a_repeated_delete_still_returns_the_cart(self):
        with (
            patch.object(main, "delete_grocery_cart_item", return_value=False),
            patch.object(main, "get_grocery_cart", return_value=[{"id": 1}]),
        ):
            body = asyncio.run(main.delete_grocery_cart_item_endpoint("407"))
        self.assertEqual(body["status"], "already_removed")
        self.assertEqual(body["grocery_cart"], [{"id": 1}])


if __name__ == "__main__":
    unittest.main()
