"""Regression tests for address-first Zepto store-context initialization."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / "backend" / ".env")

from app.main import _review_hash  # noqa: E402
from app.providers.zepto import ZeptoProviderAdapter  # noqa: E402


class FakeSession:
    def __init__(
        self,
        *,
        selection_error: str | None = None,
        cart_payload: dict | None = None,
    ):
        self.selection_error = selection_error
        self.cart_payload = cart_payload
        self.calls: list[tuple[str, dict]] = []
        self.tools = [
            SimpleNamespace(
                name="list_saved_addresses",
                description="List saved addresses",
                inputSchema={"properties": {}},
            ),
            SimpleNamespace(
                name="select_saved_address",
                description="Select a saved address and establish store context",
                inputSchema={"properties": {"addressId": {"type": "string"}}},
            ),
            SimpleNamespace(
                name="get_payment_methods",
                description="List payment methods",
                inputSchema={"properties": {}},
            ),
            SimpleNamespace(
                name="get_past_order_items",
                description="List past order items",
                inputSchema={"properties": {}},
            ),
            SimpleNamespace(
                name="search_products",
                description="Search products",
                inputSchema={
                    "properties": {
                        "query": {"type": "string"},
                        "pageNumber": {"type": "integer", "default": 0},
                    }
                },
            ),
            SimpleNamespace(
                name="update_cart",
                description="Replace cart",
                inputSchema={"properties": {}},
            ),
            SimpleNamespace(
                name="view_cart",
                description="View cart",
                inputSchema={"properties": {}},
            ),
        ]

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name: str, args: dict):
        self.calls.append((name, args))

        if name == "list_saved_addresses":
            return {
                "isError": False,
                "structuredContent": {
                    "addresses": [
                        {
                            "id": "address-1",
                            "label": "home",
                            "addressLine": "Test home",
                        }
                    ]
                },
            }
        if name == "select_saved_address":
            if self.selection_error:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": self.selection_error}],
                }
            return {
                "isError": False,
                "structuredContent": {
                    "selectedAddressId": args["addressId"],
                    "storeContextReady": True,
                },
            }
        if name == "get_payment_methods":
            return {
                "isError": False,
                "structuredContent": {"paymentMethods": [{"id": "cod"}]},
            }
        if name == "get_past_order_items":
            return {"isError": False, "structuredContent": {"items": []}}
        if name == "search_products":
            return {
                "isError": False,
                "structuredContent": {
                    "products": [
                        {
                            "name": f"Matched {args['query']}",
                            "productVariantId": "variant-1",
                            "storeProductId": "store-product-1",
                        }
                    ]
                },
            }
        if name == "update_cart":
            return {"isError": False, "structuredContent": {"updated": True}}
        if name == "view_cart":
            return self.cart_payload or {
                "isError": False,
                "structuredContent": {
                    "items": [
                        {
                            "name": "Matched Milk",
                            "productVariantId": "variant-1",
                            "storeProductId": "store-product-1",
                        }
                    ]
                },
            }
        raise AssertionError(f"Unexpected tool call: {name}")


class FakeSessionContext:
    def __init__(self, session: FakeSession):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class ZeptoAddressFirstTests(unittest.TestCase):
    def make_adapter(self, session: FakeSession) -> ZeptoProviderAdapter:
        adapter = ZeptoProviderAdapter()
        adapter.enabled = True
        adapter._session = lambda: FakeSessionContext(session)
        return adapter

    def test_sync_requires_an_address_before_opening_provider_session(self):
        adapter = ZeptoProviderAdapter()
        adapter.enabled = True
        adapter._session = lambda: (_ for _ in ()).throw(
            AssertionError("Provider session must not open without an address.")
        )

        result = asyncio.run(
            adapter.sync_cart(
                [{"id": 1, "name": "Milk", "amount": 1, "unit": "pack"}],
                selected_address_id="",
            )
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "address_required")

    def test_selects_saved_address_before_search_and_cart_update(self):
        session = FakeSession()
        adapter = self.make_adapter(session)

        result = asyncio.run(
            adapter.sync_cart(
                [{"id": 1, "name": "Milk", "amount": 1, "unit": "pack"}],
                selected_address_id="address-1",
            )
        )

        call_names = [name for name, _ in session.calls]
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["store_context"]["state"], "store_context_ready")
        self.assertEqual(result["store_context"]["selected_address_id"], "address-1")
        self.assertLess(
            call_names.index("select_saved_address"),
            call_names.index("search_products"),
        )
        self.assertLess(
            call_names.index("select_saved_address"),
            call_names.index("get_payment_methods"),
        )
        self.assertIn("update_cart", call_names)
        self.assertIn("view_cart", call_names)

    def test_store_context_failure_stops_before_product_search(self):
        session = FakeSession(
            selection_error="Selected address is not serviceable."
        )
        adapter = self.make_adapter(session)

        result = asyncio.run(
            adapter.sync_cart(
                [{"id": 1, "name": "Milk", "amount": 1, "unit": "pack"}],
                selected_address_id="address-1",
            )
        )

        call_names = [name for name, _ in session.calls]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "store_context_unavailable")
        self.assertNotIn("search_products", call_names)
        self.assertNotIn("update_cart", call_names)

    def test_saved_addresses_can_be_loaded_before_sync(self):
        session = FakeSession()
        adapter = self.make_adapter(session)

        result = asyncio.run(adapter.list_addresses())

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["provider"], "zepto")
        self.assertEqual(
            result["addresses"]["structuredContent"]["addresses"][0]["id"],
            "address-1",
        )

    def test_normalizes_complete_cart_summary_from_provider_payload(self):
        session = FakeSession(
            cart_payload={
                "isError": False,
                "structuredContent": {
                    "cart": {
                        "subtotal": 42900,
                        "discountAmount": 2500,
                        "deliveryFee": 1900,
                        "handlingFee": 900,
                        "grandTotal": 45300,
                        "currency": "INR",
                    }
                },
            }
        )
        adapter = self.make_adapter(session)

        result = asyncio.run(
            adapter.sync_cart(
                [{"id": 1, "name": "Milk", "amount": 1, "unit": "pack"}],
                selected_address_id="address-1",
            )
        )

        self.assertEqual(
            result["cart_summary"],
            {
                "currency": "INR",
                "subtotal_minor": 42900,
                "discount_minor": 2500,
                "fees": [
                    {"label": "Delivery fee", "amount_minor": 1900},
                    {"label": "Handling fee", "amount_minor": 900},
                ],
                "total_minor": 45300,
            },
        )

    def test_cart_summary_keeps_missing_provider_values_null(self):
        adapter = ZeptoProviderAdapter()

        summary = adapter.normalize_cart_summary(
            {
                "structuredContent": {
                    "cart": {
                        "subtotal": "₹429.50",
                        "fees": [{"label": "Rain fee", "amount": "₹12"}],
                    }
                }
            }
        )

        self.assertEqual(summary["subtotal_minor"], 42950)
        self.assertEqual(summary["fees"], [{"label": "Rain fee", "amount_minor": 1200}])
        self.assertIsNone(summary["discount_minor"])
        self.assertIsNone(summary["total_minor"])

    def test_malformed_cart_summary_does_not_invent_totals(self):
        adapter = ZeptoProviderAdapter()

        summary = adapter.normalize_cart_summary(
            {
                "structuredContent": {
                    "items": [{"name": "Milk", "price": 9900}],
                    "total": "not available",
                }
            }
        )

        self.assertEqual(
            summary,
            {
                "currency": "INR",
                "subtotal_minor": None,
                "discount_minor": None,
                "fees": [],
                "total_minor": None,
            },
        )

    def test_review_hash_covers_the_provider_cart_summary(self):
        review = {
            "native_items": [{"id": 1, "name": "Milk"}],
            "matched_items": [{"native_item": {"id": 1}}],
            "selected_address_id": "address-1",
            "cart_summary": {
                "currency": "INR",
                "subtotal_minor": 9900,
                "discount_minor": None,
                "fees": [],
                "total_minor": 9900,
            },
        }

        original_hash = _review_hash(review)
        changed_review = {
            **review,
            "cart_summary": {
                **review["cart_summary"],
                "total_minor": 10900,
            },
        }

        self.assertNotEqual(original_hash, _review_hash(changed_review))


if __name__ == "__main__":
    unittest.main()
