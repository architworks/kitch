"""The checkout agent is built off the request loop, once, and preloaded only when Instamart is on."""

import asyncio
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("KITCH_DATABASE_BACKEND", "supabase")

from app import main  # noqa: E402


class GroceryCheckoutPreloadTests(unittest.TestCase):
    def test_ready_builds_once_in_a_worker_thread(self):
        lazy = main._LazyGroceryCheckoutService()
        built_on = []

        class FakeService:
            def __init__(self):
                built_on.append(threading.current_thread() is threading.main_thread())

        fake_module = type(sys)("app.grocery_checkout")
        fake_module.GroceryCheckoutService = FakeService

        async def run():
            # The loop keeps answering other work while the service builds.
            first, second = await asyncio.gather(lazy.ready(), lazy.ready())
            return first, second

        with patch.dict(sys.modules, {"app.grocery_checkout": fake_module}):
            first, second = asyncio.run(run())
        self.assertIs(first, second)
        self.assertEqual(built_on, [False], "built exactly once, never on the main thread")

    def test_preload_follows_the_instamart_switch(self):
        with patch.dict(os.environ, {"SWIGGY_INSTAMART_ENABLED": "true"}):
            self.assertTrue(main._instamart_enabled())
        with patch.dict(os.environ, {"SWIGGY_INSTAMART_ENABLED": "false"}):
            self.assertFalse(main._instamart_enabled())

    def test_a_failed_preload_does_not_raise(self):
        with patch.object(main.grocery_checkout_service, "ready", side_effect=RuntimeError("boom")):
            asyncio.run(main._preload_grocery_checkout_service())


if __name__ == "__main__":
    unittest.main()
