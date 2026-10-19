"""Provider-neutral checkout orchestration safeguards."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.grocery_checkout import describe_material_changes, GroceryCheckoutService  # noqa: E402
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
            "purchaseAmount": 1,
            "purchaseUnit": "pack",
            "pantryAllocation": {},
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

    async def test_read_cart_from_chat_normalizes_alias_and_returns_live_values(self):
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(
                environment="local",
                label="Swiggy Instamart",
            ),
            get_cart=AsyncMock(return_value={
                "status": "success",
                "provider": "swiggy_instamart",
                "provider_cart": {
                    "items": [{
                        "name": "Farm Eggs",
                        "pack_size": "12 pieces",
                        "quantity": 1,
                        "price_minor": 12000,
                        "line_total_minor": 12000,
                    }],
                    "multi_store": False,
                },
                "cart_summary": {
                    "currency": "INR",
                    "subtotal_minor": 12000,
                    "fees": [{"label": "Handling Fee", "amount_minor": 1200}],
                    "total_minor": 13200,
                    "total_source": "provider",
                },
            }),
        )
        service = self.service(adapter)

        response = await service.read_cart_from_chat("Instamart")

        adapter.get_cart.assert_awaited_once()
        self.assertEqual(response["provider"], "swiggy_instamart")
        self.assertEqual(response["items"][0]["name"], "Farm Eggs")
        self.assertEqual(response["items"][0]["line_total"]["display"], "₹120.00")
        self.assertEqual(response["cart_summary"]["total"]["display"], "₹132.00")
        self.assertEqual(response["source"], "live_provider_cart")

    async def test_live_cart_returns_empty_provider_cart_without_checkout_state(self):
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(
                environment="local",
                label="Swiggy Instamart",
            ),
            get_cart=AsyncMock(return_value={
                "status": "success",
                "provider": "swiggy_instamart",
                "provider_cart": {"items": [], "stores": [], "multi_store": False},
                "cart_summary": {"currency": "INR", "total_minor": 0},
            }),
        )
        service = self.service(adapter)

        response = await service.live_cart("Instamart")

        adapter.get_cart.assert_awaited_once()
        self.assertEqual(response["provider_cart"]["items"], [])
        self.assertEqual(response["cart_summary"]["total_minor"], 0)
        self.assertNotIn("draft", response)
        self.assertNotIn("payment_options", response)

    async def test_chat_payment_choice_resolves_only_current_draft_options(self):
        draft = self.draft_row()
        draft["provider"] = "swiggy_instamart"
        draft["payment_options"] = [
            {
                "id": "gpay://upi/",
                "label": "Google Pay",
                "provider_value": "gpay://upi/",
                "kind": "upi",
            },
            {"id": "Cash", "label": "Cash on delivery", "kind": "cod"},
        ]
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production"),
        )
        service = self.service(adapter)
        service.configure_instamart_review_from_chat = AsyncMock(return_value={
            "status": "success",
        })

        with patch("app.grocery_checkout.get_provider_checkout_draft", return_value=draft):
            result = await service.configure_instamart_review_by_query(
                payment_method_query="Google Pay"
            )

        self.assertEqual(result["status"], "success")
        service.configure_instamart_review_from_chat.assert_awaited_once_with(
            selected_address_id="",
            selected_payment_method_id="gpay://upi/",
        )

    async def test_chat_payment_choice_rejects_unknown_or_ambiguous_text(self):
        draft = self.draft_row()
        draft["native_items"] = self.draft_row()["native_items"]
        draft["payment_options"] = [
            {"id": "gpay://upi/", "label": "Google Pay"},
            {"id": "paytmmp://", "label": "Paytm"},
        ]
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production"),
        )
        service = self.service(adapter)

        with (
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=draft),
            self.assertRaises(ProviderOperationError),
        ):
            await service.configure_instamart_review_by_query(
                payment_method_query="card"
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
        native_changes = [{
            "action": "add",
            "name": "Dairy Milk chocolate",
            "amount": 1,
            "unit": "bar",
        }]
        call_order = []
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True) as claim_operation,
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch(
                "app.grocery_checkout.apply_native_grocery_cart_changes",
                side_effect=lambda changes: call_order.append(("mutate", changes)),
            ) as mutate,
            patch(
                "app.grocery_checkout.get_grocery_cart",
                side_effect=lambda: call_order.append(("read", None)) or [native_item],
            ),
            patch("app.grocery_checkout.save_initial_draft", return_value=saved_review) as save_draft,
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=None),
        ):
            response = await service.sync(
                "swiggy_instamart",
                {
                    "cart_item_ids": ["1"],
                    "selected_address_id": "home-1",
                    "user_instruction": "Move my cart to Instamart",
                    "native_cart_changes": native_changes,
                },
                authority_source="chat_sync",
            )
        self.assertEqual(response["review"]["review_id"], "draft-agent")
        self.assertTrue(response["native_cart_changed"])
        mutate.assert_called_once_with(native_changes)
        self.assertEqual(call_order[0], ("mutate", native_changes))
        self.assertEqual(call_order[1], ("read", None))
        agent.synchronize.assert_awaited_once()
        call = agent.synchronize.await_args.kwargs
        self.assertEqual(call["source"], "chat_sync")
        self.assertEqual(call["native_items"][0]["requiredAmount"], native_item["amount"])
        self.assertEqual(call["native_items"][0]["requiredUnit"], native_item["unit"])
        self.assertEqual(call["native_items"][0]["amount"], native_item["purchaseAmount"])
        self.assertEqual(call["native_items"][0]["unit"], native_item["purchaseUnit"])
        self.assertEqual(call["selected_address_id"], "home-1")
        claim_operation.assert_called_once_with(
            ANY,
            "swiggy_instamart",
            "staging",
            lease_seconds=300,
        )
        save_draft.assert_called_once()

    async def test_combined_chat_request_preserves_native_change_when_provider_is_unavailable(self):
        provider_error = ProviderOperationError(
            provider="swiggy_instamart",
            operation="list_addresses",
            code="provider_unavailable",
            message="Instamart addresses could not be loaded.",
            retryable=True,
        )
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(
                environment="staging",
                label="Swiggy Instamart",
            ),
            list_addresses=AsyncMock(side_effect=provider_error),
        )
        agent = SimpleNamespace(synchronize=AsyncMock())
        service = self.service(adapter, agent)
        changes = [{
            "action": "add",
            "name": "Dairy Milk chocolate",
            "amount": 1,
            "unit": "bar",
        }]
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=None),
            patch("app.grocery_checkout.apply_native_grocery_cart_changes") as mutate,
        ):
            response = await service.sync_from_chat(
                provider_id="swiggy_instamart",
                user_instruction="Add chocolate and sync to Instamart",
                native_cart_changes=changes,
            )

        mutate.assert_called_once_with(changes)
        agent.synchronize.assert_not_awaited()
        self.assertEqual(response["status"], "partial")
        self.assertTrue(response["native_cart_changed"])
        self.assertFalse(response["provider_cart_changed"])
        self.assertIn("native Kitch cart was updated", response["message"])

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

    async def test_order_always_rereads_the_live_cart_even_when_recently_validated(self):
        """Security findings #6 and #19: a captured or recent read is never trusted."""
        from datetime import datetime, timezone
        from app.checkout_drafts import draft_row_to_review
        row = {**self.draft_row(), "last_validated_at": datetime.now(timezone.utc).isoformat()}
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production", label="Zepto"),
            revalidate_cart=AsyncMock(return_value={"status": "success", "items": []}),
            place_order=AsyncMock(return_value={"status": "success", "provider_order_ids": ["order-1"]}),
        )
        service = self.service(adapter)
        unchanged = {**draft_row_to_review(row), "can_place_order": True}
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=row),
            patch("app.grocery_checkout.save_revalidated_draft", return_value=(unchanged, False)),
            patch("app.grocery_checkout.save_provider_checkout_draft", return_value={**row, "status": "checkout_pending"}),
            patch("app.grocery_checkout.save_order_outcome", return_value={**row, "status": "ordered"}),
        ):
            await service.place_order(
                "zepto",
                {
                    "review_id": "draft-1",
                    "confirmation_token": "token-1",
                    "approved_snapshot_hash": row["snapshot_hash"],
                    "order_review_acknowledged": True,
                },
            )
        adapter.revalidate_cart.assert_awaited_once()
        adapter.place_order.assert_awaited_once()

    async def test_changed_live_cart_stops_the_order_even_within_a_minute(self):
        from datetime import datetime, timezone
        from app.checkout_drafts import draft_row_to_review
        row = {**self.draft_row(), "last_validated_at": datetime.now(timezone.utc).isoformat()}
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production", label="Zepto"),
            revalidate_cart=AsyncMock(return_value={"status": "success", "items": []}),
            place_order=AsyncMock(),
        )
        service = self.service(adapter)
        changed = {**draft_row_to_review(row), "changes": [{"type": "extra_items_changed"}]}
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=row),
            patch("app.grocery_checkout.save_revalidated_draft", return_value=(changed, True)),
        ):
            with self.assertRaises(ProviderOperationError) as caught:
                await service.place_order("zepto", {
                    "review_id": "draft-1", "confirmation_token": "token-1",
                    "approved_snapshot_hash": row["snapshot_hash"], "order_review_acknowledged": True,
                })
        self.assertEqual(caught.exception.code, "provider_cart_changed")
        adapter.place_order.assert_not_awaited()

    def test_only_a_higher_total_or_item_change_counts_as_material(self):
        previous = {
            "matched_items": [],
            "cart_summary": {"total_minor": 16400, "fees": [{"label": "Handling Fee", "amount_minor": 1200}]},
            "payment_options": [{"id": "COD"}],
            "unavailable_items": [{"name": "Eggs", "reason": "Out of stock"}],
        }
        cosmetic = GroceryCheckoutService._annotate_revalidation_changes(previous, {
            "items": [],
            "cart_summary": {"total_minor": 15000, "fees": [{"label": "Packing", "amount_minor": 1200}]},
            "payment_options": [{"id": "COD"}, {"id": "PayWithQR"}],
            "unavailable_items": [{"name": "Eggs", "reason": "Not available near you"}],
        })
        self.assertFalse(cosmetic["changed"])

        rain = GroceryCheckoutService._annotate_revalidation_changes(previous, {
            "items": [],
            "cart_summary": {"total_minor": 20000, "fees": [
                {"label": "Handling Fee", "amount_minor": 1200},
                {"label": "Rain Fee", "amount_minor": 3540},
            ]},
        })
        self.assertTrue(rain["changed"])
        bill = rain["changes"][0]
        self.assertEqual(bill["type"], "bill_changed")
        self.assertEqual(bill["added_fees"], [{"label": "Rain Fee", "amount_minor": 3540}])
        message = describe_material_changes(rain["changes"], "Swiggy Instamart")
        self.assertIn("Rain Fee ₹35.40 added", message)
        self.assertIn("₹164 → ₹200", message)

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

    async def test_revalidation_does_not_block_on_native_cart_drift(self):
        row = self.draft_row()
        refreshed = {**row, "last_validated_at": "2026-10-11T00:00:00+00:00"}
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production", label="Zepto"),
            revalidate_cart=AsyncMock(return_value={"status": "success", "changed": False}),
        )
        service = self.service(adapter)
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=row),
            patch("app.grocery_checkout.get_grocery_cart", return_value=[]),
            patch("app.grocery_checkout.save_revalidated_draft", return_value=(refreshed, False)),
        ):
            response = await service.revalidate("zepto")
        adapter.revalidate_cart.assert_awaited_once()
        self.assertEqual(response["draft"]["last_validated_at"], refreshed["last_validated_at"])

    async def test_instamart_revalidation_uses_direct_provider_refresh(self):
        row = {**self.draft_row(), "provider": "swiggy_instamart"}
        refreshed_result = {
            "status": "success",
            "items": row["matched_items"],
            "unavailable_items": [],
            "cart_summary": row["cart_summary"],
            "checkout_context": row["checkout_context"],
            "store_context": row["store_context"],
            "payment_options": row["payment_options"],
            "changed": False,
        }
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(
                environment="production",
                label="Swiggy Instamart",
            ),
            revalidate_cart=AsyncMock(return_value=refreshed_result),
        )
        agent = SimpleNamespace(synchronize=AsyncMock())
        service = self.service(adapter, agent)
        saved = {**row, "last_validated_at": "2026-10-08T00:00:00+00:00"}
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=row),
            patch("app.grocery_checkout.get_grocery_cart", return_value=row["native_items"]),
            patch("app.grocery_checkout.save_revalidated_draft", return_value=(saved, False)),
        ):
            response = await service.revalidate("swiggy_instamart")

        adapter.revalidate_cart.assert_awaited_once()
        agent.synchronize.assert_not_awaited()
        self.assertEqual(response["draft"]["last_validated_at"], saved["last_validated_at"])


