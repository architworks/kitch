"""Provider-neutral checkout orchestration safeguards."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.grocery_checkout import GroceryCheckoutService  # noqa: E402
from app.providers.base import ProviderOperationError  # noqa: E402


class FakeRegistry:
    def __init__(self, adapter):
        self.adapter = adapter

    def get(self, provider_id):
        return self.adapter

    def descriptors(self):
        return []


class ProviderCheckoutServiceTests(unittest.IsolatedAsyncioTestCase):
    def draft_row(self) -> dict:
        native_item = {
            "id": 1,
            "name": "Milk",
            "amount": 1.0,
            "unit": "pack",
            "category": "Dairy",
            "alreadyStocked": False,
        }
        return {
            "id": "draft-1",
            "profile_id": "profile-1",
            "provider": "zepto",
            "provider_environment": "production",
            "selected_address_id": "address-1",
            "selected_native_item_ids": ["1"],
            "native_items": [native_item],
            "mapped_items": [native_item],
            "matched_items": [{"native_item": native_item}],
            "unavailable_items": [],
            "replacements": [],
            "changes": [],
            "provider_cart": {"items": []},
            "cart_summary": {"total_minor": 9900},
            "checkout_context": {},
            "store_context": {"status": "ready"},
            "payment_options": [{"id": "cod", "kind": "cod"}],
            "selected_payment_method_id": "cod",
            "selected_payment_method": {"id": "cod", "kind": "cod"},
            "payment_state": {},
            "order_review_acknowledged": True,
            "can_place_order": True,
            "order_blockers": [],
            "confirmation_token": "token-1",
            "snapshot_hash": "hash-1",
            "status": "ready",
            "last_validated_at": "2026-08-15T00:00:00+00:00",
        }

    def service(self, adapter, instamart_agent=None):
        return GroceryCheckoutService(
            registry=FakeRegistry(adapter),
            cart_mapper=AsyncMock(side_effect=lambda items: items),
            instamart_agent=instamart_agent,
        )

    async def test_instamart_sync_uses_cart_agent_and_persists_confirmed_result(self):
        native_item = self.draft_row()["native_items"][0]
        capture = SimpleNamespace(marker="captured")
        agent = SimpleNamespace(synchronize=AsyncMock(return_value=SimpleNamespace(
            capture=capture,
            final_text="confirmed",
        )))
        result = {
            "status": "success",
            "items": [{"native_item": native_item}],
            "unavailable_items": [],
            "cart_summary": {"total_minor": 9900},
            "store_context": {"status": "ready"},
            "payment_options": [{"id": "Cash", "kind": "cod"}],
        }
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="staging", label="Swiggy Instamart"),
            confirmed_agent_result=lambda items, address, received_capture: result,
            enrich_agent_result_with_payment=AsyncMock(side_effect=lambda value: value),
        )
        service = self.service(adapter, agent)
        saved_review = {"review_id": "draft-agent", "matched_items": result["items"]}
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_grocery_cart", return_value=[native_item]),
            patch("app.grocery_checkout.save_initial_draft", return_value=saved_review) as save_draft,
        ):
            response = await service.sync(
                "swiggy_instamart",
                {
                    "cart_item_ids": ["1"],
                    "selected_address_id": "home-1",
                    "user_instruction": "Move my cart to Instamart",
                },
                authority_source="chat_sync",
            )
        self.assertEqual(response["review"]["review_id"], "draft-agent")
        agent.synchronize.assert_awaited_once()
        call = agent.synchronize.await_args.kwargs
        self.assertEqual(call["source"], "chat_sync")
        self.assertEqual(call["native_items"], [native_item])
        self.assertEqual(call["selected_address_id"], "home-1")
        save_draft.assert_called_once()

    async def test_order_time_change_stops_before_provider_checkout(self):
        row = self.draft_row()
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production", label="Zepto"),
            revalidate_cart=AsyncMock(return_value={"status": "success", "changed": True}),
            place_order=AsyncMock(),
        )
        service = self.service(adapter)
        changed = {**row, "snapshot_hash": "hash-2", "order_review_acknowledged": False}
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=row),
            patch("app.grocery_checkout.get_grocery_cart", return_value=row["native_items"]),
            patch("app.grocery_checkout.native_snapshot_matches", return_value=True),
            patch("app.grocery_checkout.save_revalidated_draft", return_value=(changed, True)),
        ):
            with self.assertRaises(ProviderOperationError) as caught:
                await service.place_order(
                    "zepto",
                    {
                        "review_id": "draft-1",
                        "confirmation_token": "token-1",
                        "approved_snapshot_hash": "hash-1",
                        "order_review_acknowledged": True,
                    },
                )
        self.assertEqual(caught.exception.code, "provider_cart_changed")
        adapter.place_order.assert_not_awaited()

    async def test_unchanged_review_persists_order_outcome(self):
        row = self.draft_row()
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production", label="Zepto"),
            revalidate_cart=AsyncMock(return_value={"status": "success", "changed": False}),
            place_order=AsyncMock(return_value={
                "status": "success",
                "provider_order_ids": ["order-1"],
                "order_results": [{"order_id": "order-1", "status": "placed"}],
            }),
        )
        service = self.service(adapter)
        pending = {**row, "status": "checkout_pending", "checkout_attempt_id": "attempt-1"}
        final = {**row, "status": "ordered", "provider_order_ids": ["order-1"]}
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=row),
            patch("app.grocery_checkout.get_grocery_cart", return_value=row["native_items"]),
            patch("app.grocery_checkout.native_snapshot_matches", return_value=True),
            patch("app.grocery_checkout.save_revalidated_draft", return_value=(row, False)),
            patch("app.grocery_checkout.save_provider_checkout_draft", return_value=pending),
            patch("app.grocery_checkout.save_order_outcome", return_value=final) as save_outcome,
        ):
            response = await service.place_order(
                "zepto",
                {
                    "review_id": "draft-1",
                    "confirmation_token": "token-1",
                    "approved_snapshot_hash": "hash-1",
                    "order_review_acknowledged": True,
                },
            )
        self.assertEqual(response["status"], "success")
        adapter.place_order.assert_awaited_once()
        save_outcome.assert_called_once()

    async def test_revalidation_invalidates_native_cart_drift(self):
        row = self.draft_row()
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production", label="Zepto"),
            revalidate_cart=AsyncMock(),
        )
        service = self.service(adapter)
        invalidated = {**row, "status": "blocked"}
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=row),
            patch("app.grocery_checkout.get_grocery_cart", return_value=[]),
            patch("app.grocery_checkout.native_snapshot_matches", return_value=False),
            patch("app.grocery_checkout.invalidate_draft_for_native_drift", return_value=invalidated),
        ):
            with self.assertRaises(ProviderOperationError) as caught:
                await service.revalidate("zepto")
        self.assertEqual(caught.exception.code, "native_cart_changed")
        self.assertEqual(caught.exception.draft["status"], "blocked")
        adapter.revalidate_cart.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
