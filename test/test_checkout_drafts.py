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
    refresh_checkout_eligibility,
    save_initial_draft,
    save_revalidated_draft,
)


def persisted_row(payload: dict) -> dict:
    return {
        "id": "draft-1",
        "profile_id": "profile-1",
        "provider": "zepto",
        "provider_environment": "production",
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
            "provider_cart": {"items": [{**product, "quantity": 1}]},
            "cart_summary": {"currency": "INR", "total_minor": 9900},
            "checkout_context": {"payment_methods": [{"id": "cod"}]},
            "payment_options": [{"id": "cod", "kind": "cod"}],
            "store_context": {"status": "ready", "state": "store_context_ready"},
        }

    def test_initial_draft_is_orderable_when_confirmed_cart_is_complete(self):
        native_item = self.native_item()
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload, **kwargs: persisted_row({
                "provider": kwargs["provider"],
                "provider_environment": kwargs["provider_environment"],
                **payload,
            }),
        ):
            review = save_initial_draft(
                [native_item],
                [native_item],
                self.successful_result(),
                "address-1",
                "zepto",
                "production",
                "Zepto",
            )

        self.assertEqual(review["status"], "ready")
        self.assertTrue(review["can_place_order"])
        self.assertTrue(review["confirmation_token"])
        self.assertIsNone(review["selected_payment_method_id"])

    def test_instamart_automatically_selects_its_sole_payment_method(self):
        native_item = self.native_item()
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload, **kwargs: persisted_row({
                "provider": kwargs["provider"],
                "provider_environment": kwargs["provider_environment"],
                **payload,
            }),
        ):
            review = save_initial_draft(
                [native_item],
                [native_item],
                self.successful_result(),
                "address-1",
                "swiggy_instamart",
                "staging",
                "Swiggy Instamart",
            )

        self.assertEqual(review["selected_payment_method_id"], "cod")
        self.assertEqual(review["selected_payment_method"], {"id": "cod", "kind": "cod"})

    def test_instamart_does_not_autoselect_when_multiple_methods_exist(self):
        native_item = self.native_item()
        result = self.successful_result()
        result["payment_options"] = [
            {"id": "upi", "kind": "upi"},
            {"id": "cod", "kind": "cod"},
        ]
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload, **kwargs: persisted_row({
                "provider": kwargs["provider"],
                "provider_environment": kwargs["provider_environment"],
                **payload,
            }),
        ):
            review = save_initial_draft(
                [native_item],
                [native_item],
                result,
                "address-1",
                "swiggy_instamart",
                "staging",
                "Swiggy Instamart",
            )

        self.assertIsNone(review["selected_payment_method_id"])

    def test_no_confirmed_items_blocks_order(self):
        native_item = self.native_item()
        result = {
            **self.successful_result(),
            "status": "blocked",
            "items": [],
            "unavailable_items": [{"name": "Milk"}],
        }
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload, **kwargs: persisted_row({
                "provider": kwargs["provider"],
                "provider_environment": kwargs["provider_environment"],
                **payload,
            }),
        ):
            review = save_initial_draft(
                [native_item],
                [native_item],
                result,
                "address-1",
                "zepto",
                "production",
                "Zepto",
            )

        self.assertEqual(review["status"], "blocked")
        self.assertFalse(review["can_place_order"])
        self.assertIsNone(review["confirmation_token"])

    def test_partial_provider_cart_is_orderable_with_unavailable_items_disclosed(self):
        first_item = self.native_item()
        second_item = {**self.native_item(), "id": 2, "name": "Chia Seeds"}
        result = {
            **self.successful_result(),
            "status": "blocked",
            "unavailable_items": [{
                "name": "Chia Seeds",
                "reason": "No orderable provider product was found.",
            }],
        }
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload, **kwargs: persisted_row({
                "provider": kwargs["provider"],
                "provider_environment": kwargs["provider_environment"],
                **payload,
            }),
        ):
            review = save_initial_draft(
                [first_item, second_item],
                [first_item, second_item],
                result,
                "address-1",
                "swiggy_instamart",
                "staging",
                "Swiggy Instamart",
            )

        self.assertEqual(review["status"], "ready")
        self.assertTrue(review["can_place_order"])
        self.assertTrue(review["confirmation_token"])
        self.assertEqual(review["unavailable_items"], result["unavailable_items"])
        self.assertEqual(review["order_blockers"], [])

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
                "provider_cart": self.successful_result()["provider_cart"],
                "cart_summary": self.successful_result()["cart_summary"],
                "checkout_context": self.successful_result()["checkout_context"],
                "payment_options": self.successful_result()["payment_options"],
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
            side_effect=lambda payload, **kwargs: persisted_row({**initial, **payload}),
        ):
            review, changed = save_revalidated_draft(initial, changed_result)

        self.assertTrue(changed)
        self.assertIsNone(review["selected_payment_method_id"])
        self.assertFalse(review["order_review_acknowledged"])
        self.assertNotEqual(review["confirmation_token"], "old-token")

    def test_instamart_revalidation_keeps_its_sole_current_method_selected(self):
        native_item = self.native_item()
        initial = persisted_row({
            "provider": "swiggy_instamart",
            "provider_environment": "staging",
            "selected_address_id": "address-1",
            "selected_native_item_ids": ["1"],
            "native_items": [native_item],
            "mapped_items": [native_item],
            "matched_items": self.successful_result()["items"],
            "payment_options": self.successful_result()["payment_options"],
            "selected_payment_method_id": "cod",
            "selected_payment_method": {"id": "cod", "kind": "cod"},
            "order_review_acknowledged": True,
            "can_place_order": True,
            "confirmation_token": "old-token",
            "status": "ready",
        })
        changed_result = {
            **self.successful_result(),
            "changed": True,
            "changes": [{"type": "price_changed"}],
        }
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload, **kwargs: persisted_row({**initial, **payload}),
        ):
            review, changed = save_revalidated_draft(initial, changed_result)

        self.assertTrue(changed)
        self.assertEqual(review["selected_payment_method_id"], "cod")
        self.assertFalse(review["order_review_acknowledged"])

    def test_revalidation_unlocks_a_previously_blocked_partial_draft(self):
        first_item = self.native_item()
        second_item = {**self.native_item(), "id": 2, "name": "Chia Seeds"}
        initial = persisted_row({
            "selected_address_id": "address-1",
            "selected_native_item_ids": ["1", "2"],
            "native_items": [first_item, second_item],
            "mapped_items": [first_item, second_item],
            "matched_items": self.successful_result()["items"],
            "unavailable_items": [{"name": "Chia Seeds"}],
            "provider_cart": self.successful_result()["provider_cart"],
            "cart_summary": self.successful_result()["cart_summary"],
            "checkout_context": self.successful_result()["checkout_context"],
            "payment_options": self.successful_result()["payment_options"],
            "store_context": self.successful_result()["store_context"],
            "can_place_order": False,
            "order_blockers": ["Every selected native item must have a match."],
            "confirmation_token": None,
            "snapshot_hash": "old-hash",
            "status": "blocked",
        })
        result = {
            **self.successful_result(),
            "unavailable_items": [{"name": "Chia Seeds"}],
            "changed": False,
        }
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload, **kwargs: persisted_row({**initial, **payload}),
        ):
            review, changed = save_revalidated_draft(initial, result)

        self.assertFalse(changed)
        self.assertEqual(review["status"], "ready")
        self.assertTrue(review["can_place_order"])
        self.assertTrue(review["confirmation_token"])
        self.assertEqual(review["order_blockers"], [])

    def test_restore_rederives_obsolete_partial_cart_blockers(self):
        initial = persisted_row({
            "status": "blocked",
            "native_items": [self.native_item(), {**self.native_item(), "id": 2}],
            "matched_items": self.successful_result()["items"],
            "unavailable_items": [{"name": "Chia Seeds"}],
            "provider_cart": self.successful_result()["provider_cart"],
            "cart_summary": self.successful_result()["cart_summary"],
            "checkout_context": self.successful_result()["checkout_context"],
            "payment_options": self.successful_result()["payment_options"],
            "store_context": self.successful_result()["store_context"],
            "can_place_order": False,
            "order_blockers": ["Every selected native item must have a match."],
            "confirmation_token": None,
        })
        with patch(
            "app.checkout_drafts.save_provider_checkout_draft",
            side_effect=lambda payload, **kwargs: persisted_row({**initial, **payload}),
        ):
            refreshed = refresh_checkout_eligibility(initial, "Swiggy Instamart")

        self.assertEqual(refreshed["status"], "ready")
        self.assertTrue(refreshed["can_place_order"])
        self.assertEqual(refreshed["order_blockers"], [])
        self.assertTrue(refreshed["confirmation_token"])

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

    def test_hash_covers_normalized_provider_price_and_pack(self):
        review = {
            "native_items": [self.native_item()],
            "matched_items": [{
                "native_item": self.native_item(),
                "matched_product": {
                    "spin_id": "spin-1",
                    "sku_id": "sku-1",
                    "price_minor": 9900,
                    "pack_size": "1 L",
                },
                "cart_item": {"quantity": 1},
            }],
            "cart_summary": {"total_minor": 10400},
            "selected_address_id": "address-1",
        }
        changed_price = {
            **review,
            "matched_items": [{
                **review["matched_items"][0],
                "matched_product": {
                    **review["matched_items"][0]["matched_product"],
                    "price_minor": 10900,
                },
            }],
        }
        changed_pack = {
            **review,
            "matched_items": [{
                **review["matched_items"][0],
                "matched_product": {
                    **review["matched_items"][0]["matched_product"],
                    "pack_size": "500 mL",
                },
            }],
        }
        self.assertNotEqual(checkout_snapshot_hash(review), checkout_snapshot_hash(changed_price))
        self.assertNotEqual(checkout_snapshot_hash(review), checkout_snapshot_hash(changed_pack))


if __name__ == "__main__":
    unittest.main()