class CheckoutIntegritySecurityTests(unittest.IsolatedAsyncioTestCase):
    """Security audit 2026-10-17: the owner buys exactly what they approved."""

    draft_row = ProviderCheckoutServiceTests.draft_row
    service = ProviderCheckoutServiceTests.service

    def _adapter(self, **overrides):
        return SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production", label="Instamart"),
            **overrides,
        )

    async def test_approval_of_a_replaced_review_is_refused_with_the_new_review(self):
        """#5: the owner saw draft A; a member replaced it with B before the click."""
        replaced = {**self.draft_row(), "snapshot_hash": "hash-of-B", "order_review_acknowledged": False}
        service = self.service(self._adapter())
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=replaced),
            patch("app.grocery_checkout.update_draft_review_fields") as update_fields,
        ):
            with self.assertRaises(ProviderOperationError) as caught:
                service.update_draft("swiggy_instamart", {
                    "order_review_acknowledged": True, "seen_snapshot_hash": "hash-of-A",
                })
            self.assertEqual(caught.exception.code, "checkout_snapshot_changed")
            self.assertEqual(caught.exception.draft["snapshot_hash"], "hash-of-B")
            update_fields.assert_not_called()

            # Acknowledging the review actually on screen still works.
            update_fields.return_value = {"snapshot_hash": "hash-of-B-acknowledged"}
            response = service.update_draft("swiggy_instamart", {
                "order_review_acknowledged": True, "seen_snapshot_hash": "hash-of-B",
            })
            self.assertEqual(response["draft"]["snapshot_hash"], "hash-of-B-acknowledged")

    async def test_review_edits_wait_for_the_order_lease(self):
        """#12: payment or acknowledgement edits cannot slip in while an order runs."""
        service = self.service(self._adapter())
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=False),
            patch("app.grocery_checkout.update_draft_review_fields") as update_fields,
        ):
            with self.assertRaises(ProviderOperationError) as caught:
                service.update_draft("swiggy_instamart", {"selected_payment_method_id": "cod"})
        self.assertEqual(caught.exception.code, "provider_checkout_busy")
        update_fields.assert_not_called()

    async def test_instamart_chat_cannot_edit_the_cart_while_an_order_runs(self):
        """#12: conversational cart edits take the same lease as ordering."""
        agent = SimpleNamespace(converse=AsyncMock())
        service = self.service(self._adapter(), instamart_agent=agent)
        with patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=False):
            with self.assertRaises(ProviderOperationError) as caught:
                await service.converse_with_instamart("add two packs of milk")
        self.assertEqual(caught.exception.code, "provider_checkout_busy")
        agent.converse.assert_not_awaited()

    async def test_in_flight_attempt_cannot_be_reopened_or_replaced(self):
        """#16: revalidation or a fresh sync used to reopen pending orders."""
        from datetime import datetime, timezone
        pending = {**self.draft_row(), "status": "payment_pending",
                   "updated_at": datetime.now(timezone.utc).isoformat()}
        adapter = self._adapter(revalidate_cart=AsyncMock())
        service = self.service(adapter)
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.get_provider_checkout_draft", return_value=pending),
            patch("app.grocery_checkout.get_grocery_cart") as read_cart,
        ):
            for attempt in (
                lambda: service.revalidate("swiggy_instamart"),
                lambda: service.sync("swiggy_instamart", {"selected_address_id": "home-1"}),
            ):
                with self.assertRaises(ProviderOperationError) as caught:
                    await attempt()
                self.assertEqual(caught.exception.code, "checkout_already_started")
            with self.assertRaises(ProviderOperationError):
                service.update_draft("swiggy_instamart", {"selected_payment_method_id": "cod"})
        adapter.revalidate_cart.assert_not_awaited()
        read_cart.assert_not_called()

    def test_an_unresolved_attempt_is_never_released_by_time_alone(self):
        """Swiggy: an ambiguous result is never permission to resubmit."""
        from datetime import datetime, timedelta, timezone
        from app.grocery_checkout import _attempt_in_flight
        old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        for status in ("unknown", "payment_pending", "checkout_pending"):
            self.assertTrue(_attempt_in_flight({"status": status, "updated_at": old}))
        self.assertFalse(_attempt_in_flight({"status": "ordered", "updated_at": old}))
        self.assertFalse(_attempt_in_flight({"status": "blocked", "updated_at": old}))

    def test_owner_can_start_over_only_after_checking_and_after_the_hold(self):
        from datetime import datetime, timedelta, timezone
        service = self.service(self._adapter())
        now = datetime.now(timezone.utc)
        recent = {**self.draft_row(), "status": "unknown", "updated_at": now.isoformat()}
        settled = {**self.draft_row(), "status": "unknown", "provider_order_ids": ["ord-1"],
                   "updated_at": (now - timedelta(hours=1)).isoformat()}
        with (
            patch("app.grocery_checkout.claim_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.release_provider_checkout_operation", return_value=True),
            patch("app.grocery_checkout.delete_provider_checkout_draft") as delete,
        ):
            with self.assertRaises(ProviderOperationError) as caught:
                service.release_unresolved_attempt("swiggy_instamart", {})
            self.assertEqual(caught.exception.code, "provider_check_required")
            with patch("app.grocery_checkout.get_provider_checkout_draft", return_value=recent):
                with self.assertRaises(ProviderOperationError) as caught:
                    service.release_unresolved_attempt("swiggy_instamart", {"checked_in_provider_app": True})
                self.assertEqual(caught.exception.code, "attempt_still_settling")
            with patch("app.grocery_checkout.get_provider_checkout_draft", return_value=settled):
                response = service.release_unresolved_attempt("swiggy_instamart", {"checked_in_provider_app": True})
        # The unconfirmed attempt is deleted once the owner has checked it.
        self.assertIsNone(response["draft"])
        delete.assert_called_once_with("swiggy_instamart", "production")

    def test_preflight_never_swaps_the_approved_payment_method(self):
        """#9: Instamart now offers only wallet; the owner approved UPI."""
        from app.checkout_drafts import save_revalidated_draft
        approved = {**self.draft_row(), "provider": "swiggy_instamart",
                    "payment_options": [{"id": "upi"}, {"id": "wallet"}],
                    "selected_payment_method_id": "upi", "selected_payment_method": {"id": "upi"}}
        live = {"status": "success", "items": approved["matched_items"], "changed": False,
                "cart_summary": {"total_minor": 9900}, "store_context": {"status": "ready"},
                "payment_options": [{"id": "wallet"}], "checkout_context": {"payment_methods": [{"id": "wallet"}]}}
        with patch("app.checkout_drafts.save_provider_checkout_draft", side_effect=lambda payload, **_: payload):
            review, changed = save_revalidated_draft(approved, live)
        self.assertTrue(changed)
        self.assertFalse(review["order_review_acknowledged"])
        self.assertEqual(review["changes"][-1]["type"], "payment_method_changed")
        self.assertIn("payment method", describe_material_changes(review["changes"], "Instamart"))


