"""Zepto MCP provider adapter.

This module keeps Zepto-specific MCP behavior outside Kitch's native cart
model. The adapter is intentionally defensive because Zepto OAuth/tool schemas
are controlled by the remote MCP server.
"""

from __future__ import annotations

import json
import os
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

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        raw_headers = os.environ.get("ZEPTO_MCP_HEADERS")
        if raw_headers:
            try:
                headers.update(json.loads(raw_headers))
            except json.JSONDecodeError:
                pass

        return headers

    async def sync_cart(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Replace the Zepto cart with best matches for native cart items."""
        if not self.enabled:
            return self._error("disabled", "Zepto MCP integration is disabled.")

        if not items:
            return {
                "status": "empty",
                "message": "No unchecked, non-stocked native cart items are available for Zepto sync.",
                "items": [],
                "unavailable_items": [],
            }

        try:
            return await self._sync_cart(items)
        except Exception as exc:
            return self._error(
                "mcp_sync_failed",
                f"Zepto MCP cart sync failed: {exc}",
            )

    async def _sync_cart(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with self._session() as session:
            tools = await self._list_tools(session)
            clear_tool = self._find_tool(tools, required=("cart",), preferred=("clear", "empty", "replace"))
            search_tool = self._find_tool(tools, required=(), preferred=("search", "product", "catalog"))
            add_tool = self._find_tool(tools, required=("cart",), preferred=("add",))
            get_cart_tool = self._find_tool(tools, required=("cart",), preferred=("get", "view", "show", "list"))

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
                    unavailable_items.append({"name": item.get("name"), "reason": "No product match returned by Zepto."})
                    continue

                add_args = self._build_add_args(tools[add_tool], product, item)
                if not add_args:
                    unavailable_items.append({
                        "name": item.get("name"),
                        "reason": "Product matched, but Zepto add-to-cart tool arguments could not be inferred.",
                        "matched_product": product,
                    })
                    continue

                add_result = await self._call_tool(session, add_tool, add_args)
                matched_items.append({
                    "native_item": item,
                    "matched_product": product,
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
                "message": f"Synced {len(matched_items)} items to Zepto cart.",
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
                return {"status": "success", "provider": "zepto", "zepto_cart": cart}
        except Exception as exc:
            return self._error("mcp_get_cart_failed", f"Zepto MCP cart read failed: {exc}")

    async def place_order(self) -> Dict[str, Any]:
        """Place the currently reviewed Zepto cart order through MCP."""
        try:
            async with self._session() as session:
                tools = await self._list_tools(session)
                order_tool = self._find_tool(tools, required=("order",), preferred=("place", "checkout", "create"))
                if not order_tool:
                    return self._error("missing_place_order_tool", "Could not find a Zepto MCP tool to place an order.", available_tools=list(tools.keys()))
                result = await self._call_tool(session, order_tool, self._build_empty_or_default_args(tools[order_tool]))
                return {"status": "success", "provider": "zepto", "order_result": result}
        except Exception as exc:
            return self._error("mcp_order_failed", f"Zepto MCP order placement failed: {exc}")

    def _error(self, code: str, message: str, **extra: Any) -> Dict[str, Any]:
        return {"status": "error", "provider": "zepto", "code": code, "message": message, **extra}

    def _session(self):
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError("Python MCP client is not installed. Install the `mcp` package.") from exc

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

    def _build_empty_or_default_args(self, tool: Any) -> Dict[str, Any]:
        props = self._schema_properties(tool)
        args: Dict[str, Any] = {}
        for key, schema in props.items():
            if isinstance(schema, dict) and "default" in schema:
                args[key] = schema["default"]
        return args

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
            if keys & {"id", "productid", "product_id", "skuid", "sku_id", "variantid", "variant_id"} and keys & {"name", "title", "productname", "product_name"}:
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
