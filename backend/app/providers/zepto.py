"""Zepto MCP provider adapter.

This module keeps Zepto-specific MCP behavior outside Kitch's native cart
model. The adapter is intentionally defensive because Zepto OAuth/tool schemas
are controlled by the remote MCP server.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import timedelta
from typing import Any, Dict, List


class ZeptoProviderAdapter:
    """Best-effort MCP adapter for Zepto cart and order operations."""

    def __init__(self) -> None:
        self.url = os.environ.get("ZEPTO_MCP_URL", "https://mcp.zepto.co.in/mcp")
        self.access_token = (
            os.environ.get("ZEPTO_MCP_ACCESS_TOKEN")
            or os.environ.get("ZEPTO_MCP_BEARER_TOKEN")
            or os.environ.get("ZEPTO_ACCESS_TOKEN")
        )
        self.enabled = os.environ.get("ZEPTO_MCP_ENABLED", "true").lower() not in {"0", "false", "no"}
        self.raw_headers = os.environ.get("ZEPTO_MCP_HEADERS")
        explicit_transport = os.environ.get("ZEPTO_MCP_TRANSPORT", "").strip().lower()
        self.transport = explicit_transport or ("http" if self.access_token or self.raw_headers else "stdio_remote")
        self.remote_command = os.environ.get("ZEPTO_MCP_REMOTE_COMMAND", "npx")
        self.remote_args = self._remote_args()

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        if self.raw_headers:
            try:
                headers.update(json.loads(self.raw_headers))
            except json.JSONDecodeError:
                pass

        return headers

    def _remote_args(self) -> List[str]:
        raw_args = os.environ.get("ZEPTO_MCP_REMOTE_ARGS")
        if not raw_args:
            return ["-y", "mcp-remote", self.url]
        try:
            parsed = json.loads(raw_args)
            if isinstance(parsed, list) and all(isinstance(arg, str) for arg in parsed):
                return parsed
        except json.JSONDecodeError:
            pass
        return shlex.split(raw_args)

    def status(self) -> Dict[str, Any]:
        if not self.enabled:
            state = "disabled"
            message = "Zepto MCP integration is disabled."
        elif self.transport in {"stdio", "stdio_remote", "mcp_remote"} and not self.access_token:
            state = "configured"
            message = "Zepto MCP is configured through the local browser OAuth bridge."
        elif self.access_token or self.raw_headers:
            state = "configured"
            message = "Zepto MCP credentials are configured."
        else:
            state = "not_connected"
            message = "No Zepto MCP auth token or remote OAuth bridge is configured."

        return {
            "provider": "zepto",
            "enabled": self.enabled,
            "state": state,
            "message": message,
            "endpoint": self.url,
            "transport": self.transport,
            "auth_mode": "bearer_or_headers" if self.access_token or self.raw_headers else "browser_oauth",
            "readiness": "configured_only" if state == "configured" else state,
            "store_context_state": "not_selected",
            "setup_command": f"{self.remote_command} {' '.join(self.remote_args)}" if self.transport in {"stdio", "stdio_remote", "mcp_remote"} else None,
        }

    async def list_addresses(self) -> Dict[str, Any]:
        """Return saved Zepto delivery addresses without selecting one."""
        if not self.enabled:
            return self._error("disabled", "Zepto MCP integration is disabled.")

        try:
            async with self._session() as session:
                tools = await self._list_tools(session)
                address_tool = "list_saved_addresses" if "list_saved_addresses" in tools else self._find_tool(
                    tools,
                    required=("address",),
                    preferred=("get", "list", "show", "view"),
                )
                if not address_tool:
                    return self._error(
                        "missing_address_tool",
                        "Zepto did not expose a saved-address lookup tool.",
                        available_tools=list(tools.keys()),
                    )

                addresses = await self._call_tool(
                    session,
                    address_tool,
                    self._build_empty_or_default_args(tools[address_tool]),
                )
                tool_error = self._tool_error_message(addresses)
                if tool_error:
                    return self._error(
                        "address_lookup_failed",
                        f"Zepto saved addresses could not be read: {tool_error}",
                    )

                return {
                    "status": "success",
                    "provider": "zepto",
                    "addresses": addresses,
                    "message": "Zepto saved addresses are available. Select one before syncing the cart.",
                }
        except Exception as exc:
            return self._error(
                "address_lookup_failed",
                f"Zepto saved addresses could not be read: {exc}",
            )

    async def sync_cart(
        self,
        items: List[Dict[str, Any]],
        selected_address_id: str = "",
    ) -> Dict[str, Any]:
        """Replace the Zepto cart with best matches for native cart items."""
        if not self.enabled:
            return self._error("disabled", "Zepto MCP integration is disabled.")

        selected_address_id = str(selected_address_id or "").strip()
        if not selected_address_id:
            return self._error(
                "address_required",
                "Select a Zepto delivery address before moving items to the cart.",
            )

        if not items:
            return {
                "status": "empty",
                "message": "No unchecked, non-stocked native cart items are available for Zepto sync.",
                "items": [],
                "unavailable_items": [],
            }

        try:
            return await self._sync_cart(items, selected_address_id)
        except Exception as exc:
            return self._error(
                "mcp_sync_failed",
                f"Zepto MCP cart sync failed: {exc}",
            )

    async def _sync_cart(
        self,
        items: List[Dict[str, Any]],
        selected_address_id: str,
    ) -> Dict[str, Any]:
        async with self._session() as session:
            tools = await self._list_tools(session)
            store_context = await self._select_store_context(
                session,
                tools,
                selected_address_id,
            )
            if store_context.get("status") != "ready":
                return {
                    **store_context,
                    "available_tools": list(tools.keys()),
                }

            if {"search_products", "update_cart", "view_cart"}.issubset(tools):
                return await self._sync_cart_with_zepto_tools(
                    session,
                    tools,
                    items,
                    store_context,
                )

            clear_tool = self._find_tool(tools, required=("cart",), preferred=("clear", "empty", "replace"))
            search_tool = self._find_tool(tools, required=(), preferred=("search", "product", "catalog"))
            add_tool = self._find_tool(tools, required=("cart",), preferred=("add",))
            get_cart_tool = self._find_tool(tools, required=("cart",), preferred=("get", "view", "show", "list"))
            checkout_context = await self._checkout_context(session, tools)

            if not clear_tool:
                return self._error(
                    "missing_clear_cart_tool",
                    "Could not find a Zepto MCP tool that can clear or replace the existing cart.",
                    available_tools=list(tools.keys()),
                )
            if not search_tool or not add_tool:
                return self._error(
                    "missing_cart_tools",
                    "Could not find Zepto MCP search/add cart tools.",
                    available_tools=list(tools.keys()),
                )

            await self._call_tool(session, clear_tool, {})

            matched_items = []
            unavailable_items = []
            for item in items:
                search_term = str(item.get("search_name") or item.get("name") or "").strip()
                if not search_term:
                    continue

                search_args = self._build_search_args(tools[search_tool], search_term)
                search_result = await self._call_tool(session, search_tool, search_args)
                product = self._first_product(search_result)

                if not product:
                    unavailable_items.append({"name": item.get("name"), "reason": "No available Zepto product was returned."})
                    continue

                add_args = self._build_add_args(tools[add_tool], product, item)
                if not add_args:
                    unavailable_items.append({
                        "name": item.get("name"),
                        "reason": "Zepto found a product, but Kitch could not infer the add-to-cart details.",
                        "matched_product": product,
                    })
                    continue

                add_result = await self._call_tool(session, add_tool, add_args)
                matched_items.append({
                    "native_item": item,
                    "matched_product": product,
                    "cart_item": {
                        "price": product.get("price"),
                        "quantity": next(
                            (
                                add_args[key]
                                for key in ("quantity", "qty", "count", "amount")
                                if add_args.get(key) is not None
                            ),
                            None,
                        ),
                    },
                    "add_result": add_result,
                })

            zepto_cart = None
            if get_cart_tool:
                zepto_cart = await self._call_tool(session, get_cart_tool, self._build_empty_or_default_args(tools[get_cart_tool]))

            return {
                "status": "success",
                "provider": "zepto",
                "items": matched_items,
                "unavailable_items": unavailable_items,
                "zepto_cart": zepto_cart,
                "cart_summary": self.normalize_cart_summary(zepto_cart, matched_items),
                "checkout_context": checkout_context,
                "store_context": store_context,
                "available_tools": list(tools.keys()),
                "message": f"Synced {len(matched_items)} items to Zepto cart.",
            }

    async def _sync_cart_with_zepto_tools(
        self,
        session: Any,
        tools: Dict[str, Any],
        items: List[Dict[str, Any]],
        store_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        checkout_context = await self._checkout_context(session, tools)
        matched_items = []
        unavailable_items = []
        cart_items = []

        if "get_past_order_items" in tools:
            try:
                await self._call_tool(session, "get_past_order_items", {})
            except Exception:
                pass

        for item in items:
            search_term = str(item.get("search_name") or item.get("name") or "").strip()
            if not search_term:
                continue

            try:
                search_result = await self._call_tool(session, "search_products", {"query": search_term, "pageNumber": 0})
            except Exception as exc:
                unavailable_items.append({"name": item.get("name"), "reason": f"Zepto search failed: {exc}"})
                continue

            product = self._first_product(search_result)
            if not product:
                unavailable_items.append({"name": item.get("name"), "reason": "No available Zepto product was returned."})
                continue

            cart_item = self._build_zepto_cart_item(product, item)
            if not cart_item:
                unavailable_items.append({
                    "name": item.get("name"),
                    "reason": "Zepto found a product, but cart identifiers were missing.",
                    "matched_product": product,
                })
                continue

            cart_items.append(cart_item)
            matched_items.append({
                "native_item": item,
                "matched_product": product,
                "cart_item": cart_item,
            })

        zepto_cart = None
        if cart_items:
            update_result = await self._call_tool(
                session,
                "update_cart",
                {
                    "deviceId": "kitch-native-cart",
                    "replaceCart": True,
                    "cartItems": cart_items,
                },
            )
            for index, match in enumerate(matched_items):
                match["add_result"] = update_result if index == 0 else {"status": "batched_update"}
            zepto_cart = await self._call_tool(session, "view_cart", {})

        return {
            "status": "success" if matched_items else "error",
            "provider": "zepto",
            "items": matched_items,
            "unavailable_items": unavailable_items,
            "zepto_cart": zepto_cart,
            "cart_summary": self.normalize_cart_summary(zepto_cart, matched_items),
            "checkout_context": checkout_context,
            "store_context": store_context,
            "available_tools": list(tools.keys()),
            "message": f"Synced {len(matched_items)} items to Zepto cart." if matched_items else "No Zepto products could be added to the cart.",
        }

    async def get_cart(self) -> Dict[str, Any]:
        """Fetch the current Zepto cart through MCP."""
        try:
            async with self._session() as session:
                tools = await self._list_tools(session)
                get_cart_tool = self._find_tool(tools, required=("cart",), preferred=("get", "view", "show", "list"))
                if not get_cart_tool:
                    return self._error("missing_get_cart_tool", "Could not find a Zepto MCP tool to fetch the cart.", available_tools=list(tools.keys()))
                cart = await self._call_tool(session, get_cart_tool, self._build_empty_or_default_args(tools[get_cart_tool]))
                return {
                    "status": "success",
                    "provider": "zepto",
                    "zepto_cart": cart,
                    "cart_summary": self.normalize_cart_summary(cart),
                }
        except Exception as exc:
            return self._error("mcp_get_cart_failed", f"Zepto MCP cart read failed: {exc}")

    async def place_order(self, review: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Place the currently reviewed Zepto cart order through MCP."""
        try:
            async with self._session() as session:
                tools = await self._list_tools(session)
                if review:
                    await self._apply_checkout_selection(session, tools, review)
                order_tool = self._find_tool(tools, required=("order",), preferred=("place", "checkout", "create"))
                if not order_tool:
                    return self._error("missing_place_order_tool", "Could not find a Zepto MCP tool to place an order.", available_tools=list(tools.keys()))
                result = await self._call_tool(session, order_tool, self._build_order_args(tools[order_tool], review or {}))
                return {"status": "success", "provider": "zepto", "order_result": result}
        except Exception as exc:
            return self._error("mcp_order_failed", f"Zepto MCP order placement failed: {exc}")

    def _error(self, code: str, message: str, **extra: Any) -> Dict[str, Any]:
        return {"status": "error", "provider": "zepto", "code": code, "message": message, **extra}

    def normalize_cart_summary(
        self,
        payload: Any,
        matched_items: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Prefer Zepto totals, with a guarded exact line-item fallback."""
        summary: Dict[str, Any] = {
            "currency": "INR",
            "subtotal_minor": None,
            "discount_minor": None,
            "fees": [],
            "total_minor": None,
            "total_source": "unavailable",
            "total_notice": "Zepto did not return a final cart total.",
        }
        objects: List[Dict[str, Any]] = []
        self._collect_payload_objects(payload, objects)

        summary["currency"] = self._first_text_value(
            objects,
            ("currency", "currency_code", "currencyCode"),
        ) or "INR"
        summary["subtotal_minor"] = self._first_minor_value(
            objects,
            (
                "subtotal_minor",
                "subtotal",
                "sub_total",
                "cart_subtotal",
                "cartSubtotal",
                "item_total",
                "itemTotal",
                "items_total",
                "itemsTotal",
            ),
        )
        summary["discount_minor"] = self._first_minor_value(
            objects,
            (
                "discount_minor",
                "discount",
                "discount_amount",
                "discountAmount",
                "total_discount",
                "totalDiscount",
                "savings",
            ),
        )
        if summary["discount_minor"] is not None:
            summary["discount_minor"] = abs(summary["discount_minor"])
        summary["total_minor"] = self._first_minor_value(
            objects,
            (
                "total_minor",
                "grand_total",
                "grandTotal",
                "total_amount",
                "totalAmount",
                "payable_amount",
                "payableAmount",
                "amount_payable",
                "amountPayable",
                "final_total",
                "finalTotal",
                "cart_total",
                "cartTotal",
            ),
        )

        fee_aliases = (
            ("Delivery fee", ("delivery_fee", "deliveryFee", "delivery_charge", "deliveryCharge")),
            ("Handling fee", ("handling_fee", "handlingFee", "handling_charge", "handlingCharge")),
            ("Platform fee", ("platform_fee", "platformFee")),
            ("Small cart fee", ("small_cart_fee", "smallCartFee")),
            ("Surge fee", ("surge_fee", "surgeFee", "surge_charge", "surgeCharge")),
        )
        fees: List[Dict[str, Any]] = []
        for label, aliases in fee_aliases:
            amount_minor = self._first_minor_value(objects, aliases)
            if amount_minor is not None:
                fees.append({"label": label, "amount_minor": amount_minor})

        if not fees:
            fees = self._first_fee_list(objects)
        summary["fees"] = fees

        if summary["total_minor"] is not None:
            summary["total_source"] = "provider"
            summary["total_notice"] = "Final total returned by Zepto."
            return summary

        has_adjustments = bool(fees) or bool(summary["discount_minor"]) or self._has_additional_adjustments(objects)
        if has_adjustments:
            summary["total_notice"] = (
                "Zepto returned an additional charge or discount without a final total, "
                "so Kitch did not calculate one."
            )
            return summary

        line_total = self._sum_matched_line_items(matched_items or [])
        if line_total is None:
            line_total = self._first_payload_line_total(objects)
        if line_total is not None:
            if summary["subtotal_minor"] is None:
                summary["subtotal_minor"] = line_total
            summary["total_minor"] = line_total
            summary["total_source"] = "line_items"
            summary["total_notice"] = (
                "Calculated from Zepto-returned selling prices and cart quantities; "
                "the response contained no additional charges."
            )
        return summary

    def _has_additional_adjustments(self, objects: List[Dict[str, Any]]) -> bool:
        adjustment_keys = {
            "tax",
            "taxes",
            "taxbreakdown",
            "gst",
            "cess",
            "tip",
            "fee",
            "fees",
            "feebreakdown",
            "charge",
            "charges",
            "chargebreakdown",
            "additionalcharges",
            "checkoutcharges",
            "othercharges",
            "deliveryfee",
            "deliverycharge",
            "handlingfee",
            "handlingcharge",
            "platformfee",
            "servicefee",
            "conveniencefee",
            "packagingfee",
            "smallcartfee",
            "surgefee",
            "surgecharge",
        }
        for item in objects:
            for key, value in item.items():
                normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if normalized_key not in adjustment_keys:
                    continue
                if isinstance(value, list):
                    if value:
                        return True
                    continue
                if isinstance(value, dict):
                    if value:
                        return True
                    continue
                amount = self._to_minor_units(value)
                if amount is None:
                    if value not in (None, "", False):
                        return True
                elif amount != 0:
                    return True
        return False

    def _first_payload_line_total(self, objects: List[Dict[str, Any]]) -> int | None:
        for item in objects:
            for key in ("items", "cart_items", "cartItems"):
                raw_items = item.get(key)
                if not isinstance(raw_items, list) or not raw_items:
                    continue
                normalized_matches = [
                    {"cart_item": raw_item}
                    for raw_item in raw_items
                    if isinstance(raw_item, dict)
                ]
                if len(normalized_matches) != len(raw_items):
                    continue
                line_total = self._sum_matched_line_items(normalized_matches)
                if line_total is not None:
                    return line_total
        return None

    def _sum_matched_line_items(self, matched_items: List[Dict[str, Any]]) -> int | None:
        if not matched_items:
            return None

        total = 0
        for match in matched_items:
            if not isinstance(match, dict):
                return None
            cart_item = match.get("cart_item")
            product = match.get("matched_product")
            cart_item = cart_item if isinstance(cart_item, dict) else {}
            product = product if isinstance(product, dict) else {}

            raw_price = None
            for source in (cart_item, product):
                for key in ("price", "sellingPrice", "selling_price", "discountedPrice"):
                    if source.get(key) is not None:
                        raw_price = source[key]
                        break
                if raw_price is not None:
                    break
            price_minor = self._to_minor_units(raw_price)
            raw_quantity = cart_item.get("quantity")
            if price_minor is None or isinstance(raw_quantity, bool):
                return None
            try:
                quantity = Decimal(str(raw_quantity))
            except (InvalidOperation, ValueError, TypeError):
                return None
            if quantity <= 0:
                return None
            total += int((Decimal(price_minor) * quantity).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        return total

    def _collect_payload_objects(self, value: Any, objects: List[Dict[str, Any]]) -> None:
        if isinstance(value, dict):
            objects.append(value)
            text = value.get("text")
            if isinstance(text, str):
                try:
                    self._collect_payload_objects(json.loads(text), objects)
                except json.JSONDecodeError:
                    pass
            for child in value.values():
                self._collect_payload_objects(child, objects)
        elif isinstance(value, list):
            for child in value:
                self._collect_payload_objects(child, objects)

    def _first_text_value(
        self,
        objects: List[Dict[str, Any]],
        keys: tuple[str, ...],
    ) -> str | None:
        for item in objects:
            for key in keys:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().upper()
        return None

    def _first_minor_value(
        self,
        objects: List[Dict[str, Any]],
        keys: tuple[str, ...],
    ) -> int | None:
        for item in objects:
            for key in keys:
                if key in item:
                    value = self._to_minor_units(item.get(key))
                    if value is not None:
                        return value
        return None

    def _first_fee_list(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for item in objects:
            raw_fees = item.get("fees") or item.get("fee_breakdown") or item.get("feeBreakdown")
            if not isinstance(raw_fees, list):
                continue

            fees: List[Dict[str, Any]] = []
            for index, fee in enumerate(raw_fees):
                if not isinstance(fee, dict):
                    continue
                label = (
                    fee.get("label")
                    or fee.get("name")
                    or fee.get("title")
                    or f"Fee {index + 1}"
                )
                amount = self._to_minor_units(
                    fee.get("amount_minor")
                    if "amount_minor" in fee
                    else fee.get("amount", fee.get("value"))
                )
                if amount is not None:
                    fees.append({"label": str(label), "amount_minor": amount})
            if fees:
                return fees
        return []

    def _to_minor_units(self, value: Any) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, dict):
            for key in ("amount_minor", "amount", "value"):
                if key in value:
                    return self._to_minor_units(value[key])
            return None
        if isinstance(value, (int, float, Decimal)):
            try:
                return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            except (InvalidOperation, ValueError):
                return None
        if not isinstance(value, str):
            return None

        text = value.strip()
        if not text:
            return None
        is_major_currency = "₹" in text or re.search(r"\b(?:INR|RS\.?)\b", text, re.IGNORECASE)
        numeric = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
        if not numeric or numeric in {"-", ".", "-."}:
            return None
        try:
            amount = Decimal(numeric)
            if is_major_currency:
                amount *= 100
            return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        except InvalidOperation:
            return None

    def _session(self):
        try:
            from mcp import ClientSession
        except ImportError as exc:
            raise RuntimeError("Python MCP client is not installed. Install the `mcp` package.") from exc

        if self.transport in {"stdio", "stdio_remote", "mcp_remote"}:
            return self._stdio_remote_session(ClientSession)

        return self._http_session(ClientSession)

    def _http_session(self, ClientSession):
        try:
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError("Python MCP streamable HTTP client is not installed.") from exc

        headers = self._headers()
        client_ctx = streamablehttp_client(
            self.url,
            headers=headers or None,
            timeout=timedelta(seconds=30),
            sse_read_timeout=timedelta(seconds=300),
        )

        class _SessionContext:
            async def __aenter__(inner_self):
                inner_self.client = client_ctx
                inner_self.read, inner_self.write, _ = await inner_self.client.__aenter__()
                inner_self.session = ClientSession(inner_self.read, inner_self.write)
                await inner_self.session.__aenter__()
                await inner_self.session.initialize()
                return inner_self.session

            async def __aexit__(inner_self, exc_type, exc, tb):
                await inner_self.session.__aexit__(exc_type, exc, tb)
                await inner_self.client.__aexit__(exc_type, exc, tb)

        return _SessionContext()

    def _stdio_remote_session(self, ClientSession):
        try:
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise RuntimeError("Python MCP stdio client is not installed.") from exc

        server_params = StdioServerParameters(command=self.remote_command, args=self.remote_args)
        client_ctx = stdio_client(server_params)

        class _SessionContext:
            async def __aenter__(inner_self):
                inner_self.client = client_ctx
                inner_self.read, inner_self.write = await inner_self.client.__aenter__()
                inner_self.session = ClientSession(inner_self.read, inner_self.write)
                await inner_self.session.__aenter__()
                await inner_self.session.initialize()
                return inner_self.session

            async def __aexit__(inner_self, exc_type, exc, tb):
                await inner_self.session.__aexit__(exc_type, exc, tb)
                await inner_self.client.__aexit__(exc_type, exc, tb)

        return _SessionContext()

    async def _list_tools(self, session: Any) -> Dict[str, Any]:
        result = await session.list_tools()
        return {tool.name: tool for tool in result.tools}

    async def _call_tool(self, session: Any, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        result = await session.call_tool(name, args or {})
        return self._to_plain(result)

    def _to_plain(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return [self._to_plain(v) for v in value]
        if isinstance(value, dict):
            return {k: self._to_plain(v) for k, v in value.items()}
        return value

    def _find_tool(self, tools: Dict[str, Any], required: tuple[str, ...], preferred: tuple[str, ...]) -> str | None:
        best_name = None
        best_score = -1
        for name, tool in tools.items():
            text = f"{name} {getattr(tool, 'description', '')}".lower()
            if any(req not in text for req in required):
                continue
            score = sum(3 for word in preferred if word in text) + sum(1 for word in required if word in text)
            if score > best_score:
                best_name = name
                best_score = score
        return best_name

    def _schema_properties(self, tool: Any) -> Dict[str, Any]:
        schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}
        if hasattr(schema, "model_dump"):
            schema = schema.model_dump(mode="json")
        return schema.get("properties", {}) if isinstance(schema, dict) else {}

    def _build_search_args(self, tool: Any, query: str) -> Dict[str, Any]:
        props = self._schema_properties(tool)
        for key in ("query", "search_query", "searchTerm", "search_term", "q", "text", "keyword"):
            if key in props:
                return {key: query}
        return {"query": query}

    def _build_add_args(self, tool: Any, product: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
        props = self._schema_properties(tool)
        product_id = self._find_product_id(product)
        quantity = item.get("amount", item.get("qty", item.get("quantity", 1)))
        args: Dict[str, Any] = {}

        for key in ("product_id", "productId", "sku_id", "skuId", "variant_id", "variantId", "id", "item_id", "itemId"):
            if key in props and product_id:
                args[key] = product_id
                break

        for key in ("quantity", "qty", "count", "amount"):
            if key in props:
                args[key] = quantity
                break

        if not args and product_id:
            args = {"product_id": product_id, "quantity": quantity}

        return args

    def _build_selection_args(self, tool: Any, value: Any, kind: str) -> Dict[str, Any]:
        props = self._schema_properties(tool)
        args: Dict[str, Any] = {}
        candidate_keys = (
            "address_id", "addressId", "selected_address_id", "id"
        ) if kind == "address" else (
            "payment_method_id", "paymentMethodId", "payment_method", "method", "id"
        )
        for key in candidate_keys:
            if key in props:
                args[key] = value
                break
        if not args and value:
            args = {candidate_keys[0]: value}
        return args

    def _find_address_selection_tool(self, tools: Dict[str, Any]) -> str | None:
        if "select_saved_address" in tools:
            return "select_saved_address"

        for name, tool in tools.items():
            text = f"{name} {getattr(tool, 'description', '')}".lower()
            if "address" in text and any(word in text for word in ("select", "set", "choose")):
                return name
        return None

    async def _select_store_context(
        self,
        session: Any,
        tools: Dict[str, Any],
        selected_address_id: str,
    ) -> Dict[str, Any]:
        address_tool = self._find_address_selection_tool(tools)
        if not address_tool:
            return self._error(
                "missing_select_address_tool",
                "Zepto did not expose a tool that can establish store context from a saved address.",
                selected_address_id=selected_address_id,
            )

        try:
            selection_result = await self._call_tool(
                session,
                address_tool,
                self._build_selection_args(
                    tools[address_tool],
                    selected_address_id,
                    "address",
                ),
            )
        except Exception as exc:
            return self._error(
                "store_context_unavailable",
                f"Zepto could not establish store context for the selected address: {exc}",
                selected_address_id=selected_address_id,
            )

        tool_error = self._tool_error_message(selection_result)
        if tool_error:
            return self._error(
                "store_context_unavailable",
                f"Zepto could not establish store context for the selected address: {tool_error}",
                selected_address_id=selected_address_id,
            )

        return {
            "status": "ready",
            "provider": "zepto",
            "state": "store_context_ready",
            "selected_address_id": selected_address_id,
            "address_tool": address_tool,
            "selection_result": selection_result,
        }

    def _build_order_args(self, tool: Any, review: Dict[str, Any]) -> Dict[str, Any]:
        args = self._build_empty_or_default_args(tool)
        props = self._schema_properties(tool)
        selected_address = review.get("selected_address_id")
        selected_payment = review.get("selected_payment_method_id")

        for key in ("address_id", "addressId", "selected_address_id"):
            if key in props and selected_address:
                args[key] = selected_address
                break

        for key in ("payment_method_id", "paymentMethodId", "payment_method", "method"):
            if key in props and selected_payment:
                args[key] = selected_payment
                break

        return args

    def _build_zepto_cart_item(self, product: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any] | None:
        product_variant_id = product.get("productVariantId") or product.get("variantId") or product.get("id")
        store_product_id = product.get("storeProductId")
        if not product_variant_id or not store_product_id:
            return None

        quantity = 1
        unit = str(item.get("unit") or "").lower()
        try:
            amount = float(item.get("amount") or 1)
        except (TypeError, ValueError):
            amount = 1
        if unit in {"piece", "pieces", "pc", "pcs", "pack", "packs"}:
            quantity = max(1, round(amount))

        return {
            "productVariantId": product_variant_id,
            "storeProductId": store_product_id,
            "quantity": quantity,
            "name": product.get("name") or product.get("title") or item.get("name"),
            "label": product.get("label") or "",
            "price": product.get("price"),
            "mrp": product.get("mrp"),
            "imageUrl": product.get("imageUrl"),
            "packSize": product.get("packSize"),
            "availableQuantity": product.get("availableQuantity"),
            "isAd": bool(product.get("isAd", False)),
            "variantId": product.get("variantId") or product_variant_id,
            "cartProductId": product.get("cartProductId") or product_variant_id,
        }

    async def _checkout_context(self, session: Any, tools: Dict[str, Any]) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "addresses": None,
            "payment_methods": None,
            "address_tool": None,
            "payment_tool": None,
        }

        address_tool = "list_saved_addresses" if "list_saved_addresses" in tools else self._find_tool(
            tools,
            required=("address",),
            preferred=("get", "list", "show", "view"),
        )
        payment_tool = "get_payment_methods" if "get_payment_methods" in tools else self._find_tool(
            tools,
            required=("payment",),
            preferred=("get", "list", "show", "view"),
        )

        if address_tool:
            context["address_tool"] = address_tool
            try:
                addresses = await self._call_tool(session, address_tool, self._build_empty_or_default_args(tools[address_tool]))
                address_error = self._tool_error_message(addresses)
                if address_error:
                    context["address_error"] = address_error
                else:
                    context["addresses"] = addresses
            except Exception as exc:
                context["address_error"] = str(exc)

        if payment_tool:
            context["payment_tool"] = payment_tool
            try:
                payment_methods = await self._call_tool(session, payment_tool, self._build_empty_or_default_args(tools[payment_tool]))
                payment_error = self._tool_error_message(payment_methods)
                if payment_error:
                    context["payment_error"] = payment_error
                else:
                    context["payment_methods"] = payment_methods
            except Exception as exc:
                context["payment_error"] = str(exc)

        return context

    async def _apply_checkout_selection(self, session: Any, tools: Dict[str, Any], review: Dict[str, Any]) -> None:
        selected_address = review.get("selected_address_id")
        selected_payment = review.get("selected_payment_method_id")

        if selected_address:
            address_tool = self._find_address_selection_tool(tools)
            if address_tool:
                selection_result = await self._call_tool(
                    session,
                    address_tool,
                    self._build_selection_args(
                        tools[address_tool],
                        selected_address,
                        "address",
                    ),
                )
                selection_error = self._tool_error_message(selection_result)
                if selection_error:
                    raise RuntimeError(selection_error)

        if selected_payment:
            payment_tool = self._find_tool(tools, required=("payment",), preferred=("select", "set", "update", "choose"))
            if payment_tool:
                await self._call_tool(session, payment_tool, self._build_selection_args(tools[payment_tool], selected_payment, "payment"))

    def _build_empty_or_default_args(self, tool: Any) -> Dict[str, Any]:
        props = self._schema_properties(tool)
        args: Dict[str, Any] = {}
        for key, schema in props.items():
            if isinstance(schema, dict) and "default" in schema:
                args[key] = schema["default"]
        return args

    def _tool_error_message(self, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        if payload.get("isError") is not True and payload.get("is_error") is not True:
            return None

        content = payload.get("content")
        if isinstance(content, list):
            messages = [
                str(item.get("text")).strip()
                for item in content
                if isinstance(item, dict) and item.get("text")
            ]
            if messages:
                return " ".join(messages)

        message = payload.get("message") or payload.get("error")
        return str(message).strip() if message else "Zepto returned an unspecified tool error."

    def _first_product(self, payload: Any) -> Dict[str, Any] | None:
        products = []
        self._collect_products(payload, products)
        return products[0] if products else None

    def _collect_products(self, value: Any, products: List[Dict[str, Any]]) -> None:
        if isinstance(value, dict):
            text = value.get("text")
            if isinstance(text, str):
                try:
                    self._collect_products(json.loads(text), products)
                except json.JSONDecodeError:
                    pass

            keys = {str(k).lower() for k in value.keys()}
            product_id_keys = {
                "id",
                "productid",
                "product_id",
                "productvariantid",
                "storeproductid",
                "skuid",
                "sku_id",
                "variantid",
                "variant_id",
            }
            if keys & product_id_keys and keys & {"name", "title", "productname", "product_name"}:
                products.append(value)

            for child in value.values():
                self._collect_products(child, products)
        elif isinstance(value, list):
            for child in value:
                self._collect_products(child, products)

    def _find_product_id(self, product: Dict[str, Any]) -> Any:
        for key in ("product_id", "productId", "sku_id", "skuId", "variant_id", "variantId", "id"):
            if product.get(key):
                return product[key]
        return None