class OwnerOnlyGroceryAppTests(unittest.IsolatedAsyncioTestCase):
    """Only the household owner uses the grocery app; members see order status."""

    draft_row = ProviderCheckoutServiceTests.draft_row
    service = ProviderCheckoutServiceTests.service

    def _as(self, role):
        from app.auth import HouseholdIdentity, begin_identity_scope
        return begin_identity_scope(HouseholdIdentity(
            google_subject="subject", email="m@example.com", household_id="household-a",
            owner_profile_id="owner-a", members=({"id": "owner-a", "name": "Owner"},),
            profile_id="member-b" if role == "member" else "owner-a", role=role,
        ))

    async def test_members_cannot_use_the_grocery_app_from_any_path(self):
        from app.auth import end_identity_scope
        agent = SimpleNamespace(converse=AsyncMock(), synchronize=AsyncMock())
        adapter = SimpleNamespace(
            descriptor=lambda: SimpleNamespace(environment="production", label="Instamart"),
            list_addresses=AsyncMock(), get_cart=AsyncMock(), revalidate_cart=AsyncMock(),
            payment_status=AsyncMock(),
        )
        service = self.service(adapter, instamart_agent=agent)
        token = self._as("member")
        try:
            with patch("app.grocery_checkout.claim_provider_checkout_operation") as claim:
                for call in (
                    lambda: service.addresses("swiggy_instamart"),
                    lambda: service.live_cart("swiggy_instamart"),
                    lambda: service.read_cart_from_chat("swiggy_instamart"),
                    lambda: service.sync("swiggy_instamart", {"selected_address_id": "home"}),
                    lambda: service.revalidate("swiggy_instamart"),
                    lambda: service.place_order("swiggy_instamart", {}),
                    lambda: service.payment_status("swiggy_instamart"),
                    lambda: service.converse_with_instamart("add milk"),
                    lambda: service.sync_from_chat(provider_id="swiggy_instamart"),
                    lambda: service.configure_instamart_review_by_query(address_query="home"),
                ):
                    with self.assertRaises(ProviderOperationError) as caught:
                        await call()
                    self.assertEqual(caught.exception.code, "owner_required")
                with self.assertRaises(ProviderOperationError):
                    service.update_draft("swiggy_instamart", {"selected_payment_method_id": "upi"})
                with self.assertRaises(ProviderOperationError) as caught:
                    service.release_unresolved_attempt("swiggy_instamart", {"checked_in_provider_app": True})
                self.assertEqual(caught.exception.code, "owner_required")
                claim.assert_not_called()
        finally:
            end_identity_scope(token)
        for mock in (adapter.list_addresses, adapter.get_cart, adapter.revalidate_cart,
                     adapter.payment_status, agent.converse, agent.synchronize):
            mock.assert_not_awaited()

    async def test_members_see_only_the_order_status(self):
        from app.auth import end_identity_scope
        adapter = SimpleNamespace(descriptor=lambda: SimpleNamespace(environment="production", label="Instamart"))
        service = self.service(adapter)
        ordered = {**self.draft_row(), "status": "ordered", "updated_at": "2026-10-18T10:00:00+00:00"}
        token = self._as("member")
        try:
            with patch("app.grocery_checkout.get_provider_checkout_draft", return_value=ordered):
                response = service.draft("swiggy_instamart")
        finally:
            end_identity_scope(token)
        self.assertIsNone(response["draft"])
        self.assertEqual(response["order_status"], {"status": "ordered", "updated_at": "2026-10-18T10:00:00+00:00"})
        self.assertNotIn("address", str(response))
        self.assertNotIn("payment", str(response))

    async def test_the_owner_still_sees_the_full_review(self):
        from app.auth import end_identity_scope
        adapter = SimpleNamespace(descriptor=lambda: SimpleNamespace(environment="production", label="Instamart"))
        service = self.service(adapter)
        token = self._as("owner")
        try:
            with patch("app.grocery_checkout.get_provider_checkout_draft", return_value=self.draft_row()), patch(
                "app.grocery_checkout.refresh_checkout_eligibility", side_effect=lambda row, label: row,
            ):
                response = service.draft("swiggy_instamart")
        finally:
            end_identity_scope(token)
        self.assertEqual(response["draft"]["selected_address_id"], "address-1")


if __name__ == "__main__":
    unittest.main()
