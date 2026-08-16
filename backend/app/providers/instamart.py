"""Swiggy Instamart MCP adapter with confirmed-cart reconciliation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List

from app.providers.base import (
    GroceryProviderAdapter,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderOperationError,
)
from app.providers.catalog_matcher import ProviderCatalogMatcher
from app.providers.mcp_client import McpProviderClient, to_plain
from app.providers.swiggy_oauth import SwiggyOAuthBroker
from app.supabase_client import update_provider_connection_status


REQUIRED_INSTAMART_TOOLS = {
    "get_addresses",
    "search_products",
    "update_cart",
    "get_cart",
    "get_payment_options",
}
ALLOWED_INSTAMART_TOOLS = REQUIRED_INSTAMART_TOOLS | {
    "checkout",
    "get_orders",
    "get_order_details",
    "track_order",
    "check_payment_status",
    "confirm_order",
}


class InstamartProviderAdapter(GroceryProviderAdapter):
    provider_id = "swiggy_instamart"

    def __init__(
        self,
        *,
        oauth: SwiggyOAuthBroker | None = None,
        matcher: ProviderCatalogMatcher | None = None,
        client: McpProviderClient | None = None,
    ) -> None:
        self.oauth = oauth or SwiggyOAuthBroker()
        self.environment = self.oauth.environment
        default_url = (
            "https://mcp-staging.swiggy.com/im"
            if self.environment == "staging"
            else "https://mcp.swiggy.com/im"
        )
        self.url = os.environ.get("SWIGGY_INSTAMART_MCP_URL", default_url)
        self.enabled = os.environ.get("SWIGGY_INSTAMART_ENABLED", "false").lower() in {
            "1", "true", "yes"
        }
        self.matcher = matcher or ProviderCatalogMatcher()
        self._client = client

    def descriptor(self) -> ProviderDescriptor:
        if not self.enabled:
            state = "disabled"
            message = "Swiggy Instamart is disabled in this environment."
        else:
            connection = self.oauth.connection_status()
            state = str(connection["state"])
            message = str(connection["message"])
        return ProviderDescriptor(
            id=self.provider_id,
            label="Swiggy Instamart",
            brand_label="instamart",
            description="Address-scoped grocery search, confirmed cart review, and guarded checkout.",
            enabled=self.enabled and state != "gated",
            state=state,
            message=message,
            environment=self.environment,
            badge="Staging" if self.environment == "staging" else None,
            requires_connection=True,
            production_gated=state == "gated",
            capabilities=ProviderCapabilities(
                saved_addresses=True,
                cart_sync=True,
                cart_revalidation=True,
                checkout=True,
                payment_status=True,
                order_history=True,
                order_tracking=True,
            ),
            theme={"start": "#ff7f22", "end": "#d84b10"},
        )

    def _client_for_request(self) -> McpProviderClient:
        if self._client is not None:
            return self._client
        return McpProviderClient(
            url=self.url,
            access_token=self.oauth.access_token(),
            provider_id=self.provider_id,
            environment=self.environment,
        )

    async def readiness(self) -> Dict[str, Any]:
        descriptor = self.descriptor()
        if not descriptor.enabled or descriptor.state != "connected":
            return await super().readiness()
        try:
            client = self._client_for_request()
            async with client.session() as session:
                _, version = await self._validated_tools(
                    client,
                    session,
                    REQUIRED_INSTAMART_TOOLS | {"checkout"},
                )
            return {
                "provider": self.provider_id,
                "environment": self.environment,
                "state": "ready",
                "message": "Instamart authentication and required MCP capabilities are ready.",
                "capability_version": version,
            }
        except Exception as exc:
            self._mark_401(exc)
            return {
                "provider": self.provider_id,
                "environment": self.environment,
                "state": "degraded",
                "message": "Instamart is connected, but its required MCP capabilities could not be verified.",
            }

    async def list_addresses(self) -> Dict[str, Any]:
        client = self._client_for_request()
        try:
            async with client.session() as session:
                tools, version = await self._validated_tools(client, session, {"get_addresses"})
                addresses: List[Dict[str, Any]] = []
                seen_address_ids: set[str] = set()
                page = 1
                while True:
                    payload = self._unwrap(
                        await client.call_tool(
                            session,
                            "get_addresses",
                            {"page": page, "pageSize": 10},
                        ),
                        prefer_structured=True,
                    )
                    for address in self._normalize_addresses(payload):
                        if address["id"] in seen_address_ids:
                            continue
                        seen_address_ids.add(address["id"])
                        addresses.append(address)

                    pagination = payload.get("pagination")
                    has_more = (
                        bool(pagination.get("hasMore"))
                        if isinstance(pagination, dict)
                        else False
                    )
                    if not has_more:
                        break
                    if page >= 100:
                        raise ProviderOperationError(
                            provider=self.provider_id,
                            operation="list_addresses",
                            code="provider_response_malformed",
                            message="Instamart returned invalid address pagination.",
                            retryable=True,
                        )
                    page += 1
                return {
                    "status": "success",
                    "provider": self.provider_id,
                    "provider_label": "Swiggy Instamart",
                    "capability_version": version,
                    "addresses": addresses,
                    "message": "Select a Swiggy delivery address before synchronizing Instamart.",
                }
        except ProviderOperationError:
            raise
        except Exception as exc:
            self._mark_401(exc)
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="list_addresses",
                code="provider_address_lookup_failed",
                message="Kitch could not read Swiggy delivery addresses.",
                retryable=True,
            ) from exc

    async def sync_cart(
        self,
        items: List[Dict[str, Any]],
        selected_address_id: str = "",
    ) -> Dict[str, Any]:
        if not selected_address_id:
            return self._error(
                "address_required",
                "Select a Swiggy delivery address before moving items to Instamart.",
            )
        if not items:
            return self._error("cart_empty", "Select at least one native grocery item.")
        client = self._client_for_request()
        try:
            async with client.session() as session:
                tools, version = await self._validated_tools(client, session, REQUIRED_INSTAMART_TOOLS)
                selections: List[Dict[str, Any]] = []
                unavailable: List[Dict[str, Any]] = []
                for item in items:
                    query = str(item.get("search_name") or item.get("name") or "").strip()
                    try:
                        requested_amount = float(item.get("amount") or 0)
                    except (TypeError, ValueError):
                        requested_amount = 0
                    if requested_amount <= 0:
                        unavailable.append({
                            "name": item.get("name"),
                            "reason": "The native item has an invalid quantity.",
                            "candidates": [],
                        })
                        continue
                    search_payload = self._unwrap(
                        await client.call_tool(
                            session,
                            "search_products",
                            {"addressId": selected_address_id, "query": query},
                        )
                    )
                    candidates = self._product_candidates(search_payload, item)
                    decision = await self.matcher.choose(item, candidates)
                    candidate = next(
                        (
                            value for value in candidates
                            if decision and value["candidate_id"] == decision["candidate_id"]
                        ),
                        None,
                    )
                    if not candidate:
                        unavailable.append(
                            {
                                "name": item.get("name"),
                                "reason": "Instamart did not return one unambiguous orderable variant.",
                                "candidates": candidates[:5],
                            }
                        )
                        continue
                    selections.append(
                        {
                            "native_item": item,
                            "matched_product": candidate,
                            "matching": decision,
                            "cart_item": {
                                **candidate,
                                "quantity": candidate["requested_quantity"],
                            },
                        }
                    )

                if not selections:
                    return {
                        **self._base_result(version, selected_address_id),
                        "status": "blocked",
                        "items": [],
                        "unavailable_items": unavailable,
                        "provider_cart": None,
                        "cart_summary": self._empty_summary(),
                        "payment_options": [],
                        "message": "No selected item had an orderable Instamart match, so the provider cart was not changed.",
                    }

                update_items = [
                    {
                        "spinId": match["matched_product"]["spin_id"],
                        "skuId": match["matched_product"]["sku_id"],
                        "quantity": match["cart_item"]["quantity"],
                    }
                    for match in selections
                ]
                update_payload = self._unwrap(
                    await client.call_tool(
                        session,
                        "update_cart",
                        {
                            "selectedAddressId": selected_address_id,
                            "items": update_items,
                        },
                    )
                )
                self._raise_tool_failure(update_payload, "update_cart")
                confirmed_payload = self._unwrap(await client.call_tool(session, "get_cart", {}))
                self._raise_tool_failure(confirmed_payload, "get_cart")
                confirmed_cart = self._normalize_cart(confirmed_payload)
                confirmed, reconciliation_failures = self._reconcile(selections, confirmed_cart["items"])
                payment_payload = self._unwrap(
                    await client.call_tool(session, "get_payment_options", {})
                )
                self._raise_tool_failure(payment_payload, "get_payment_options")
                payment_options = self._payment_options(payment_payload)
                unavailable.extend(reconciliation_failures)
                status = "success" if len(confirmed) == len(items) and not unavailable else "blocked"
                return {
                    **self._base_result(version, selected_address_id),
                    "status": status,
                    "items": confirmed,
                    "unavailable_items": unavailable,
                    "replacements": [],
                    "changes": [],
                    "changed": False,
                    "provider_cart": confirmed_cart,
                    "cart_summary": self._cart_summary(confirmed_payload, confirmed),
                    "payment_options": payment_options,
                    "checkout_context": {"payment_methods": payment_options},
                    "message": (
                        "The Instamart cart was replaced and confirmed for review."
                        if status == "success"
                        else "Instamart did not confirm every selected item and quantity."
                    ),
                }
        except ProviderOperationError as exc:
            return self._error(exc.code, exc.message)
        except Exception as exc:
            self._mark_401(exc)
            return self._error(
                "provider_cart_sync_failed",
                "Kitch could not synchronize the Instamart cart.",
            )

    async def revalidate_cart(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        refreshed = await self.sync_cart(
            list(draft.get("mapped_items") or draft.get("native_items") or []),
            str(draft.get("selected_address_id") or ""),
        )
        if refreshed.get("status") == "error":
            return refreshed
        previous = list(draft.get("matched_items") or [])
        current = list(refreshed.get("items") or [])
        previous_by_native = {
            str((item.get("native_item") or {}).get("id")): item for item in previous
        }
        replacements = []
        changes = []
        for match in current:
            native_id = str((match.get("native_item") or {}).get("id"))
            old = previous_by_native.get(native_id)
            if not old:
                changes.append({"type": "added", "native_item": match.get("native_item")})
                continue
            old_product = old.get("matched_product") or {}
            new_product = match.get("matched_product") or {}
            if old_product.get("candidate_id") != new_product.get("candidate_id"):
                replacements.append(
                    {
                        "native_item": match.get("native_item"),
                        "previous_product": old_product,
                        "replacement_product": new_product,
                    }
                )
            else:
                old_cart = old.get("cart_item") or {}
                new_cart = match.get("cart_item") or {}
                changed_fields = [
                    key for key in ("price_minor", "pack_size", "quantity", "store_id")
                    if old_cart.get(key) != new_cart.get(key)
                ]
                if changed_fields:
                    changes.append({
                        "type": "product_changed",
                        "native_item": match.get("native_item"),
                        "fields": changed_fields,
                    })
        if len(previous) != len(current):
            changes.append({"type": "membership_changed"})
        if (draft.get("cart_summary") or {}) != (refreshed.get("cart_summary") or {}):
            changes.append({"type": "bill_changed"})
        previous_payments = [
            (option.get("id"), option.get("kind"), option.get("flow"), option.get("provider_value"))
            for option in draft.get("payment_options") or []
        ]
        current_payments = [
            (option.get("id"), option.get("kind"), option.get("flow"), option.get("provider_value"))
            for option in refreshed.get("payment_options") or []
        ]
        if previous_payments != current_payments:
            changes.append({"type": "payment_methods_changed"})
        previous_cart = draft.get("provider_cart") or {}
        refreshed_cart = refreshed.get("provider_cart") or {}
        if previous_cart.get("stores") != refreshed_cart.get("stores"):
            changes.append({"type": "store_fulfillment_changed"})
        refreshed["replacements"] = replacements
        refreshed["changes"] = changes
        refreshed["changed"] = bool(replacements or changes or refreshed.get("unavailable_items"))
        return refreshed

    async def get_cart(self) -> Dict[str, Any]:
        client = self._client_for_request()
        async with client.session() as session:
            _, version = await self._validated_tools(
                client,
                session,
                {"get_cart", "get_payment_options"},
            )
            payload = self._unwrap(await client.call_tool(session, "get_cart", {}))
            payment_payload = self._unwrap(
                await client.call_tool(session, "get_payment_options", {})
            )
            return {
                "status": "success",
                "provider": self.provider_id,
                "capability_version": version,
                "provider_cart": self._normalize_cart(payload),
                "cart_summary": self._cart_summary(payload),
                "payment_options": self._payment_options(payment_payload),
            }

    async def place_order(self, review: Dict[str, Any] | None = None) -> Dict[str, Any]:
        review = review or {}
        selected_payment = str(review.get("selected_payment_method_id") or "")
        allowed_payments = list(review.get("payment_options") or [])
        selected = next(
            (option for option in allowed_payments if str(option.get("id")) == selected_payment),
            None,
        )
        if not selected:
            return self._error(
                "payment_method_required",
                "Select a payment method returned by Instamart before ordering.",
            )
        client = self._client_for_request()
        try:
            async with client.session() as session:
                tools, version = await self._validated_tools(client, session, {"checkout"})
                args: Dict[str, Any] = {"addressId": review.get("selected_address_id")}
                if selected.get("kind") == "upi":
                    args["paymentMethod"] = "UPI"
                    if selected.get("flow") == "upi_qr":
                        args["generateUPIQR"] = True
                    else:
                        args["intentApp"] = selected.get("provider_value") or selected["id"]
                elif selected.get("kind") == "cod":
                    args["paymentMethod"] = selected.get("provider_value") or "Cash"
                else:
                    return self._error(
                        "payment_method_invalid",
                        "The selected Instamart payment method is no longer supported.",
                    )
                payload = self._unwrap(await client.call_tool(session, "checkout", args))
                self._raise_tool_failure(payload, "checkout")
                order_ids = self._find_values(payload, {"orderId", "order_id"})
                status_text = " ".join(str(value) for value in self._find_values(payload, {"status", "paymentStatus"})).lower()
                pending = "pending" in status_text
                order_id = self._first(payload, "orderId", "order_id")
                paas_id = self._first(payload, "paasId", "paas_id")
                return {
                    "status": "payment_pending" if pending else "success",
                    "provider": self.provider_id,
                    "capability_version": version,
                    "provider_order_ids": list(dict.fromkeys(str(value) for value in order_ids if value)),
                    "order_results": self._normalize_order_results(payload),
                    "payment_state": {
                        "status": "pending" if pending else "confirmed",
                        "paas_id": str(paas_id) if paas_id else None,
                        "order_id": str(order_id) if order_id else None,
                        "upi_intent_url": self._first(payload, "upiIntentUrl", "upi_intent_url"),
                        "bridge_url": self._first(payload, "bridgeUrl", "bridge_url"),
                        "is_qr_flow": bool(self._first(payload, "isQrFlow", "is_qr_flow")),
                        "polling_interval_ms": self._first(payload, "pollingIntervalInMs"),
                        "max_poll_time_ms": self._first(payload, "maxTimeToPollForInMs"),
                    },
                    "message": str(payload.get("message") or "Instamart checkout completed."),
                }
        except ProviderOperationError as exc:
            return self._error(exc.code, exc.message)
        except Exception as exc:
            self._mark_401(exc)
            history = await self._order_history_after_ambiguous_failure()
            return {
                "status": "unknown",
                "provider": self.provider_id,
                "code": "checkout_ambiguous",
                "message": "Instamart checkout may have reached Swiggy. Kitch blocked another attempt while the order is verified.",
                "ambiguous_order": True,
                "order_results": history,
            }

    async def payment_status(self, review: Dict[str, Any]) -> Dict[str, Any]:
        client = self._client_for_request()
        async with client.session() as session:
            tools, _ = await self._validated_tools(client, session, set())
            if "check_payment_status" not in tools:
                return self._error(
                    "payment_status_unsupported",
                    "Instamart does not currently expose a documented payment-status operation.",
                )
            payment_state = review.get("payment_state") or {}
            order_id = payment_state.get("order_id") or next(
                iter(review.get("provider_order_ids") or []), None
            )
            paas_id = payment_state.get("paas_id")
            if not paas_id:
                return self._error(
                    "provider_payment_reference_missing",
                    "No Instamart payment reference is available to check.",
                )
            payload = self._unwrap(
                await client.call_tool(
                    session,
                    "check_payment_status",
                    {"paasId": paas_id, **({"orderId": order_id} if order_id else {})},
                )
            )
            self._raise_tool_failure(payload, "check_payment_status")
            status = str(self._first(payload, "status") or "pending").lower()
            terminal = bool(self._first(payload, "terminal"))
            terminal_success = bool(self._first(payload, "isTerminalSuccess"))
            return {
                "status": "success" if terminal_success else "payment_failed" if terminal else "payment_pending",
                "provider": self.provider_id,
                "payment_state": {
                    **payment_state,
                    "status": status,
                    "terminal": terminal,
                    "terminal_success": terminal_success,
                    "terminal_failure": bool(self._first(payload, "isTerminalFailure")),
                    "confirmed": bool(self._first(payload, "confirmed")),
                    "order_status": self._first(payload, "orderStatus"),
                },
            }

    async def _validated_tools(
        self,
        client: McpProviderClient,
        session: Any,
        required: set[str],
    ) -> tuple[Dict[str, Any], str]:
        discovered = await client.list_tools(session)
        tools = {name: tool for name, tool in discovered.items() if name in ALLOWED_INSTAMART_TOOLS}
        missing = sorted(required - set(tools))
        if missing:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="discover_tools",
                code="provider_contract_incompatible",
                message=f"Instamart is missing required capabilities: {', '.join(missing)}.",
                retryable=False,
            )
        incompatible = sorted(
            name for name in required
            if not self._schema_is_compatible(
                name,
                McpProviderClient.input_schema(tools[name]),
            )
        )
        if incompatible:
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="discover_tools",
                code="provider_contract_incompatible",
                message=f"Instamart returned incompatible tool schemas: {', '.join(incompatible)}.",
                retryable=False,
            )
        contract = {
            name: McpProviderClient.input_schema(tool)
            for name, tool in sorted(tools.items())
        }
        version = hashlib.sha256(
            json.dumps(contract, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
        return tools, version

    @staticmethod
    def _schema_is_compatible(name: str, schema: Dict[str, Any]) -> bool:
        mandatory = {
            "get_addresses": set(),
            "search_products": {"addressId", "query"},
            "update_cart": {"selectedAddressId", "items"},
            "get_cart": set(),
            "get_payment_options": set(),
            "checkout": {"addressId"},
            "check_payment_status": {"paasId"},
        }.get(name, set())
        if not isinstance(schema, dict) or schema.get("type") not in {None, "object"}:
            return False
        if not mandatory:
            return True
        properties = schema.get("properties")
        required = schema.get("required")
        return (
            isinstance(properties, dict)
            and mandatory.issubset(properties)
            and isinstance(required, list)
            and mandatory.issubset(set(required))
        )

    def _base_result(self, version: str, address_id: str) -> Dict[str, Any]:
        return {
            "provider": self.provider_id,
            "provider_label": "Swiggy Instamart",
            "capability_version": version,
            "store_context": {
                "status": "ready",
                "state": "store_context_ready",
                "selected_address_id": address_id,
            },
        }

    def _unwrap(self, payload: Any, *, prefer_structured: bool = False) -> Dict[str, Any]:
        value = to_plain(payload)
        if (
            prefer_structured
            and isinstance(value, dict)
            and isinstance(value.get("structuredContent"), dict)
        ):
            self._raise_tool_failure(value, "provider_call")
            value = value["structuredContent"]
        elif isinstance(value, dict) and isinstance(value.get("content"), list):
            for block in value["content"]:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            value = parsed
                            break
                    except json.JSONDecodeError:
                        continue
        if not isinstance(value, dict):
            raise ProviderOperationError(
                provider=self.provider_id,
                operation="parse_response",
                code="provider_response_malformed",
                message="Instamart returned a malformed response.",
                retryable=True,
            )
        self._raise_tool_failure(value, "provider_call")
        data = value.get("data")
        return data if isinstance(data, dict) else value

    def _raise_tool_failure(self, payload: Dict[str, Any], operation: str) -> None:
        if payload.get("success") is False or payload.get("isError") is True:
            error = payload.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise ProviderOperationError(
                provider=self.provider_id,
                operation=operation,
                code="provider_operation_rejected",
                message=str(message or "Instamart rejected the operation."),
                retryable=False,
            )

    def _normalize_addresses(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        objects = self._all_objects(payload)
        addresses = []
        for value in objects:
            address_id = self._first(value, "id", "addressId", "address_id")
            if not address_id:
                continue
            label = self._first(
                value,
                "label",
                "addressTag",
                "address_tag",
                "addressCategory",
                "address_category",
                "type",
                "name",
                "addressLabel",
            )
            full = self._first(
                value,
                "addressLine",
                "address_line",
                "displayText",
                "display_text",
                "formattedAddress",
                "formatted_address",
                "fullAddress",
                "full_address",
                "address",
            )
            label_text = str(label or "").strip()
            full_text = str(full or "").strip()
            if not label_text and not full_text:
                continue
            addresses.append({
                "id": str(address_id),
                "label": label_text or "Saved address",
                "address": full_text or label_text,
            })
        deduped = {address["id"]: address for address in addresses}
        return list(deduped.values())

    def _product_candidates(
        self,
        payload: Dict[str, Any],
        native_item: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        product_lists = self._lists_for_keys(payload, {"products", "similarProducts", "similar_products"})
        for products in product_lists:
            for product in products:
                if not isinstance(product, dict):
                    continue
                variations = product.get("variations") or product.get("variants") or [product]
                if not isinstance(variations, list):
                    variations = [product]
                for variation in variations:
                    if not isinstance(variation, dict):
                        continue
                    merged = {**product, **variation}
                    spin_id = self._first(merged, "spinId", "spin_id")
                    sku_id = self._first(merged, "skuId", "sku_id")
                    if not spin_id or not sku_id:
                        continue
                    pack_size = str(self._first(
                        merged,
                        "packSize",
                        "itemVariant",
                        "quantityDescription",
                        "unit",
                    ) or "")
                    requested_quantity = self._requested_pack_quantity(native_item, pack_size)
                    if requested_quantity is None:
                        continue
                    available_value = self._first(merged, "available", "isAvailable", "inStock", "orderable")
                    available_quantity = self._first(
                        merged,
                        "availableQuantity",
                        "available_quantity",
                        "inventory",
                        "stock",
                        "maxQuantity",
                    )
                    if isinstance(available_value, str):
                        available = available_value.lower() in {"true", "yes", "available", "in_stock"}
                    else:
                        available = available_value is True
                    try:
                        quantity = int(available_quantity)
                    except (TypeError, ValueError):
                        # A boolean in-stock flag does not prove the requested
                        # quantity is orderable. Missing stock counts stay
                        # unverified and cannot authorize cart mutation.
                        quantity = 0
                    candidates.append(
                        {
                            "candidate_id": f"{spin_id}:{sku_id}",
                            "spin_id": str(spin_id),
                            "sku_id": str(sku_id),
                            "name": str(self._first(
                                merged,
                                "name",
                                "itemName",
                                "title",
                                "productName",
                            ) or "Instamart product"),
                            "brand": str(self._first(merged, "brand", "brandName") or ""),
                            "pack_size": pack_size,
                            "price_minor": self._minor(self._first(
                                merged,
                                "sellingPrice",
                                "price",
                                "discountedPrice",
                                "discountedFinalPrice",
                            )),
                            "image_url": self._first(merged, "imageUrl", "image_url", "thumbnail"),
                            "available": available,
                            "available_quantity": quantity,
                            "requested_quantity": requested_quantity,
                        }
                    )
        return list({item["candidate_id"]: item for item in candidates}.values())

    @staticmethod
    def _requested_pack_quantity(native_item: Dict[str, Any], pack_size: str) -> int | None:
        try:
            amount = float(native_item.get("amount") or 0)
        except (TypeError, ValueError):
            return None
        if amount <= 0:
            return None
        unit = str(native_item.get("unit") or "piece").strip().lower()
        normalized_unit = re.sub(r"[^a-z]", "", unit)
        native_scales = {
            "ml": ("volume", 1.0), "milliliter": ("volume", 1.0), "milliliters": ("volume", 1.0),
            "l": ("volume", 1000.0), "liter": ("volume", 1000.0), "liters": ("volume", 1000.0),
            "cup": ("volume", 240.0), "cups": ("volume", 240.0),
            "tbsp": ("volume", 15.0), "tablespoon": ("volume", 15.0), "tablespoons": ("volume", 15.0),
            "tsp": ("volume", 5.0), "teaspoon": ("volume", 5.0), "teaspoons": ("volume", 5.0),
            "g": ("weight", 1.0), "gram": ("weight", 1.0), "grams": ("weight", 1.0),
            "kg": ("weight", 1000.0), "kilogram": ("weight", 1000.0), "kilograms": ("weight", 1000.0),
        }
        pack_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(ml|l|litres?|liters?|g|kg|grams?|kilograms?)\b", pack_size.lower())
        if normalized_unit in native_scales and pack_match:
            pack_unit = re.sub(r"[^a-z]", "", pack_match.group(2))
            aliases = {
                "litre": "l", "litres": "l", "liter": "l", "liters": "l",
                "gram": "g", "grams": "g", "kilogram": "kg", "kilograms": "kg",
            }
            pack_unit = aliases.get(pack_unit, pack_unit)
            pack_scale = native_scales.get(pack_unit)
            native_scale = native_scales[normalized_unit]
            if not pack_scale or pack_scale[0] != native_scale[0]:
                return None
            desired_base = amount * native_scale[1]
            pack_base = float(pack_match.group(1)) * pack_scale[1]
            return max(1, int(math.ceil(desired_base / pack_base)))
        if normalized_unit in native_scales and pack_match is None:
            return None
        return max(1, int(math.ceil(amount)))

    def _normalize_cart(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        lines = []
        for value in self._all_objects(payload):
            spin_id = self._first(value, "spinId", "spin_id")
            sku_id = self._first(value, "skuId", "sku_id")
            quantity = self._first(value, "quantity", "qty", "count")
            if not spin_id or not sku_id or quantity is None:
                continue
            normalized_quantity = int(quantity)
            price_minor = self._minor(self._first(
                value,
                "sellingPrice",
                "price",
                "discountedPrice",
                "discountedFinalPrice",
                "finalPrice",
                "itemPrice",
                "unitPrice",
            ))
            line_total_minor = self._minor(self._first(
                value,
                "lineTotal",
                "line_total",
                "itemSubtotal",
                "item_subtotal",
                "totalPrice",
            ))
            if line_total_minor is None and price_minor is not None:
                line_total_minor = price_minor * normalized_quantity
            lines.append(
                {
                    "candidate_id": f"{spin_id}:{sku_id}",
                    "spin_id": str(spin_id),
                    "sku_id": str(sku_id),
                    "name": str(self._first(
                        value,
                        "name",
                        "itemName",
                        "title",
                        "productName",
                    ) or "Instamart product"),
                    "quantity": normalized_quantity,
                    "price_minor": price_minor,
                    "line_total_minor": line_total_minor,
                    "pack_size": str(self._first(
                        value,
                        "packSize",
                        "itemVariant",
                        "quantityDescription",
                        "unit",
                    ) or ""),
                    "image_url": self._first(value, "imageUrl", "image_url", "thumbnail"),
                    "store_id": self._first(value, "storeId", "store_id", "merchantId", "merchant_id"),
                    "store_name": self._first(value, "storeName", "store_name", "merchantName", "merchant_name"),
                }
            )
        items = list({(line["candidate_id"], line["quantity"]): line for line in lines}.values())
        stores = {}
        for item in items:
            store_id = str(item.get("store_id") or "")
            if not store_id:
                continue
            stores.setdefault(
                store_id,
                {"id": store_id, "name": item.get("store_name") or "Instamart store", "item_count": 0},
            )["item_count"] += 1
        return {
            "items": items,
            "stores": list(stores.values()),
            "multi_store": len(stores) > 1,
        }

    def _reconcile(
        self,
        matches: List[Dict[str, Any]],
        cart_items: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        confirmed = []
        failures = []
        for match in matches:
            expected = match["cart_item"]
            actual = next(
                (
                    line for line in cart_items
                    if line.get("candidate_id") == expected.get("candidate_id")
                    and int(line.get("quantity") or 0) == int(expected.get("quantity") or 0)
                ),
                None,
            )
            if not actual:
                failures.append(
                    {
                        "name": (match.get("native_item") or {}).get("name"),
                        "reason": "The selected Instamart SKU and quantity were absent from the confirmed cart.",
                    }
                )
                continue
            confirmed.append({**match, "cart_item": actual})
        expected_ids = {match["cart_item"].get("candidate_id") for match in matches}
        unexpected = [
            line for line in cart_items
            if line.get("candidate_id") not in expected_ids
        ]
        if unexpected:
            failures.append({
                "name": "Provider cart drift",
                "reason": "Instamart returned products outside the authoritative Kitch selection.",
                "unexpected_products": [line.get("name") for line in unexpected],
            })
        return confirmed, failures

    def _cart_summary(
        self,
        payload: Dict[str, Any],
        matches: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        objects = self._all_objects(payload)
        total = self._first_minor(
            objects,
            "total",
            "grandTotal",
            "grand_total",
            "cartTotal",
            "cartTotalAmount",
            "toPay",
        )
        subtotal = self._first_minor(objects, "subtotal", "itemTotal", "item_total", "itemsTotal")
        discount = self._first_minor(objects, "discount", "discountAmount", "totalDiscount")
        fees = []
        for value in objects:
            label = self._first(value, "label", "name", "title")
            amount = self._first(value, "amount", "value", "fee")
            normalized_label = str(label or "").strip().lower()
            if subtotal is None and normalized_label in {"item total", "items total", "subtotal"}:
                subtotal = self._minor(amount)
            if discount is None and "discount" in normalized_label:
                discount = self._minor(amount)
            if label and amount is not None and any(word in str(label).lower() for word in ("fee", "charge", "handling", "delivery", "tax")):
                minor = self._minor(amount)
                if minor is not None:
                    fees.append({"label": str(label), "amount_minor": minor})
        summary = {
            "currency": "INR",
            "subtotal_minor": subtotal,
            "discount_minor": discount,
            "fees": list({(fee["label"], fee["amount_minor"]): fee for fee in fees}.values()),
            "total_minor": total,
            "total_source": "provider" if total is not None else "unavailable",
            "total_notice": (
                "Final payable total returned by Swiggy Instamart."
                if total is not None
                else "Instamart did not return a final payable total."
            ),
        }
        if subtotal is None and matches:
            values = []
            for match in matches:
                cart_item = match.get("cart_item") or {}
                price = cart_item.get("price_minor")
                quantity = cart_item.get("quantity")
                if price is None or quantity is None:
                    values = []
                    break
                values.append(int(price) * int(quantity))
            if values:
                summary["subtotal_minor"] = sum(values)
                summary["subtotal_source"] = "line_items"
        return summary

    def _payment_options(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        options: List[Dict[str, Any]] = []
        platforms = payload.get("platforms") if isinstance(payload.get("platforms"), dict) else {}
        for surface, flow in (("mobile", "upi_intent"), ("desktop", "upi_qr")):
            surface_payload = platforms.get(surface) if isinstance(platforms, dict) else None
            methods = surface_payload.get("methods") if isinstance(surface_payload, dict) else []
            for value in methods if isinstance(methods, list) else []:
                if not isinstance(value, dict):
                    continue
                identifier = self._first(value, "id", "method", "paymentMethod")
                if not identifier:
                    continue
                options.append(
                    {
                        "id": str(identifier),
                        "label": str(self._first(value, "label", "name", "title") or identifier),
                        "kind": "upi",
                        "provider_value": str(identifier),
                        "flow": flow,
                    }
                )

        values: List[Any] = []
        values.extend(self._values_for_keys(payload, {
            "allMethods", "availablePaymentMethods", "paymentMethods", "payment_methods",
        }))
        cod = payload.get("cod")
        if cod:
            values.append(cod)
        flattened = [child for value in values for child in (value if isinstance(value, list) else [value])]
        for value in flattened:
            if isinstance(value, str):
                identifier = value
                label = value
            elif isinstance(value, dict):
                identifier = self._first(value, "id", "method", "paymentMethod", "type", "name")
                label = self._first(value, "label", "title", "name", "method", "type") or identifier
            else:
                continue
            text = f"{identifier} {label}".lower()
            kind = "upi" if any(term in text for term in ("upi", "paywithqr")) else "cod" if any(term in text for term in ("cod", "cash")) else "unsupported"
            if kind == "unsupported" or not identifier:
                continue
            options.append(
                {
                    "id": str(identifier),
                    "label": str(label),
                    "kind": kind,
                    "provider_value": str(identifier),
                    "flow": "upi_qr" if "paywithqr" in text else "upi_intent" if kind == "upi" else "cash",
                }
            )
        deduped = list({option["id"]: option for option in options}.values())
        upi = [option for option in deduped if option["kind"] == "upi"]
        return upi or [option for option in deduped if option["kind"] == "cod"]

    async def _order_history_after_ambiguous_failure(self) -> List[Dict[str, Any]]:
        try:
            client = self._client_for_request()
            async with client.session() as session:
                tools, _ = await self._validated_tools(client, session, set())
                if "get_orders" not in tools:
                    return []
                payload = self._unwrap(await client.call_tool(session, "get_orders", {}))
                return self._normalize_order_results(payload)
        except Exception:
            return []

    def _normalize_order_results(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for value in self._all_objects(payload):
            order_id = self._first(value, "orderId", "order_id")
            if order_id:
                results.append(
                    {
                        "order_id": str(order_id),
                        "status": str(self._first(value, "status", "orderStatus") or "unknown"),
                        "message": str(self._first(value, "message", "description") or ""),
                    }
                )
        return list({result["order_id"]: result for result in results}.values())

    def _mark_401(self, exc: Exception) -> None:
        text = str(exc).lower()
        if "401" in text or "unauthorized" in text:
            update_provider_connection_status(
                self.provider_id,
                self.environment,
                "reconnect_required",
                "provider_unauthorized",
            )

    def _error(self, code: str, message: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "provider": self.provider_id,
            "provider_label": "Swiggy Instamart",
            "code": code,
            "message": message,
        }

    @staticmethod
    def _empty_summary() -> Dict[str, Any]:
        return {
            "currency": "INR",
            "subtotal_minor": None,
            "discount_minor": None,
            "fees": [],
            "total_minor": None,
            "total_source": "unavailable",
            "total_notice": "No confirmed provider cart is available.",
        }

    def _all_objects(self, value: Any) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []
        if isinstance(value, dict):
            found.append(value)
            for child in value.values():
                found.extend(self._all_objects(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(self._all_objects(child))
        return found

    def _lists_for_keys(self, value: Any, keys: set[str]) -> List[List[Any]]:
        found = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in keys and isinstance(child, list):
                    found.append(child)
                found.extend(self._lists_for_keys(child, keys))
        elif isinstance(value, list):
            for child in value:
                found.extend(self._lists_for_keys(child, keys))
        return found

    def _values_for_keys(self, value: Any, keys: set[str]) -> List[Any]:
        found = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in keys:
                    found.append(child)
                found.extend(self._values_for_keys(child, keys))
        elif isinstance(value, list):
            for child in value:
                found.extend(self._values_for_keys(child, keys))
        return found

    def _find_values(self, value: Any, keys: set[str]) -> List[Any]:
        return self._values_for_keys(value, keys)

    @staticmethod
    def _first(value: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if value.get(key) is not None:
                return value[key]
        return None

    def _first_minor(self, values: Iterable[Dict[str, Any]], *keys: str) -> int | None:
        for value in values:
            raw = self._first(value, *keys)
            minor = self._minor(raw)
            if minor is not None:
                return minor
        return None

    @staticmethod
    def _minor(value: Any) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, dict):
            for key in ("amount", "value", "price"):
                if key in value:
                    value = value[key]
                    break
        text = re.sub(r"[^0-9.\-]", "", str(value))
        if not text:
            return None
        try:
            return int((Decimal(text) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        except (InvalidOperation, ValueError):
            return None
