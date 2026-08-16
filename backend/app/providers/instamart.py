"""Swiggy Instamart MCP adapter with confirmed-cart reconciliation."""

from __future__ import annotations

import hashlib
import json
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
from app.providers.mcp_client import McpProviderClient, to_plain
from app.commerce_policy import CommerceToolPolicy
from app.providers.swiggy_oauth import SwiggyOAuthBroker
from app.supabase_client import update_provider_connection_status


REQUIRED_INSTAMART_TOOLS = {
    "get_addresses",
    "search_products",
    "your_go_to_items",
    "update_cart",
    "get_cart",
}
ALLOWED_INSTAMART_TOOLS = REQUIRED_INSTAMART_TOOLS | {
    "get_payment_options",
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
        self._client = client

    def confirmed_agent_result(
        self,
        native_items: List[Dict[str, Any]],
        selected_address_id: str,
        capture: Any,
    ) -> Dict[str, Any]:
        """Build durable review state from the exact final MCP cart response.

        Gemini supplies semantic mapping metadata. This method performs only
        structural ID/quantity reconciliation against captured ``get_cart``;
        it never re-ranks products or interprets pack descriptions.
        """
        for update_result in capture.tool_results.get("update_cart") or []:
            self._unwrap(update_result)
        raw_cart = self._unwrap(capture.latest("get_cart"))
        confirmed_cart = self._normalize_cart(raw_cart)
        report = capture.structured_result or {}
        report_matches = report.get("matches") if isinstance(report, dict) else []
        unresolved = report.get("unresolved_items") if isinstance(report, dict) else []
        report_matches = report_matches if isinstance(report_matches, list) else []
        unavailable = unresolved if isinstance(unresolved, list) else []
        native_by_id = {
            str(item.get("id")): item
            for item in native_items
            if item.get("id") is not None
        }
        cart_by_id = {
            (
                str(line.get("spin_id") or ""),
                str(line.get("sku_id") or ""),
            ): line
            for line in confirmed_cart.get("items") or []
        }
        confirmed: List[Dict[str, Any]] = []
        matched_native_ids: set[str] = set()
        for metadata in report_matches:
            if not isinstance(metadata, dict):
                continue
            native_id = str(
                metadata.get("native_item_id")
                or (metadata.get("native_item") or {}).get("id")
                or ""
            )
            spin_id = str(
                metadata.get("spin_id")
                or metadata.get("spinId")
                or metadata.get("selected_spin_id")
                or ""
            )
            sku_id = str(
                metadata.get("sku_id")
                or metadata.get("skuId")
                or metadata.get("selected_sku_id")
                or ""
            )
            native = native_by_id.get(native_id)
            actual = cart_by_id.get((spin_id, sku_id))
            try:
                expected_quantity = int(metadata.get("cart_quantity") or 0)
            except (TypeError, ValueError):
                expected_quantity = 0
            if not native or not actual or expected_quantity <= 0 or int(actual.get("quantity") or 0) != expected_quantity:
                unavailable.append({
                    "name": (native or {}).get("name") or metadata.get("native_item_name") or "Selected item",
                    "reason": "The agent-selected Instamart SKU and quantity were absent from the confirmed cart.",
                    "matching": metadata,
                })
                continue
            matched_native_ids.add(native_id)
            matching = {
                "matching_mode": "gemini_mcp_agent",
                "requested_quantity": metadata.get("requested_quantity"),
                "requested_unit": metadata.get("requested_unit"),
                "fulfilled_quantity": metadata.get("fulfilled_quantity"),
                "excess_quantity": metadata.get("excess_quantity"),
                "preference_source": metadata.get("preference_source") or "none",
                "alternatives_considered": metadata.get("alternatives_considered") or [],
                "confidence": metadata.get("confidence"),
                "reason": metadata.get("reasoning") or metadata.get("reason") or "Selected by the Instamart cart agent.",
            }
            confirmed.append({
                "native_item": native,
                "matched_product": {
                    **actual,
                    "name": actual.get("name") or metadata.get("product_name") or "Instamart product",
                    "pack_size": actual.get("pack_size") or metadata.get("pack") or "",
                },
                "matching": matching,
                "cart_item": actual,
            })

        unresolved_ids = {
            str(item.get("native_item_id") or (item.get("native_item") or {}).get("id") or "")
            for item in unavailable
            if isinstance(item, dict)
        }
        for native_id, native in native_by_id.items():
            if native_id not in matched_native_ids and native_id not in unresolved_ids:
                unavailable.append({
                    "native_item_id": native_id,
                    "name": native.get("name"),
                    "reason": "The Instamart agent did not confirm a product for this native item.",
                })

        payment_options = self._payment_options(raw_cart)
        return {
            **self._base_result("adk-mcp-agent-v1", selected_address_id),
            "status": "success" if confirmed else "blocked",
            "items": confirmed,
            "unavailable_items": unavailable,
            "replacements": [],
            "changes": [],
            "changed": False,
            "provider_cart": confirmed_cart,
            "cart_summary": self._cart_summary(raw_cart, confirmed),
            "payment_options": payment_options,
            "checkout_context": {"payment_methods": payment_options},
            "agent_matching": {
                "mode": "gemini_mcp_agent",
                "repair_attempted": bool(report.get("repair_attempted")),
                "update_cart_calls": len(capture.tool_results.get("update_cart") or []),
                "get_cart_calls": len(capture.tool_results.get("get_cart") or []),
            },
            "message": (
                f"Instamart confirmed {len(confirmed)} selected item"
                f"{'s' if len(confirmed) != 1 else ''}; {len(unavailable)} item"
                f"{'s were' if len(unavailable) != 1 else ' was'} not found and will not be ordered."
                if confirmed and unavailable
                else "The Instamart cart was prepared by Gemini and confirmed for review."
                if confirmed
                else "Instamart did not confirm a reasonable product for any selected item."
            ),
        }

    async def enrich_agent_result_with_payment(
        self,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Read payment capability outside the agent's MCP allowlist."""
        client = self._client_for_request()
        try:
            async with client.session() as session:
                tools, _ = await self._validated_tools(client, session, set())
                if "get_payment_options" not in tools:
                    return result
                payload = self._unwrap(
                    await client.call_tool(session, "get_payment_options", {})
                )
                options = self._payment_options(payload)
                result["payment_options"] = options
                result["checkout_context"] = {"payment_methods": options}
                return result
        except Exception as exc:
            self._mark_401(exc)
            context = dict(result.get("checkout_context") or {})
            context["payment_error"] = True
            context.setdefault("payment_methods", result.get("payment_options") or [])
            result["checkout_context"] = context
            return result

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
        raise ProviderOperationError(
            provider=self.provider_id,
            operation="sync_cart",
            code="agent_cart_service_required",
            message="Instamart cart synchronization must run through the guarded Gemini cart agent service.",
            status_code=500,
        )

    async def revalidate_cart(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        raise ProviderOperationError(
            provider=self.provider_id,
            operation="revalidate_cart",
            code="agent_cart_service_required",
            message="Instamart cart revalidation must run through the guarded Gemini cart agent service.",
            status_code=500,
        )

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
                CommerceToolPolicy.authorize("checkout")
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
        if (
            payload.get("success") is False
            or payload.get("isError") is True
            or (payload.get("error") and payload.get("success") is not True)
        ):
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
            normalized = {
                "id": str(address_id),
                "label": label_text or "Saved address",
                "address": full_text or label_text,
            }
            if bool(self._first(value, "isDefault", "is_default", "default", "selected")):
                normalized["is_default"] = True
            addresses.append(normalized)
        deduped = {address["id"]: address for address in addresses}
        return list(deduped.values())

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
