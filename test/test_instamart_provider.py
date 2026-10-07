"""Thin Instamart adapter tests for agent-confirmed cart translation."""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.commerce_policy import (  # noqa: E402
    CommercePermission,
    CommerceRunCapture,
    commerce_request_context,
)
from app.providers.instamart import InstamartProviderAdapter  # noqa: E402
from app.providers.base import ProviderOperationError  # noqa: E402


class FakeContext:
    def __init__(self, session):
        self.session_value = session

    async def __aenter__(self):
        return self.session_value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeInstamartClient:
    def __init__(
        self,
        *,
        checkout_error=False,
        live_optional_address_schema=False,
        checkout_payload=None,
        cart_payload=None,
        payment_payload=None,
    ):
        self.calls = []
        self.checkout_error = checkout_error
        self.checkout_payload = checkout_payload
        self.cart_payload = cart_payload
        self.payment_payload = payment_payload
        names = {
            "get_addresses", "search_products", "your_go_to_items",
            "update_cart", "get_cart", "checkout", "get_orders",
            "check_payment_status", "get_payment_options",
        }
        required = {
            "search_products": ["addressId", "query"],
            "update_cart": ["selectedAddressId", "items"],
            "checkout": ["addressId"],
            "check_payment_status": ["paasId"],
        }
        self.tools = {
            name: SimpleNamespace(
                name=name,
                inputSchema={
                    "type": "object",
                    "properties": {key: {} for key in required.get(name, [])},
                    "required": (
                        [key for key in required.get(name, []) if key not in {"addressId", "selectedAddressId"}]
                        if live_optional_address_schema
                        else required.get(name, [])
                    ),
                },
            )
            for name in names
        }

    def session(self):
        return FakeContext(object())

    async def list_tools(self, _session):
        return self.tools

    async def call_tool(self, _session, name, arguments=None):
        arguments = arguments or {}
        self.calls.append((name, arguments))
        if name == "get_addresses":
            data = {
                "addresses": [{
                    "id": "home-1",
                    "addressTag": "Home",
                    "addressLine": "HSR Layout, Bengaluru 560102",
                    "isDefault": True,
                    "phoneNumber": "must-not-leak",
                }],
                "pagination": {"hasMore": False},
            }
            return {
                "content": [{"type": "text", "text": json.dumps({"success": True, "data": data})}],
                "structuredContent": data,
            }
        if name == "checkout":
            if self.checkout_error:
                raise TimeoutError("ambiguous timeout")
            return self.checkout_payload or {
                "success": True,
                "data": {"orderId": "order-1", "status": "PLACED"},
            }
        if name == "get_orders":
            return {"success": True, "data": {"orders": []}}
        if name == "update_cart":
            return {"success": True, "data": {"updated": True}}
        if name == "get_cart":
            return self.cart_payload or {
                "success": True,
                "data": {
                    "items": [{
                        "spinId": "eggs-spin-12",
                        "skuId": "eggs-sku-12",
                        "itemName": "Farm Fresh Eggs - 12 pieces",
                        "quantity": 1,
                        "discountedFinalPrice": 92,
                        "itemVariant": "12 pieces",
                    }],
                    "toPay": "₹92.00",
                },
            }
        if name == "get_payment_options":
            return self.payment_payload or {
                "success": True,
                "data": {"availablePaymentMethods": ["COD"]},
            }
        raise AssertionError(f"Unexpected direct tool call: {name}")

    @staticmethod
    def input_schema(tool):
        return tool.inputSchema


class FakeOAuth:
    environment = "staging"

    def connection_status(self):
        return {"state": "connected", "message": "Connected"}


