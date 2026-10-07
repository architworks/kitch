"""Provider-neutral durable grocery checkout orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List
from uuid import uuid4

from app.checkout_drafts import (
    draft_row_to_review,
    invalidate_draft_for_native_drift,
    native_snapshot_matches,
    refresh_checkout_eligibility,
    save_initial_draft,
    save_order_outcome,
    save_revalidated_draft,
    update_draft_review_fields,
)
from app.providers.base import ProviderOperationError
from app.providers.registry import ProviderRegistry, provider_registry
from app.agent.instamart_cart_agent import InstamartCartAgentService
from app.commerce_policy import (
    CommercePermission,
    commerce_request_context,
)
from app.storage import (
    apply_native_grocery_cart_changes,
    claim_provider_checkout_operation,
    get_grocery_cart,
    get_provider_checkout_draft,
    get_selected_grocery_provider,
    release_provider_checkout_operation,
    save_provider_checkout_draft,
)


CartMapper = Callable[[List[Dict[str, Any]]], Awaitable[List[Dict[str, Any]]]]
CHECKOUT_OPERATION_LEASE_SECONDS = 300


class GroceryCheckoutService:
    def __init__(
        self,
        *,
        registry: ProviderRegistry = provider_registry,
        cart_mapper: CartMapper | None = None,
        instamart_agent: InstamartCartAgentService | None = None,
    ) -> None:
        self.registry = registry
        self.cart_mapper = cart_mapper
        self.instamart_agent = instamart_agent or InstamartCartAgentService()

    def providers(self) -> Dict[str, Any]:
        return {"providers": self.registry.descriptors()}

    async def addresses(self, provider_id: str) -> Dict[str, Any]:
        adapter = self.registry.get(provider_id)
        return await adapter.list_addresses()

    def draft(self, provider_id: str) -> Dict[str, Any]:
        adapter = self.registry.get(provider_id)
        descriptor = adapter.descriptor()
        environment = descriptor.environment
        row = get_provider_checkout_draft(provider_id, environment)
        if row and row.get("native_items") and not native_snapshot_matches(row, get_grocery_cart()):
            row = invalidate_draft_for_native_drift(row)
        if row:
            row = refresh_checkout_eligibility(row, descriptor.label)
        review = draft_row_to_review(row)
        if review and not review.get("native_items"):
            review = None
        return {"status": "success", "provider": provider_id, "draft": review}

    async def read_cart_from_chat(self, provider_id: str = "") -> Dict[str, Any]:
        """Read the live provider cart without changing provider or Kitch state."""
        canonical_provider = ProviderRegistry.canonical_id(provider_id)
        if not canonical_provider:
            canonical_provider = ProviderRegistry.canonical_id(
                get_selected_grocery_provider()
            )
        if canonical_provider not in {"zepto", "swiggy_instamart"}:
            raise ProviderOperationError(
                provider=canonical_provider or "unselected",
                operation="read_cart",
                code="provider_selection_required",
                message=(
                    "Select and connect an ordering app in Groceries before "
                    "asking about its cart."
                ),
                status_code=422,
            )

        adapter = self.registry.get(canonical_provider)
        descriptor = adapter.descriptor()
        operation_id = str(uuid4())
        with commerce_request_context(
            source="chat_provider_cart_read",
            permissions={CommercePermission.READ},
            operation_id=operation_id,
        ):
            result = await adapter.get_cart()
        self._raise_result_error(canonical_provider, "read_cart", result)

        provider_cart = result.get("provider_cart") or {}
        raw_items = (
            provider_cart.get("items")
            if isinstance(provider_cart, dict)
            and isinstance(provider_cart.get("items"), list)
            else []
        )
        items = [self._readable_cart_item(item) for item in raw_items]
        summary = self._readable_cart_summary(result.get("cart_summary") or {})
        return {
            "status": "success",
            "provider": canonical_provider,
            "provider_label": descriptor.label,
            "source": "live_provider_cart",
            "read_at": datetime.now(timezone.utc).isoformat(),
            "items": items,
            "item_count": len(items),
            "cart_summary": summary,
            "multi_store": bool(
                isinstance(provider_cart, dict)
                and provider_cart.get("multi_store")
            ),
            "message": (
                f"Read the current {descriptor.label} cart without changing it."
            ),
        }

    @staticmethod
    def _money_value(value: Any, currency: str = "INR") -> Dict[str, Any] | None:
        if value is None:
            return None
        try:
            minor = int(value)
        except (TypeError, ValueError):
            return None
        major = minor / 100
        symbol = "₹" if currency == "INR" else f"{currency} "
        return {
            "minor": minor,
            "amount": major,
            "display": f"{symbol}{major:,.2f}",
        }

    @classmethod
    def _readable_cart_item(cls, item: Any) -> Dict[str, Any]:
        value = item if isinstance(item, dict) else {}
        return {
            "name": str(value.get("name") or "Provider product"),
            "pack": str(
                value.get("pack_size") or value.get("packSize") or ""
            ),
            "quantity": value.get("quantity"),
            "unit_price": cls._money_value(
                value.get("price_minor", value.get("price"))
            ),
            "line_total": cls._money_value(
                value.get("line_total_minor", value.get("lineTotal"))
            ),
            "store_name": value.get("store_name") or value.get("storeName"),
        }

    @classmethod
    def _readable_cart_summary(cls, summary: Dict[str, Any]) -> Dict[str, Any]:
        currency = str(summary.get("currency") or "INR")
        return {
            "currency": currency,
            "subtotal": cls._money_value(summary.get("subtotal_minor"), currency),
            "discount": cls._money_value(summary.get("discount_minor"), currency),
            "fees": [
                {
                    "label": str(fee.get("label") or "Fee"),
                    "amount": cls._money_value(fee.get("amount_minor"), currency),
                }
                for fee in summary.get("fees") or []
                if isinstance(fee, dict)
            ],
            "total": cls._money_value(summary.get("total_minor"), currency),
            "total_source": summary.get("total_source") or "unavailable",
            "notice": summary.get("total_notice") or "",
        }

    async def sync(
        self,
        provider_id: str,
        payload: Dict[str, Any],
        *,
        authority_source: str = "ui_sync",
    ) -> Dict[str, Any]:
        adapter = self.registry.get(provider_id)
        descriptor = adapter.descriptor()
        operation_id = str(uuid4())
        self._claim(provider_id, descriptor.environment, operation_id)
        native_cart_changed = False
        try:
            native_cart_changes = payload.get("native_cart_changes") or []
            if native_cart_changes:
                apply_native_grocery_cart_changes(native_cart_changes)
                native_cart_changed = True
            selected_ids = {str(value) for value in payload.get("cart_item_ids", [])}
            selected_address_id = str(payload.get("selected_address_id") or "").strip()
            if not selected_address_id:
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="sync_cart",
                    code="provider_address_required",
                    message=f"Select a {descriptor.label} delivery address before synchronizing the cart.",
                    status_code=422,
                )
            cart_items = get_grocery_cart()
            export_items = [
                {
                    **item,
                    "requiredAmount": float(item.get("amount") or 0),
                    "requiredUnit": item.get("unit") or "piece",
                    "amount": float(item.get("purchaseAmount") or 0),
                    "unit": item.get("purchaseUnit") or item.get("unit") or "piece",
                }
                for item in cart_items
                if float(item.get("purchaseAmount") or 0) > 0
                and (not selected_ids or str(item.get("id")) in selected_ids)
            ]
            if not export_items:
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="sync_cart",
                    code="native_cart_empty",
                    message="Select at least one eligible native-cart item.",
                    status_code=422,
                )
            if provider_id == "swiggy_instamart":
                outcome = await self.instamart_agent.synchronize(
                    adapter=adapter,
                    native_items=export_items,
                    selected_address_id=selected_address_id,
                    source=authority_source,
                    user_instruction=str(payload.get("user_instruction") or ""),
                    operation_id=operation_id,
                )
                result = adapter.confirmed_agent_result(
                    export_items,
                    selected_address_id,
                    outcome.capture,
                )
                result = await adapter.enrich_agent_result_with_payment(result)
                mapped_items = export_items
            else:
                mapped_items = (
                    await self.cart_mapper(export_items)
                    if self.cart_mapper
                    else export_items
                )
                result = await adapter.sync_cart(
                    mapped_items,
                    selected_address_id=selected_address_id,
                )
            self._raise_result_error(provider_id, "sync_cart", result)
            review = save_initial_draft(
                export_items,
                mapped_items,
                result,
                selected_address_id,
                provider_id,
                descriptor.environment,
                descriptor.label,
            )
            return {
                "status": result.get("status", "blocked"),
                "provider": provider_id,
                "native_cart_changed": native_cart_changed,
                "review": review,
            }
        except ProviderOperationError as error:
            if authority_source == "chat_sync" and native_cart_changed:
                return {
                    "status": "partial",
                    "provider": provider_id,
                    "native_cart_changed": True,
                    "provider_cart_changed": False,
                    "review": None,
                    "message": (
                        f"The native Kitch cart was updated, but the {descriptor.label} "
                        f"cart was not synchronized: {error.message}"
                    ),
                }
            raise
        finally:
            release_provider_checkout_operation(
                operation_id,
                provider_id,
                descriptor.environment,
            )

    def update_draft(
        self,
        provider_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        adapter = self.registry.get(provider_id)
        environment = adapter.descriptor().environment
        row = get_provider_checkout_draft(provider_id, environment)
        if not row or not row.get("native_items"):
            raise ProviderOperationError(
                provider=provider_id,
                operation="update_checkout",
                code="checkout_draft_missing",
                message="No provider checkout draft exists.",
                status_code=404,
            )
        allowed: Dict[str, Any] = {}
        if "selected_payment_method_id" in payload:
            selected_id = payload.get("selected_payment_method_id")
            options = list(row.get("payment_options") or [])
            selected = next(
                (option for option in options if str(option.get("id")) == str(selected_id)),
                None,
            ) if selected_id else None
            if selected_id and not selected:
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="update_checkout",
                    code="payment_method_invalid",
                    message="Select a payment method returned by the current provider cart.",
                    status_code=422,
                )
            allowed["selected_payment_method_id"] = str(selected_id) if selected_id else None
            allowed["selected_payment_method"] = selected
        if "order_review_acknowledged" in payload:
            allowed["order_review_acknowledged"] = bool(payload["order_review_acknowledged"])
        if not allowed:
            raise ProviderOperationError(
                provider=provider_id,
                operation="update_checkout",
                code="checkout_update_empty",
                message="No supported checkout fields were provided.",
                status_code=422,
            )
        return {
            "status": "success",
            "provider": provider_id,
            "draft": update_draft_review_fields(row, allowed),
        }

    async def revalidate(self, provider_id: str) -> Dict[str, Any]:
        adapter = self.registry.get(provider_id)
        descriptor = adapter.descriptor()
        operation_id = str(uuid4())
        self._claim(provider_id, descriptor.environment, operation_id)
        try:
            row = get_provider_checkout_draft(provider_id, descriptor.environment)
            if not row or not row.get("native_items"):
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="revalidate_cart",
                    code="checkout_draft_missing",
                    message="No provider checkout draft exists.",
                    status_code=404,
                )
            if not native_snapshot_matches(row, get_grocery_cart()):
                changed = invalidate_draft_for_native_drift(row)
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="revalidate_cart",
                    code="native_cart_changed",
                    message="The native cart changed. Synchronize the selected items again.",
                    status_code=409,
                    draft=changed,
                )
            current_review = draft_row_to_review(row) or {}
            result = await self._revalidate_provider(
                provider_id,
                adapter,
                current_review,
                operation_id=operation_id,
                source="ui_revalidation",
            )
            self._raise_result_error(provider_id, "revalidate_cart", result)
            review, changed = save_revalidated_draft(row, result)
            return {
                "status": result.get("status", "blocked"),
                "provider": provider_id,
                "changed": changed,
                "changes": result.get("changes") or [],
                "draft": review,
            }
        finally:
            release_provider_checkout_operation(
                operation_id,
                provider_id,
                descriptor.environment,
            )

    async def place_order(
        self,
        provider_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        adapter = self.registry.get(provider_id)
        descriptor = adapter.descriptor()
        operation_id = str(uuid4())
        self._claim(provider_id, descriptor.environment, operation_id)
        try:
            row = get_provider_checkout_draft(provider_id, descriptor.environment)
            review = draft_row_to_review(row)
            if not row or not review or payload.get("review_id") != review.get("review_id"):
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="place_order",
                    code="checkout_draft_missing",
                    message="The provider checkout draft was not found.",
                    status_code=404,
                )
            if review.get("status") in {"checkout_pending", "payment_pending", "unknown", "ordered"}:
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="place_order",
                    code="checkout_already_started",
                    message="This checkout has already started and cannot be submitted again.",
                    status_code=409,
                    draft=review,
                )
            if not review.get("can_place_order") or review.get("order_blockers"):
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="place_order",
                    code="checkout_blocked",
                    message="The reviewed provider cart is not eligible for ordering.",
                    status_code=403,
                )
            if payload.get("confirmation_token") != review.get("confirmation_token"):
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="place_order",
                    code="approval_token_invalid",
                    message="Final approval is missing or expired.",
                    status_code=403,
                )
            if payload.get("approved_snapshot_hash") != review.get("snapshot_hash"):
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="place_order",
                    code="checkout_snapshot_changed",
                    message="The provider review changed after approval.",
                    status_code=409,
                )
            if not payload.get("order_review_acknowledged") or not review.get("order_review_acknowledged"):
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="place_order",
                    code="checkout_acknowledgement_required",
                    message="Explicit final order acknowledgement is required.",
                    status_code=403,
                )
            if not review.get("selected_payment_method_id"):
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="place_order",
                    code="payment_method_required",
                    message="Select a provider-returned payment method before ordering.",
                    status_code=422,
                )
            if not native_snapshot_matches(row, get_grocery_cart()):
                changed = invalidate_draft_for_native_drift(row)
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="place_order",
                    code="native_cart_changed",
                    message="The native cart changed after approval.",
                    status_code=409,
                    draft=changed,
                )

            validation = await self._revalidate_provider(
                provider_id,
                adapter,
                review,
                operation_id=operation_id,
                source="ui_order_preflight",
            )
            self._raise_result_error(provider_id, "place_order_revalidation", validation)
            refreshed, changed = save_revalidated_draft(row, validation)
            if changed or refreshed.get("snapshot_hash") != payload.get("approved_snapshot_hash"):
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="place_order",
                    code="provider_cart_changed",
                    message="The provider cart changed during the final availability check.",
                    status_code=409,
                    draft=refreshed,
                )

            checkout_attempt_id = str(uuid4())
            pending_row = save_provider_checkout_draft(
                {
                    "status": "checkout_pending",
                    "checkout_attempt_id": checkout_attempt_id,
                    "ambiguous_order": False,
                },
                provider_id,
                descriptor.environment,
            )
            with commerce_request_context(
                source="ui_place_order",
                permissions={CommercePermission.READ, CommercePermission.CHECKOUT},
                operation_id=operation_id,
            ):
                outcome = await adapter.place_order(
                    draft_row_to_review(pending_row) or refreshed
                )
            outcome["checkout_attempt_id"] = checkout_attempt_id
            final_review = save_order_outcome(pending_row, outcome)
            return {
                "status": outcome.get("status", "error"),
                "provider": provider_id,
                "result": outcome,
                "review": final_review,
            }
        finally:
            release_provider_checkout_operation(
                operation_id,
                provider_id,
                descriptor.environment,
            )

    async def payment_status(self, provider_id: str) -> Dict[str, Any]:
        adapter = self.registry.get(provider_id)
        environment = adapter.descriptor().environment
        row = get_provider_checkout_draft(provider_id, environment)
        if not row:
            raise ProviderOperationError(
                provider=provider_id,
                operation="payment_status",
                code="checkout_draft_missing",
                message="No provider checkout draft exists.",
                status_code=404,
            )
        outcome = await adapter.payment_status(draft_row_to_review(row) or {})
        self._raise_result_error(provider_id, "payment_status", outcome)
        return {
            "status": outcome.get("status", "success"),
            "provider": provider_id,
            "review": save_order_outcome(row, outcome),
        }

    async def sync_from_chat(
        self,
        *,
        provider_id: str = "",
        cart_item_ids: List[str] | None = None,
        selected_address_id: str = "",
        user_instruction: str = "",
        native_cart_changes: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Synchronize an explicitly requested or UI-selected provider cart."""
        provider_id = ProviderRegistry.canonical_id(provider_id)
        if not provider_id:
            provider_id = ProviderRegistry.canonical_id(
                get_selected_grocery_provider()
            )
        if provider_id not in {"zepto", "swiggy_instamart"}:
            raise ProviderOperationError(
                provider=provider_id or "unselected", operation="chat_sync_cart",
                code="provider_selection_required",
                message="Select and connect an ordering app in Groceries before synchronizing from chat.",
                status_code=422,
            )
        adapter = self.registry.get(provider_id)
        environment = adapter.descriptor().environment
        address_id = str(selected_address_id or "").strip()
        if not address_id:
            existing = get_provider_checkout_draft(provider_id, environment)
            address_id = str((existing or {}).get("selected_address_id") or "").strip()
        used_default = False
        if not address_id:
            try:
                address_result = await adapter.list_addresses()
            except ProviderOperationError:
                if not native_cart_changes:
                    raise
                address_result = {"addresses": []}
            addresses = list(address_result.get("addresses") or [])
            selected = next(
                (address for address in addresses if address.get("is_default")),
                addresses[0] if addresses else None,
            )
            if not selected and not native_cart_changes:
                raise ProviderOperationError(
                    provider=provider_id,
                    operation="chat_sync_cart",
                    code="provider_address_required",
                    message=f"Connect {adapter.descriptor().label} and add a saved delivery address before moving the cart from chat.",
                    status_code=422,
                )
            if selected:
                address_id = str(selected.get("id") or "")
                used_default = True
        result = await self.sync(
            provider_id,
            {
                "cart_item_ids": cart_item_ids or [],
                "selected_address_id": address_id,
                "user_instruction": user_instruction,
                "native_cart_changes": native_cart_changes or [],
            },
            authority_source="chat_sync",
        )
        result["address_selection"] = "provider_default" if used_default else "last_selected"
        return result

    async def _revalidate_provider(
        self,
        provider_id: str,
        adapter: Any,
        review: Dict[str, Any],
        *,
        operation_id: str,
        source: str,
    ) -> Dict[str, Any]:
        del provider_id
        with commerce_request_context(
            source=source,
            permissions={CommercePermission.READ, CommercePermission.CART_WRITE},
            operation_id=operation_id,
        ):
            refreshed = await adapter.revalidate_cart(review)
        return self._annotate_revalidation_changes(review, refreshed)

    @staticmethod
    def _annotate_revalidation_changes(
        previous_review: Dict[str, Any],
        refreshed: Dict[str, Any],
    ) -> Dict[str, Any]:
        previous = list(previous_review.get("matched_items") or [])
        current = list(refreshed.get("items") or [])
        previous_by_native = {
            str((item.get("native_item") or {}).get("id")): item
            for item in previous
        }
        replacements: List[Dict[str, Any]] = list(
            refreshed.get("replacements") or []
        )
        changes: List[Dict[str, Any]] = list(refreshed.get("changes") or [])
        for match in current:
            native_id = str((match.get("native_item") or {}).get("id"))
            old = previous_by_native.get(native_id)
            if not old:
                changes.append({"type": "added", "native_item": match.get("native_item")})
                continue
            old_product = old.get("matched_product") or {}
            new_product = match.get("matched_product") or {}
            old_id = old_product.get("candidate_id")
            new_id = new_product.get("candidate_id")
            if old_id != new_id:
                replacements.append({
                    "native_item": match.get("native_item"),
                    "previous_product": old_product,
                    "replacement_product": new_product,
                })
                continue
            old_cart = old.get("cart_item") or {}
            new_cart = match.get("cart_item") or {}
            changed_fields = [
                key
                for key in ("price_minor", "line_total_minor", "pack_size", "quantity", "store_id")
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
        if (previous_review.get("cart_summary") or {}) != (refreshed.get("cart_summary") or {}):
            changes.append({"type": "bill_changed"})
        if (previous_review.get("payment_options") or []) != (refreshed.get("payment_options") or []):
            changes.append({"type": "payment_methods_changed"})
        previous_unavailable = sorted(
            (str(item.get("name") or ""), str(item.get("reason") or ""))
            for item in previous_review.get("unavailable_items") or []
        )
        current_unavailable = sorted(
            (str(item.get("name") or ""), str(item.get("reason") or ""))
            for item in refreshed.get("unavailable_items") or []
        )
        if previous_unavailable != current_unavailable:
            changes.append({"type": "unavailable_items_changed"})
        refreshed["replacements"] = replacements
        refreshed["changes"] = changes
        refreshed["changed"] = bool(replacements or changes)
        return refreshed

    def _claim(self, provider: str, environment: str, operation_id: str) -> None:
        if not claim_provider_checkout_operation(
            operation_id,
            provider,
            environment,
            lease_seconds=CHECKOUT_OPERATION_LEASE_SECONDS,
        ):
            raise ProviderOperationError(
                provider=provider,
                operation="checkout_lease",
                code="provider_checkout_busy",
                message="Another checkout operation is already running for this provider.",
                retryable=True,
                status_code=409,
            )

    @staticmethod
    def _raise_result_error(
        provider: str,
        operation: str,
        result: Dict[str, Any],
    ) -> None:
        if result.get("status") != "error":
            return
        code = str(result.get("code") or "provider_operation_failed")
        raise ProviderOperationError(
            provider=provider,
            operation=operation,
            code=code,
            message=str(result.get("message") or "The ordering provider operation failed."),
            retryable=code not in {
                "address_required",
                "cart_empty",
                "payment_method_required",
                "provider_contract_incompatible",
            },
            status_code=401 if code == "provider_auth_required" else 502,
        )
