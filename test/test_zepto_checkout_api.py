"""API-level safeguards for durable Zepto checkout revalidation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import main  # noqa: E402


class ZeptoCheckoutApiTests(unittest.IsolatedAsyncioTestCase):
    def draft_row(self) -> dict:
        native_item = {
            "id": 1,
            "name": "Milk",
            "amount": 1.0,
            "unit": "pack",
            "alreadyStocked": False,
        }
        return {
            "id": "draft-1",
            "provider": "zepto",
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
            "selected_payment_method_id": "cod",
            "order_review_acknowledged": True,
            "can_place_order": True,
            "order_blockers": [],
            "confirmation_token": "token-1",
            "snapshot_hash": "hash-1",
            "status": "ready",
            "last_validated_at": "2026-08-03T00:00:00+00:00",
        }

    async def test_order_time_change_returns_409_without_placing_order(self):
        row = self.draft_row()
        changed_review = {
            **main.draft_row_to_review(row),
            "snapshot_hash": "hash-2",
            "order_review_acknowledged": False,
        }
        adapter = SimpleNamespace(
            revalidate_cart=AsyncMock(return_value={"status": "success", "changed": True}),
            place_order=AsyncMock(),
        )
        with (
            patch.object(main, "claim_provider_checkout_operation", return_value=True),
            patch.object(main, "release_provider_checkout_operation", return_value=True),
            patch.object(main, "get_provider_checkout_draft", return_value=row),
            patch.object(main, "get_grocery_cart", return_value=row["native_items"]),
            patch.object(main, "native_snapshot_matches", return_value=True),
            patch.object(main, "save_revalidated_draft", return_value=(changed_review, True)),
            patch.object(main, "ZeptoProviderAdapter", return_value=adapter),
        ):
            response = await main.place_zepto_order_endpoint(
                {
                    "review_id": "draft-1",
                    "confirmation_token": "token-1",
                    "approved_snapshot_hash": "hash-1",
                    "order_review_acknowledged": True,
                }
            )

        self.assertEqual(response.status_code, 409)
        body = json.loads(response.body)
        self.assertEqual(body["detail"]["code"], "provider_cart_changed")
        adapter.place_order.assert_not_awaited()

    async def test_unchanged_final_revalidation_can_reach_provider_order(self):
        row = self.draft_row()
        review = main.draft_row_to_review(row)
        adapter = SimpleNamespace(
            revalidate_cart=AsyncMock(return_value={"status": "success", "changed": False}),
            place_order=AsyncMock(return_value={"status": "success", "provider": "zepto"}),
        )
        with (
            patch.object(main, "claim_provider_checkout_operation", return_value=True),
            patch.object(main, "release_provider_checkout_operation", return_value=True),
            patch.object(main, "get_provider_checkout_draft", return_value=row),
            patch.object(main, "get_grocery_cart", return_value=row["native_items"]),
            patch.object(main, "native_snapshot_matches", return_value=True),
            patch.object(main, "save_revalidated_draft", return_value=(review, False)),
            patch.object(main, "delete_provider_checkout_draft", return_value=True) as delete_draft,
            patch.object(main, "ZeptoProviderAdapter", return_value=adapter),
        ):
            response = await main.place_zepto_order_endpoint(
                {
                    "review_id": "draft-1",
                    "confirmation_token": "token-1",
                    "approved_snapshot_hash": "hash-1",
                    "order_review_acknowledged": True,
                }
            )

        self.assertEqual(response["status"], "success")
        adapter.place_order.assert_awaited_once()
        delete_draft.assert_called_once()

    async def test_revalidation_invalidates_draft_when_native_cart_changed(self):
        row = self.draft_row()
        invalidated = {**main.draft_row_to_review(row), "status": "blocked"}
        with (
            patch.object(main, "claim_provider_checkout_operation", return_value=True),
            patch.object(main, "release_provider_checkout_operation", return_value=True),
            patch.object(main, "get_provider_checkout_draft", return_value=row),
            patch.object(main, "get_grocery_cart", return_value=[]),
            patch.object(main, "native_snapshot_matches", return_value=False),
            patch.object(main, "invalidate_draft_for_native_drift", return_value=invalidated),
        ):
            response = await main.revalidate_zepto_cart_endpoint()

        self.assertEqual(response.status_code, 409)
        body = json.loads(response.body)
        self.assertEqual(body["detail"]["code"], "native_cart_changed")


if __name__ == "__main__":
    unittest.main()