class InstamartProviderTests(unittest.TestCase):
    def adapter(self, client=None):
        adapter = InstamartProviderAdapter(oauth=FakeOAuth(), client=client)
        adapter.enabled = True
        return adapter

    def capture(self, *, include_eggs=True, unresolved=None):
        capture = CommerceRunCapture()
        cart_items = []
        matches = []
        if include_eggs:
            cart_items.append({
                "spinId": "eggs-spin-12",
                "skuId": "eggs-sku-12",
                "itemName": "Farm Fresh Eggs - 12 pieces",
                "quantity": 1,
                "discountedFinalPrice": 92,
                "itemVariant": "12 pieces",
                "imageUrl": "https://example.test/eggs.png",
            })
            matches.append({
                "native_item_id": "180",
                "spin_id": "eggs-spin-12",
                "sku_id": "eggs-sku-12",
                "product_name": "Farm Fresh Eggs - 12 pieces",
                "pack": "12 pieces",
                "cart_quantity": 1,
                "requested_quantity": 12,
                "requested_unit": "piece",
                "fulfilled_quantity": 12,
                "excess_quantity": 0,
                "preference_source": "none",
                "alternatives_considered": ["6 pieces x 2", "30 pieces"],
                "confidence": 0.96,
                "reasoning": "One 12-piece pack exactly fulfils the request.",
            })
        raw = {
            "success": True,
            "data": {
                "items": cart_items,
                "billBreakdown": {
                    "lineItems": [{"label": "Item Total", "value": "₹92.00"}],
                    "toPay": {"label": "To Pay", "value": "₹92.00"},
                },
                "availablePaymentMethods": ["COD"],
            },
        }
        capture.record_tool_result("update_cart", {"success": True})
        capture.record_tool_result("get_cart", raw)
        capture.structured_result = {
            "matches": matches,
            "unresolved_items": unresolved or [],
            "selected_address_id": "home-1",
            "repair_attempted": False,
        }
        return capture

    def test_address_shape_is_normalized_without_phone_number(self):
        result = asyncio.run(self.adapter(FakeInstamartClient()).list_addresses())
        self.assertEqual(result["addresses"], [{
            "id": "home-1",
            "label": "Home",
            "address": "HSR Layout, Bengaluru 560102",
            "is_default": True,
        }])

    def test_readiness_accepts_live_schema_with_alternative_location_inputs(self):
        client = FakeInstamartClient(live_optional_address_schema=True)
        result = asyncio.run(self.adapter(client).readiness())
        self.assertEqual(result["state"], "ready")
        self.assertTrue(result["capability_version"])

    def test_egg_request_uses_one_twelve_piece_pack_not_twelve_packs(self):
        native = [{"id": 180, "name": "Eggs", "amount": 12, "unit": "piece"}]
        result = self.adapter().confirmed_agent_result(native, "home-1", self.capture())
        match = result["items"][0]
        self.assertEqual(match["cart_item"]["quantity"], 1)
        self.assertEqual(match["matching"]["fulfilled_quantity"], 12)
        self.assertEqual(match["matching"]["excess_quantity"], 0)
        self.assertEqual(match["cart_item"]["price_minor"], 9200)
        self.assertEqual(match["cart_item"]["line_total_minor"], 9200)
        self.assertEqual(result["cart_summary"]["total_minor"], 9200)

    def test_confirmed_cart_accepts_selected_ids_from_agent_alternatives(self):
        native = [{"id": 180, "name": "Eggs", "amount": 12, "unit": "piece"}]
        capture = self.capture()
        report = capture.structured_result["matches"][0]
        spin_id = report.pop("spin_id")
        sku_id = report.pop("sku_id")
        report["alternatives_considered"] = [{
            "spin_id": spin_id,
            "sku_id": sku_id,
            "product_name": report["product_name"],
            "pack": report["pack"],
        }]

        result = self.adapter().confirmed_agent_result(native, "home-1", capture)

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["cart_item"]["quantity"], 1)
        self.assertEqual(result["unavailable_items"], [])

    def test_agent_partial_cart_is_valid_and_unresolved_item_is_disclosed(self):
        native = [
            {"id": 180, "name": "Eggs", "amount": 12, "unit": "piece"},
            {"id": 181, "name": "Rare herb", "amount": 1, "unit": "pack"},
        ]
        unresolved = [{
            "native_item_id": "181",
            "name": "Rare herb",
            "reason": "No acceptable orderable product was returned after three searches.",
        }]
        result = self.adapter().confirmed_agent_result(
            native,
            "home-1",
            self.capture(unresolved=unresolved),
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["unavailable_items"][0]["name"], "Rare herb")

    def test_revalidation_rebuilds_reviewed_cart_without_reselecting_products(self):
        native = [{"id": 180, "name": "Eggs", "amount": 12, "unit": "piece"}]
        previous = self.adapter().confirmed_agent_result(
            native,
            "home-1",
            self.capture(),
        )
        draft = {
            **previous,
            "selected_address_id": "home-1",
            "matched_items": previous["items"],
        }
        client = FakeInstamartClient(cart_payload={
            "success": True,
            "data": {
                "items": [{
                    "spinId": "eggs-spin-12",
                    "skuId": "eggs-sku-12",
                    "itemName": "Farm Fresh Eggs - 12 pieces",
                    "quantity": 1,
                    "discountedFinalPrice": 95,
                    "itemVariant": "12 pieces",
                }],
                "toPay": "₹95.00",
            },
        })

        with commerce_request_context(
            source="test_revalidation",
            permissions={CommercePermission.READ, CommercePermission.CART_WRITE},
            operation_id="revalidate-1",
        ):
            result = asyncio.run(self.adapter(client).revalidate_cart(draft))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["items"][0]["cart_item"]["price_minor"], 9500)
        self.assertEqual(result["items"][0]["native_item"]["name"], "Eggs")
        self.assertEqual(
            [name for name, _arguments in client.calls],
            ["update_cart", "get_cart", "get_payment_options"],
        )
        self.assertEqual(client.calls[0][1], {
            "selectedAddressId": "home-1",
            "items": [{
                "spinId": "eggs-spin-12",
                "skuId": "eggs-sku-12",
                "quantity": 1,
            }],
        })

    def test_revalidation_marks_a_removed_reviewed_line_unavailable(self):
        native = [{"id": 180, "name": "Eggs", "amount": 12, "unit": "piece"}]
        previous = self.adapter().confirmed_agent_result(
            native,
            "home-1",
            self.capture(),
        )
        draft = {
            **previous,
            "selected_address_id": "home-1",
            "matched_items": previous["items"],
        }
        client = FakeInstamartClient(cart_payload={
            "success": True,
            "data": {"items": [], "toPay": "₹0.00"},
        })

        with commerce_request_context(
            source="test_revalidation",
            permissions={CommercePermission.READ, CommercePermission.CART_WRITE},
            operation_id="revalidate-2",
        ):
            result = asyncio.run(self.adapter(client).revalidate_cart(draft))

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["changed"])
        self.assertEqual(result["items"], [])
        self.assertEqual(result["unavailable_items"][0]["name"], "Eggs")
        self.assertEqual(result["changes"][0]["type"], "provider_item_removed")

    def test_report_cannot_claim_item_absent_from_confirmed_cart(self):
        native = [{"id": 180, "name": "Eggs", "amount": 12, "unit": "piece"}]
        capture = self.capture()
        capture.tool_results["get_cart"][-1]["data"]["items"] = []
        result = self.adapter().confirmed_agent_result(native, "home-1", capture)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["items"], [])
        self.assertIn("absent from the confirmed cart", result["unavailable_items"][0]["reason"])
        self.assertEqual(len(result["unavailable_items"]), 1)
        self.assertEqual(result["unavailable_items"][0]["native_item_id"], "180")

    def test_failed_update_result_cannot_be_reconstructed_as_success(self):
        native = [{"id": 180, "name": "Eggs", "amount": 12, "unit": "piece"}]
        capture = self.capture()
        capture.tool_results["update_cart"][-1] = {"error": "provider rejected cart"}
        with self.assertRaises(ProviderOperationError):
            self.adapter().confirmed_agent_result(native, "home-1", capture)

    def test_payment_options_use_friendly_labels_without_changing_provider_values(self):
        options = self.adapter()._payment_options({
            "availablePaymentMethods": [
                "gpay://upi/",
                "phonepe://",
                "PayWithQR",
            ]
        })

        self.assertEqual(
            [(option["label"], option["provider_value"]) for option in options],
            [
                ("Google Pay", "gpay://upi/"),
                ("PhonePe", "phonepe://"),
                ("Scan QR with any UPI app", "PayWithQR"),
            ],
        )

    def test_checkout_requires_ui_authority(self):
        adapter = self.adapter(FakeInstamartClient())
        review = {
            "selected_address_id": "home-1",
            "selected_payment_method_id": "Cash",
            "payment_options": [{"id": "Cash", "kind": "cod", "provider_value": "Cash"}],
        }
        without_authority = asyncio.run(adapter.place_order(review))
        self.assertEqual(without_authority["status"], "unknown")
        with commerce_request_context(
            source="ui_place_order",
            permissions={CommercePermission.READ, CommercePermission.CHECKOUT},
            operation_id="test-order",
        ):
            result = asyncio.run(adapter.place_order(review))
        self.assertEqual(result["status"], "success")

    def test_checkout_preserves_exact_provider_message_and_each_store_result(self):
        client = FakeInstamartClient(checkout_payload={
            "success": True,
            "message": "Your Instamart orders were placed. Track both deliveries separately.",
            "data": {
                "orders": [
                    {"orderId": "order-1", "status": "PLACED", "message": "Store one confirmed"},
                    {"status": "FAILED", "error": "Store two became unavailable"},
                ]
            },
        })
        review = {
            "selected_address_id": "home-1",
            "selected_payment_method_id": "Cash",
            "payment_options": [{"id": "Cash", "kind": "cod", "provider_value": "Cash"}],
        }
        with commerce_request_context(
            source="ui_place_order",
            permissions={CommercePermission.READ, CommercePermission.CHECKOUT},
            operation_id="test-multi-store-order",
        ):
            result = asyncio.run(self.adapter(client).place_order(review))

        self.assertEqual(
            result["message"],
            "Your Instamart orders were placed. Track both deliveries separately.",
        )
        self.assertEqual(len(result["order_results"]), 2)
        self.assertEqual(result["order_results"][1]["status"], "FAILED")
        self.assertEqual(result["order_results"][1]["message"], "Store two became unavailable")

    def test_price_parser_rejects_display_text_with_multiple_amounts(self):
        adapter = self.adapter()
        self.assertEqual(adapter._minor("₹70"), 7000)
        self.assertEqual(adapter._minor({"amount": "70.00"}), 7000)
        self.assertIsNone(adapter._minor("₹70 MRP ₹175"))

    def test_recorded_fixture_covers_pack_preference_and_containment_cases(self):
        fixture_path = ROOT / "test" / "fixtures" / "instamart_agent_catalog.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        cases = {case["name"]: case for case in fixture["cases"]}
        egg_packs = {
            candidate["pack"]
            for candidate in cases["eggs_semantic_pack_coverage"]["candidates"]
        }
        self.assertTrue({"12 pieces", "1 dozen", "2 x 6 pieces", "6 pieces x 2"}.issubset(egg_packs))
        self.assertEqual(cases["explicit_preference_over_history"]["expected_preference_source"], "explicit")
        self.assertEqual(cases["historical_preference_without_explicit_memory"]["expected_preference_source"], "history")
        self.assertFalse(cases["unavailable_partial_cart_and_untrusted_text"]["expected"]["checkout_allowed_to_agent"])


if __name__ == "__main__":
    unittest.main()
