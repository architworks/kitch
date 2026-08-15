"""Contract tests for the Swiggy Instamart adapter."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.providers.catalog_matcher import ProviderCatalogMatcher  # noqa: E402
from app.providers.instamart import InstamartProviderAdapter  # noqa: E402


class FakeContext:
    def __init__(self, session):
        self.session_value = session

    async def __aenter__(self):
        return self.session_value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeInstamartClient:
    def __init__(self, *, cart_items=None, available=True, tools=None, checkout_error=False):
        self.calls = []
        self.cart_items = cart_items
        self.available = available
        self.checkout_error = checkout_error
        names = tools or {
            "get_addresses", "search_products", "update_cart", "get_cart",
            "get_payment_options", "checkout", "get_orders", "track_order",
            "check_payment_status",
        }
        schemas = {
            "get_addresses": {},
            "search_products": {
                "addressId": {"type": "string"}, "query": {"type": "string"},
            },
            "update_cart": {
                "selectedAddressId": {"type": "string"}, "items": {"type": "array"},
            },
            "get_cart": {},
            "get_payment_options": {},
            "checkout": {"addressId": {"type": "string"}},
            "get_orders": {},
            "track_order": {"orderId": {"type": "string"}},
            "check_payment_status": {"paasId": {"type": "string"}},
        }
        self.tools = {
            name: SimpleNamespace(
                name=name,
                inputSchema={
                    "type": "object",
                    "properties": schemas.get(name, {}),
                    "required": list(schemas.get(name, {})),
                },
            )
            for name in names
        }

    def session(self):
        return FakeContext(object())

    async def list_tools(self, session):
        return self.tools

    async def call_tool(self, session, name, arguments=None):
        arguments = arguments or {}
        self.calls.append((name, arguments))
        if name == "get_addresses":
            return {"success": True, "data": {"addresses": [{"id": "home-1", "label": "Home", "address": "Bengaluru"}]}}
        if name == "search_products":
            variation = {
                "spinId": "spin-1",
                "skuId": "sku-1",
                "name": "Milk",
                "packSize": "1 L",
                "sellingPrice": 99,
                "available": self.available,
                "availableQuantity": 4 if self.available else 0,
                "imageUrl": "https://example.test/milk.png",
            }
            return {"success": True, "data": {"products": [{"name": "Milk", "variations": [variation]}]}}
        if name == "update_cart":
            return {"success": True, "data": {"updated": True}}
        if name == "get_cart":
            items = self.cart_items
            if items is None:
                items = [{
                    "spinId": "spin-1",
                    "skuId": "sku-1",
                    "name": "Milk",
                    "quantity": 1,
                    "sellingPrice": 99,
                    "packSize": "1 L",
                }]
            return {
                "success": True,
                "data": {
                    "items": items,
                    "itemTotal": 99,
                    "grandTotal": 104,
                    "fees": [{"label": "Delivery fee", "amount": 5}],
                    "availablePaymentMethods": ["UPI", "COD"],
                },
            }
        if name == "get_payment_options":
            return {
                "success": True,
                "data": {
                    "platforms": {
                        "mobile": {"methods": [{"id": "com.google.android.apps.nbu.paisa.user", "label": "Google Pay"}]},
                        "desktop": {"methods": [{"id": "PayWithQR", "label": "Scan QR to pay"}]},
                    },
                    "cod": {"paymentMethod": "Cash", "label": "Cash on Delivery"},
                },
            }
        if name == "checkout":
            if self.checkout_error:
                raise TimeoutError("ambiguous provider timeout")
            return {"success": True, "data": {"orderId": "im-order-1", "status": "PLACED"}}
        if name == "check_payment_status":
            return {
                "success": True,
                "data": {
                    "paasId": arguments["paasId"],
                    "status": "success",
                    "terminal": True,
                    "isTerminalSuccess": True,
                    "confirmed": True,
                },
            }
        if name == "get_orders":
            return {"success": True, "data": {"orders": [{"orderId": "im-order-possible", "status": "PLACED"}]}}
        raise AssertionError(f"Unexpected tool call: {name}")

    @staticmethod
    def input_schema(tool):
        return tool.inputSchema


class FakeOAuth:
    environment = "staging"

    def connection_status(self):
        return {"state": "connected", "message": "Connected"}

    def production_gate_error(self):
        return None


class InstamartProviderTests(unittest.TestCase):
    def adapter(self, client):
        adapter = InstamartProviderAdapter(
            oauth=FakeOAuth(),
            matcher=ProviderCatalogMatcher(llm_enabled=False),
            client=client,
        )
        adapter.enabled = True
        return adapter

    def item(self):
        return {"id": 1, "name": "Milk", "amount": 1, "unit": "L"}

    def test_sync_is_address_scoped_replaces_cart_and_confirms_result(self):
        client = FakeInstamartClient()
        result = asyncio.run(self.adapter(client).sync_cart([self.item()], "home-1"))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["provider"], "swiggy_instamart")
        self.assertEqual(result["cart_summary"]["total_minor"], 10400)
        self.assertEqual(
            [option["id"] for option in result["payment_options"]],
            ["com.google.android.apps.nbu.paisa.user", "PayWithQR"],
        )
        search_call = next(args for name, args in client.calls if name == "search_products")
        update_call = next(args for name, args in client.calls if name == "update_cart")
        self.assertEqual(search_call["addressId"], "home-1")
        self.assertEqual(update_call["selectedAddressId"], "home-1")
        self.assertEqual(update_call["items"], [{"spinId": "spin-1", "skuId": "sku-1", "quantity": 1}])
        self.assertLess(
            [name for name, _ in client.calls].index("update_cart"),
            [name for name, _ in client.calls].index("get_cart"),
        )

    def test_search_result_absent_from_confirmed_cart_is_not_success(self):
        client = FakeInstamartClient(cart_items=[])
        result = asyncio.run(self.adapter(client).sync_cart([self.item()], "home-1"))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["items"], [])
        self.assertEqual(len(result["unavailable_items"]), 1)

    def test_missing_availability_is_unverified_and_cart_is_not_mutated(self):
        client = FakeInstamartClient(available=False)
        result = asyncio.run(self.adapter(client).sync_cart([self.item()], "home-1"))
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn("update_cart", [name for name, _ in client.calls])

    def test_boolean_availability_without_stock_quantity_is_unverified(self):
        adapter = self.adapter(FakeInstamartClient())
        candidates = adapter._product_candidates({
            "products": [{
                "name": "Milk",
                "variations": [{
                    "spinId": "spin-1",
                    "skuId": "sku-1",
                    "available": True,
                    "packSize": "1 L",
                }],
            }],
        }, self.item())
        self.assertTrue(candidates[0]["available"])
        self.assertEqual(candidates[0]["available_quantity"], 0)

    def test_pack_quantity_is_converted_before_stock_validation(self):
        adapter = self.adapter(FakeInstamartClient())
        self.assertEqual(
            adapter._requested_pack_quantity(
                {"amount": 1500, "unit": "mL"},
                "1 L",
            ),
            2,
        )
        self.assertIsNone(
            adapter._requested_pack_quantity(
                {"amount": 1, "unit": "kg"},
                "1 L",
            )
        )

    def test_matcher_rejects_dietary_conflicts_and_invented_ids(self):
        matcher = ProviderCatalogMatcher(llm_enabled=False)
        dairy = {
            "candidate_id": "spin-1:sku-1",
            "name": "Full Cream Dairy Milk",
            "available": True,
            "available_quantity": 2,
            "requested_quantity": 1,
        }
        decision = asyncio.run(matcher.choose(
            {"name": "Milk"},
            [dairy],
            ["Vegan household"],
        ))
        self.assertIsNone(decision)

    def test_required_tool_schema_drift_fails_closed(self):
        client = FakeInstamartClient(tools={"get_addresses", "search_products", "get_cart"})
        result = asyncio.run(self.adapter(client).sync_cart([self.item()], "home-1"))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "provider_contract_incompatible")

    def test_cod_is_used_only_when_upi_is_absent(self):
        adapter = self.adapter(FakeInstamartClient())
        options = adapter._payment_options({"availablePaymentMethods": ["COD"]})
        self.assertEqual(options[0]["kind"], "cod")

    def test_incompatible_required_input_schema_fails_closed(self):
        client = FakeInstamartClient()
        client.tools["update_cart"].inputSchema = {
            "type": "object",
            "properties": {"items": {"type": "array"}},
            "required": ["items"],
        }
        result = asyncio.run(self.adapter(client).sync_cart([self.item()], "home-1"))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "provider_contract_incompatible")

    def test_upi_checkout_passes_opaque_intent_id_in_the_documented_field(self):
        client = FakeInstamartClient()
        adapter = self.adapter(client)
        review = {
            "selected_address_id": "home-1",
            "selected_payment_method_id": "com.google.android.apps.nbu.paisa.user",
            "payment_options": [{
                "id": "com.google.android.apps.nbu.paisa.user",
                "kind": "upi",
                "provider_value": "com.google.android.apps.nbu.paisa.user",
                "flow": "upi_intent",
            }],
        }
        result = asyncio.run(adapter.place_order(review))
        checkout_args = next(args for name, args in client.calls if name == "checkout")
        self.assertEqual(result["status"], "success")
        self.assertEqual(checkout_args["paymentMethod"], "UPI")
        self.assertEqual(checkout_args["intentApp"], "com.google.android.apps.nbu.paisa.user")

    def test_payment_status_uses_persisted_paas_and_order_references(self):
        client = FakeInstamartClient()
        adapter = self.adapter(client)
        result = asyncio.run(adapter.payment_status({
            "provider_order_ids": ["im-order-1"],
            "payment_state": {"paas_id": "paas-1", "order_id": "im-order-1"},
        }))
        status_args = next(args for name, args in client.calls if name == "check_payment_status")
        self.assertEqual(status_args, {"paasId": "paas-1", "orderId": "im-order-1"})
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["payment_state"]["confirmed"])

    def test_ambiguous_checkout_reads_order_history_and_blocks_retry(self):
        client = FakeInstamartClient(checkout_error=True)
        adapter = self.adapter(client)
        review = {
            "selected_address_id": "home-1",
            "selected_payment_method_id": "UPI",
            "payment_options": [{"id": "UPI", "kind": "upi", "provider_value": "UPI"}],
        }
        result = asyncio.run(adapter.place_order(review))
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(result["ambiguous_order"])
        self.assertEqual(result["order_results"][0]["order_id"], "im-order-possible")
        self.assertEqual([name for name, _ in client.calls].count("checkout"), 1)


if __name__ == "__main__":
    unittest.main()
