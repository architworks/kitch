"""The checkout agent is built once, off the request loop, and its startup steps are reported truthfully."""

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


    def test_startup_reports_each_step_and_reaches_ready(self):
        import subprocess
        script = """
import os, sys, time
os.environ["KITCH_DATABASE_BACKEND"] = "supabase"
os.environ["KITCH_AUTH_SESSION_SECRET"] = "s" * 40
os.environ["SWIGGY_INSTAMART_ENABLED"] = "true"
from fastapi.testclient import TestClient
from app import main
seen = []
with TestClient(main.app) as client:
    # The live check answers at once while the agent loads in the background.
    assert client.get("/api/health/live").status_code == 200
    since = ""
    for _ in range(60):
        body = client.get("/api/health/startup", params={"since": since}).json()
        assert body["instamart"] is True and body["stage"] in main.STARTUP_STAGES, body
        if not seen or seen[-1] != body["stage"]:
            seen.append(body["stage"])
        if body["stage"] == "ready":
            break
        since = body["stage"]
assert seen[-1] == "ready", seen
assert seen == sorted(seen, key=main.STARTUP_STAGES.index), seen
assert "app.grocery_checkout" in sys.modules
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1] / "backend",
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-800:] or result.stdout[-800:])

    def test_startup_is_ready_at_once_without_instamart(self):
        import subprocess
        script = """
import os, sys
os.environ["KITCH_DATABASE_BACKEND"] = "supabase"
os.environ["KITCH_AUTH_SESSION_SECRET"] = "s" * 40
os.environ["SWIGGY_INSTAMART_ENABLED"] = "false"
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    body = client.get("/api/health/startup").json()
assert body["stage"] == "ready" and body["instamart"] is False, body
assert "app.grocery_checkout" not in sys.modules
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1] / "backend",
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-800:] or result.stdout[-800:])


if __name__ == "__main__":
    unittest.main()
