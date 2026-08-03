"""Regression tests for durable provider checkout draft behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.checkout_drafts import (  # noqa: E402
    checkout_snapshot_hash,
    native_snapshot_matches,
    save_initial_draft,
    save_revalidated_draft,
)


def persisted_row(payload: dict) -> dict:
    return {
        "id": "draft-1",
        "profile_id": "profile-1",
        "provider": "zepto",
        "created_at": "2026-08-03T00:00:00+00:00",
        "updated_at": "2026-08-03T00:00:00+00:00",
        **payload,
    }


class CheckoutDraftTests(unittest.TestCase):
    def native_item(self) -> dict:
        return {
            "id": 1,
            "name": "Milk",
            "amount": 1.0,
            "unit": "pack",
            "category": "Dairy",
            "alreadyStocked": False,
        }

    def successful_result(self) -> dict:
        native_item = self.native_item()
        product = {
            "name": "Zepto Milk",
            "productVariantId": "variant-1",
            "storeProductId": "store-product-1",
            "availableQuantity": 10,
            "price": 9900,
        }
        return {
            "status": "success",
            "items": [
                {
                    "native_item": native_item,
                    "matched_product": product,
                    "cart_item": {**product, "quantity": 1},
                }
            ],
            "unavailable_items": [],
            "replacements": [],
            "changes": [],
            "zepto_cart": {"items": [{**product, "quantity": 1}]},
            "cart_summary": {"currency": "INR", "total_minor": 9900},
            "checkout_context": {"payment_methods": [{"id": "cod"}]},
            "store_context": {"status": "ready", "state": "store_context_ready"},
        }

    def test_initial_draft_is_orderable_only_when_every_native_item_is_confirmed(self):
        native_item = self.native_item()
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload: persisted_row(payload),
        ):
            review = save_initial_draft(
                [native_item],
                [native_item],
                self.successful_result(),
                "address-1",
            )

        self.assertEqual(review["status"], "ready")
        self.assertTrue(review["can_place_order"])
        self.assertTrue(review["confirmation_token"])

    def test_unresolved_item_blocks_complete_order(self):
        native_item = self.native_item()
        result = {
            **self.successful_result(),
            "status": "blocked",
            "items": [],
            "unavailable_items": [{"name": "Milk"}],
        }
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload: persisted_row(payload),
        ):
            review = save_initial_draft(
                [native_item],
                [native_item],
                result,
                "address-1",
            )

        self.assertEqual(review["status"], "blocked")
        self.assertFalse(review["can_place_order"])
        self.assertIsNone(review["confirmation_token"])

    def test_material_revalidation_change_resets_payment_and_approval(self):
        native_item = self.native_item()
        initial = persisted_row(
            {
                "selected_address_id": "address-1",
                "selected_native_item_ids": ["1"],
                "native_items": [native_item],
                "mapped_items": [native_item],
                "matched_items": self.successful_result()["items"],
                "unavailable_items": [],
                "replacements": [],
                "changes": [],
                "provider_cart": self.successful_result()["zepto_cart"],
                "cart_summary": self.successful_result()["cart_summary"],
                "checkout_context": self.successful_result()["checkout_context"],
                "store_context": self.successful_result()["store_context"],
                "selected_payment_method_id": "cod",
                "order_review_acknowledged": True,
                "can_place_order": True,
                "order_blockers": [],
                "confirmation_token": "old-token",
                "snapshot_hash": "old-hash",
                "status": "ready",
            }
        )
        changed_result = {
            **self.successful_result(),
            "changed": True,
            "changes": [{"type": "replacement"}],
            "replacements": [{"reason": "unavailable"}],
        }
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload: persisted_row({**initial, **payload}),
        ):
            review, changed = save_revalidated_draft(initial, changed_result)

        self.assertTrue(changed)
        self.assertIsNone(review["selected_payment_method_id"])
        self.assertFalse(review["order_review_acknowledged"])
        self.assertNotEqual(review["confirmation_token"], "old-token")

    def test_native_snapshot_detects_quantity_or_membership_drift(self):
        native_item = self.native_item()
        row = persisted_row(
            {
                "selected_native_item_ids": ["1"],
                "native_items": [native_item],
            }
        )
        self.assertTrue(native_snapshot_matches(row, [native_item]))
        self.assertFalse(
            native_snapshot_matches(row, [{**native_item, "amount": 2.0}])
        )
        self.assertFalse(native_snapshot_matches(row, []))

    def test_hash_changes_with_confirmed_provider_projection(self):
        review = {
            "native_items": [self.native_item()],
            "matched_items": [
                {
                    "native_item": self.native_item(),
                    "matched_product": {
                        "productVariantId": "variant-1",
                        "storeProductId": "store-product-1",
                    },
                    "cart_item": {"quantity": 1},
                }
            ],
            "cart_summary": {"total_minor": 9900},
            "selected_address_id": "address-1",
        }
        changed = {
            **review,
            "matched_items": [
                {
                    **review["matched_items"][0],
                    "matched_product": {
                        "productVariantId": "variant-2",
                        "storeProductId": "store-product-2",
                    },
                }
            ],
        }
        self.assertNotEqual(
            checkout_snapshot_hash(review),
            checkout_snapshot_hash(changed),
        )


if __name__ == "__main__":
    unittest.main()
