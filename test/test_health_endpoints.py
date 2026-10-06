"""Liveness and readiness endpoint contracts."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from starlette.responses import Response


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_SECRET_KEY"] = "sb_secret_unit_test_credential_value"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["SUPABASE_KEY"] = ""
os.environ.setdefault("GOOGLE_API_KEY", "unit-test-key")

from app import main  # noqa: E402
from app.persistence import PersistenceError  # noqa: E402
from app.providers.base import ProviderCapabilities, ProviderDescriptor  # noqa: E402
from app.providers import registry as registry_module  # noqa: E402


class HealthEndpointTests(unittest.IsolatedAsyncioTestCase):
    def test_hosted_cors_default_excludes_local_origins(self):
        with patch.dict(os.environ, {}, clear=False), patch.object(
            main, "auth_required", return_value=True,
        ):
            os.environ.pop("KITCH_ALLOWED_ORIGINS", None)
            self.assertEqual(
                main._configured_allowed_origins(),
                ["https://kitch-meal-planner.vercel.app"],
            )

        with patch.dict(os.environ, {
            "KITCH_ALLOWED_ORIGINS": "https://one.example, https://two.example",
        }), patch.object(main, "auth_required", return_value=True):
            self.assertEqual(main._configured_allowed_origins(), [
                "https://one.example", "https://two.example",
            ])

    def test_security_headers_include_hosted_transport_and_google_popup_policy(self):
        with patch.dict(os.environ, {"VERCEL": "1"}):
            response = main._security_headers(Response())
        self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin-allow-popups")
        self.assertEqual(response.headers["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertIn("includeSubDomains", response.headers["Strict-Transport-Security"])

    def test_provider_callback_defaults_to_same_origin(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FRONTEND_URL", None)
            self.assertEqual(
                main._provider_callback_destination("swiggy_instamart"),
                "/?provider_connection=swiggy_instamart&connection_status=connected",
            )
        with patch.dict(os.environ, {"FRONTEND_URL": "https://kitch.example/"}):
            self.assertEqual(
                main._provider_callback_destination("swiggy_instamart"),
                "https://kitch.example/?provider_connection=swiggy_instamart&connection_status=connected",
            )

    def test_confirmation_action_is_recovered_from_nested_tool_response(self):
        action = main._confirmation_action_from_tool_response({
            "result": {
                "status": "confirmation_required",
                "type": "CONFIRM_DESTRUCTIVE_ACTION",
                "action_id": "pending-1",
                "impact": {"title": "Remove these planned meals?"},
            },
        })
        self.assertEqual(action, {
            "type": "CONFIRM_DESTRUCTIVE_ACTION",
            "action_id": "pending-1",
            "impact": {"title": "Remove these planned meals?"},
        })

    async def test_liveness_has_no_dependency_checks(self):
        with (
            patch.object(main, "validate_persistence_readiness") as persistence,
            patch.object(main.provider_registry, "readiness", new=AsyncMock()) as providers,
            patch.object(main, "memory_readiness", new=AsyncMock()) as memory,
        ):
            result = await main.liveness_check()

        self.assertEqual(result, {"status": "alive", "service": "kitch-backend"})
        persistence.assert_not_called()
        providers.assert_not_awaited()
        memory.assert_not_awaited()

    async def test_readiness_runs_blocking_persistence_check_off_event_loop(self):
        event_loop_thread = threading.get_ident()
        worker_threads: list[int] = []

        def validate():
            worker_threads.append(threading.get_ident())
            return {"status": "ready"}

        providers = [{"provider": "zepto", "state": "disconnected"}]
        with (
            patch.object(main, "auth_required", return_value=False),
            patch.object(main, "validate_persistence_readiness", side_effect=validate),
            patch.object(
                main.provider_registry,
                "readiness",
                new=AsyncMock(return_value=providers),
            ),
            patch.object(
                main,
                "memory_readiness",
                new=AsyncMock(return_value={"backend": "in_memory", "state": "ready"}),
            ),
        ):
            result = await main.readiness_check()

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["providers"], providers)
        self.assertEqual(result["memory"]["state"], "ready")
        self.assertTrue(worker_threads)
        self.assertNotEqual(worker_threads[0], event_loop_thread)

    async def test_readiness_returns_503_for_core_persistence_failure(self):
        failure = PersistenceError(
            operation="readiness_check",
            table="profiles",
            supabase_code="TimeoutError",
            retryable=True,
        )
        with (
            patch.object(main, "validate_persistence_readiness", side_effect=failure),
            patch.object(
                main.provider_registry,
                "readiness",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                main,
                "memory_readiness",
                new=AsyncMock(return_value={"backend": "vertex", "state": "degraded"}),
            ),
        ):
            response = await main.readiness_check()

        self.assertEqual(response.status_code, 503)
        payload = json.loads(response.body)
        self.assertEqual(payload["detail"]["code"], "persistence_unavailable")

    async def test_memory_failure_is_degraded_without_making_core_unready(self):
        with (
            patch.object(main, "auth_required", return_value=False),
            patch.object(
                main,
                "validate_persistence_readiness",
                return_value={"status": "ready"},
            ),
            patch.object(
                main.provider_registry,
                "readiness",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(
                main,
                "memory_readiness",
                new=AsyncMock(return_value={
                    "backend": "vertex",
                    "state": "degraded",
                    "durable": True,
                    "diagnostic": "Memory Bank authentication failed.",
                }),
            ),
        ):
            result = await main.readiness_check()

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["memory"]["state"], "degraded")

    async def test_unauthenticated_hosted_readiness_hides_component_details(self):
        with (
            patch.object(main, "auth_required", return_value=True),
            patch.object(main, "current_identity", return_value=None),
            patch.object(
                main,
                "validate_persistence_readiness",
                return_value={"status": "ready", "tables": ["profiles"]},
            ),
            patch.object(main.provider_registry, "readiness", new=AsyncMock()) as providers,
            patch.object(main, "memory_readiness", new=AsyncMock()) as memory,
        ):
            result = await main.readiness_check()

        self.assertEqual(result, {
            "status": "ready",
            "service": "kitch-backend",
            "persistence": "ready",
        })
        providers.assert_not_awaited()
        memory.assert_not_awaited()


class ProviderReadinessTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_timeout_is_degraded_without_raising(self):
        descriptor = ProviderDescriptor(
            id="slow_provider",
            label="Slow Provider",
            brand_label="slow",
            description="fixture",
            enabled=True,
            state="connected",
            message="Connected.",
            environment="local",
            capabilities=ProviderCapabilities(),
        )

        class SlowAdapter:
            def descriptor(self):
                return descriptor

            async def readiness(self):
                await asyncio.sleep(1)
                return {"provider": descriptor.id, "state": "ready"}

        adapters = [SlowAdapter(), SlowAdapter()]
        with (
            patch.object(
                registry_module,
                "ZeptoProviderAdapter",
                return_value=adapters[0],
            ),
            patch.object(
                registry_module,
                "InstamartProviderAdapter",
                return_value=adapters[1],
            ),
            patch.object(registry_module, "PROVIDER_READINESS_TIMEOUT_SECONDS", 0.01),
        ):
            result = await registry_module.ProviderRegistry().readiness()

        self.assertEqual(result[0]["state"], "degraded")
        self.assertIn("timed out", result[0]["message"])
        self.assertEqual(result[1]["state"], "degraded")
        self.assertEqual(result[-1]["provider"], "blinkit")


if __name__ == "__main__":
    unittest.main()
