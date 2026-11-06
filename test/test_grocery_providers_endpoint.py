"""Listing grocery providers must not build the checkout service (a slow cold import)."""

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("KITCH_DATABASE_BACKEND", "supabase")

from app import main  # noqa: E402


class GroceryProvidersEndpointTests(unittest.TestCase):
    def test_lists_providers_without_loading_the_checkout_service(self):
        with (
            patch.object(main.grocery_checkout_service, "_load", side_effect=AssertionError("checkout service loaded")),
            patch.object(main, "get_selected_grocery_provider", return_value="swiggy_instamart"),
            patch.object(main.provider_registry, "descriptors", return_value=[{"id": "swiggy_instamart"}]),
        ):
            body = asyncio.run(main.grocery_providers_endpoint())
        self.assertEqual(body["selected_provider"], "swiggy_instamart")
        self.assertEqual([p["id"] for p in body["providers"]], ["swiggy_instamart"])


if __name__ == "__main__":
    unittest.main()
