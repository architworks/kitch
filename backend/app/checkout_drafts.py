"""Durable checkout-review construction and native-cart drift checks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from app.supabase_client import save_provider_checkout_draft


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(child) for key, child in value.items()}
        if isinstance(value, list):
            return [_json_safe(child) for child in value]
        return str(value)


def checkout_snapshot_hash(review: Dict[str, Any]) -> str:
    normalized_matches = []
    for match in review.get("matched_items", []) or []:
        native_item = match.get("native_item") or {}
        product = match.get("matched_product") or {}
        cart_item = match.get("cart_item") or {}
        normalized_matches.append(
            {
                "native_item_id": str(native_item.get("id") or ""),
                "native_item_name": native_item.get("name"),
                "product_variant_id": product.get("productVariantId")
                or product.get("variantId")
                or product.get("spinId")
                or product.get("spin_id")
                or cart_item.get("productVariantId")
                or cart_item.get("variantId")
                or cart_item.get("spinId")
                or cart_item.get("spin_id"),
                "store_product_id": product.get("storeProductId")
                or product.get("skuId")
                or product.get("sku_id")
                or cart_item.get("storeProductId")
                or cart_item.get("skuId")
                or cart_item.get("sku_id"),
                "product_name": product.get("name") or product.get("title")
                or cart_item.get("name"),
                "price_minor": product.get(
                    "price_minor",
                    product.get("price", cart_item.get("price_minor", cart_item.get("price"))),
                ),
                "pack_size": product.get(
                    "pack_size",
                    product.get("packSize", cart_item.get("pack_size", cart_item.get("packSize"))),
                ),
                "quantity": cart_item.get("quantity"),
                "provider_store_id": cart_item.get("store_id") or cart_item.get("storeId"),
            }
        )
    stable_payload = {
        "native_items": review.get("native_items", []),
        "mapped_items": review.get("mapped_items", []),
        "matched_items": normalized_matches,
        "unavailable_items": review.get("unavailable_items", []),
        "replacements": review.get("replacements", []),
        "cart_summary": review.get("cart_summary"),
        "selected_address_id": review.get("selected_address_id"),
        "selected_payment_method_id": review.get("selected_payment_method_id"),
        "selected_payment_method": review.get("selected_payment_method"),
        "provider": review.get("provider"),
        "provider_environment": review.get("provider_environment"),
    }
    encoded = json.dumps(
        _json_safe(stable_payload),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def draft_row_to_review(row: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not row:
        return None
    return {
        "review_id": str(row.get("id") or ""),
        "provider": row.get("provider") or "",
        "provider_environment": row.get("provider_environment") or "production",
        "capability_version": row.get("capability_version") or "",
        "status": row.get("status") or "draft",
        "selected_native_item_ids": row.get("selected_native_item_ids") or [],
        "native_items": row.get("native_items") or [],
        "mapped_items": row.get("mapped_items") or [],
        "matched_items": row.get("matched_items") or [],
        "unavailable_items": row.get("unavailable_items") or [],
        "replacements": row.get("replacements") or [],
        "changes": row.get("changes") or [],
        "provider_cart": row.get("provider_cart"),
        "cart_summary": row.get("cart_summary") or {},
        "checkout_context": row.get("checkout_context") or {},
        "store_context": row.get("store_context") or {},
        "selected_address_id": row.get("selected_address_id") or "",
        "selected_payment_method_id": row.get("selected_payment_method_id"),
        "selected_payment_method": row.get("selected_payment_method"),
        "payment_options": row.get("payment_options") or [],
        "payment_state": row.get("payment_state") or {},
        "order_review_acknowledged": bool(row.get("order_review_acknowledged")),
        "can_place_order": bool(row.get("can_place_order")),
        "order_blockers": row.get("order_blockers") or [],
        "confirmation_token": row.get("confirmation_token"),
        "snapshot_hash": row.get("snapshot_hash") or "",
        "checkout_attempt_id": row.get("checkout_attempt_id"),
        "provider_order_ids": row.get("provider_order_ids") or [],
        "order_results": row.get("order_results") or [],
        "ambiguous_order": bool(row.get("ambiguous_order")),
        "last_validated_at": row.get("last_validated_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _order_blockers(
    native_items: List[Dict[str, Any]],
    result: Dict[str, Any],
    provider_label: str,
) -> List[str]:
    matched_items = result.get("items") or []
    unavailable_items = result.get("unavailable_items") or []
    checkout_context = result.get("checkout_context") or {}
    blockers: List[str] = []
    if result.get("status") != "success":
        blockers.append(f"{provider_label} did not confirm every selected cart item as orderable.")
    if len(matched_items) != len(native_items) or unavailable_items:
        blockers.append(f"Every selected native item must have a confirmed orderable {provider_label} product.")
    if checkout_context.get("address_error"):
        blockers.append(f"{provider_label} address options could not be read.")
    if checkout_context.get("payment_error"):
        blockers.append(f"{provider_label} payment options could not be read.")
    if (result.get("store_context") or {}).get("status") != "ready":
        blockers.append(f"{provider_label} store context is not ready for the selected address.")
    if (result.get("cart_summary") or {}).get("total_minor") is None:
        blockers.append(f"{provider_label} did not return an authoritative payable total.")
    if not (result.get("payment_options") or checkout_context.get("payment_methods") or []):
        blockers.append(f"{provider_label} did not return a supported payment method.")
    return list(dict.fromkeys(blockers))


def save_initial_draft(
    native_items: List[Dict[str, Any]],
    mapped_items: List[Dict[str, Any]],
    result: Dict[str, Any],
    selected_address_id: str,
    provider: str,
    provider_environment: str,
    provider_label: str,
) -> Dict[str, Any]:
    blockers = _order_blockers(native_items, result, provider_label)
    payload: Dict[str, Any] = {
        "selected_address_id": selected_address_id,
        "selected_native_item_ids": [str(item.get("id")) for item in native_items if item.get("id") is not None],
        "native_items": native_items,
        "mapped_items": mapped_items,
        "matched_items": result.get("items") or [],
        "unavailable_items": result.get("unavailable_items") or [],
        "replacements": result.get("replacements") or [],
        "changes": result.get("changes") or [],
        "capability_version": result.get("capability_version") or "",
        "provider_cart": result.get("provider_cart"),
        "cart_summary": result.get("cart_summary") or {},
        "checkout_context": result.get("checkout_context") or {},
        "store_context": result.get("store_context") or {},
        "payment_options": result.get("payment_options") or (result.get("checkout_context") or {}).get("payment_methods") or [],
        "selected_payment_method_id": None,
        "selected_payment_method": None,
        "payment_state": {},
        "order_review_acknowledged": False,
        "can_place_order": not blockers,
        "order_blockers": blockers,
        "confirmation_token": f"kitch_confirm_{uuid4()}" if not blockers else None,
        "status": "ready" if not blockers else "blocked",
        "last_validated_at": _now_iso(),
    }
    payload["snapshot_hash"] = checkout_snapshot_hash(payload)
    return draft_row_to_review(save_provider_checkout_draft(
        payload,
        provider=provider,
        provider_environment=provider_environment,
    )) or {}


def save_revalidated_draft(
    existing_row: Dict[str, Any],
    result: Dict[str, Any],
) -> tuple[Dict[str, Any], bool]:
    existing = draft_row_to_review(existing_row) or {}
    native_items = existing.get("native_items") or []
    provider = str(existing_row.get("provider") or "")
    provider_environment = str(existing_row.get("provider_environment") or "production")
    provider_label = str(result.get("provider_label") or provider.replace("_", " ").title())
    blockers = _order_blockers(native_items, result, provider_label)
    changed = bool(result.get("changed"))
    replacements = (
        result.get("replacements") or []
        if changed
        else existing.get("replacements") or []
    )
    changes = (
        result.get("changes") or []
        if changed
        else existing.get("changes") or []
    )
    payload: Dict[str, Any] = {
        "selected_address_id": existing.get("selected_address_id") or "",
        "selected_native_item_ids": existing.get("selected_native_item_ids") or [],
        "native_items": native_items,
        "mapped_items": existing.get("mapped_items") or [],
        "matched_items": result.get("items") or [],
        "unavailable_items": result.get("unavailable_items") or [],
        "replacements": replacements,
        "changes": changes,
        "capability_version": result.get("capability_version") or existing.get("capability_version") or "",
        "provider_cart": result.get("provider_cart"),
        "cart_summary": result.get("cart_summary") or {},
        "checkout_context": result.get("checkout_context") or {},
        "store_context": result.get("store_context") or {},
        "payment_options": result.get("payment_options") or (result.get("checkout_context") or {}).get("payment_methods") or [],
        "selected_payment_method_id": None if changed else existing.get("selected_payment_method_id"),
        "selected_payment_method": None if changed else existing.get("selected_payment_method"),
        "payment_state": {} if changed else existing.get("payment_state") or {},
        "order_review_acknowledged": False if changed else bool(existing.get("order_review_acknowledged")),
        "can_place_order": not blockers,
        "order_blockers": blockers,
        "confirmation_token": (
            f"kitch_confirm_{uuid4()}"
            if not blockers and changed
            else existing.get("confirmation_token") if not blockers else None
        ),
        "status": "changed" if changed and not blockers else "ready" if not blockers else "blocked",
        "last_validated_at": _now_iso(),
    }
    payload["snapshot_hash"] = checkout_snapshot_hash(payload)
    return draft_row_to_review(save_provider_checkout_draft(
        payload,
        provider=provider,
        provider_environment=provider_environment,
    )) or {}, changed


def update_draft_review_fields(
    existing_row: Dict[str, Any],
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    existing = draft_row_to_review(existing_row) or {}
    payload = {
        "selected_payment_method_id": (
            updates.get("selected_payment_method_id")
            if "selected_payment_method_id" in updates
            else existing.get("selected_payment_method_id")
        ),
        "selected_payment_method": (
            updates.get("selected_payment_method")
            if "selected_payment_method" in updates
            else existing.get("selected_payment_method")
        ),
        "order_review_acknowledged": (
            bool(updates.get("order_review_acknowledged"))
            if "order_review_acknowledged" in updates
            else bool(existing.get("order_review_acknowledged"))
        ),
    }
    hash_payload = {**existing, **payload}
    payload["snapshot_hash"] = checkout_snapshot_hash(hash_payload)
    return draft_row_to_review(save_provider_checkout_draft(
        payload,
        provider=str(existing_row.get("provider") or ""),
        provider_environment=str(existing_row.get("provider_environment") or "production"),
    )) or {}


def invalidate_draft_for_native_drift(
    existing_row: Dict[str, Any],
) -> Dict[str, Any]:
    existing = draft_row_to_review(existing_row) or {}
    blockers = list(existing.get("order_blockers") or [])
    provider_label = str(existing.get("provider") or "provider").replace("_", " ").title()
    blockers.append(f"The native grocery selection changed after the {provider_label} cart was reviewed.")
    payload = {
        "selected_payment_method_id": None,
        "order_review_acknowledged": False,
        "can_place_order": False,
        "order_blockers": list(dict.fromkeys(blockers)),
        "confirmation_token": None,
        "status": "blocked",
    }
    payload["snapshot_hash"] = checkout_snapshot_hash({**existing, **payload})
    return draft_row_to_review(save_provider_checkout_draft(
        payload,
        provider=str(existing_row.get("provider") or ""),
        provider_environment=str(existing_row.get("provider_environment") or "production"),
    )) or {}


def native_snapshot_matches(
    existing_row: Dict[str, Any],
    current_cart: List[Dict[str, Any]],
) -> bool:
    existing = draft_row_to_review(existing_row) or {}
    selected_ids = {str(item_id) for item_id in existing.get("selected_native_item_ids") or []}
    current_selected = [
        item
        for item in current_cart
        if str(item.get("id")) in selected_ids and not item.get("alreadyStocked")
    ]

    def stable(items: List[Dict[str, Any]]) -> str:
        normalized = [
            {
                "id": str(item.get("id")),
                "name": item.get("name"),
                "amount": item.get("amount"),
                "unit": item.get("unit"),
                "category": item.get("category"),
                "alreadyStocked": bool(item.get("alreadyStocked")),
            }
            for item in items
        ]
        return json.dumps(sorted(normalized, key=lambda item: item["id"]), sort_keys=True, default=str)

    return len(current_selected) == len(selected_ids) and stable(current_selected) == stable(existing.get("native_items") or [])


def save_order_outcome(
    existing_row: Dict[str, Any],
    outcome: Dict[str, Any],
) -> Dict[str, Any]:
    existing = draft_row_to_review(existing_row) or {}
    outcome_status = str(outcome.get("status") or "unknown")
    status = {
        "success": "ordered",
        "payment_pending": "payment_pending",
        "unknown": "unknown",
    }.get(outcome_status, "blocked")
    payload = {
        "status": status,
        "checkout_attempt_id": outcome.get("checkout_attempt_id") or existing.get("checkout_attempt_id"),
        "provider_order_ids": outcome.get("provider_order_ids") or existing.get("provider_order_ids") or [],
        "order_results": outcome.get("order_results") or existing.get("order_results") or [],
        "payment_state": outcome.get("payment_state") or existing.get("payment_state") or {},
        "ambiguous_order": bool(outcome.get("ambiguous_order")),
        "can_place_order": False,
        "order_review_acknowledged": False,
        "confirmation_token": None,
    }
    if status == "blocked":
        payload["order_blockers"] = list(dict.fromkeys([
            *(existing.get("order_blockers") or []),
            str(outcome.get("message") or "The provider did not confirm the order."),
        ]))
    payload["snapshot_hash"] = checkout_snapshot_hash({**existing, **payload})
    return draft_row_to_review(save_provider_checkout_draft(
        payload,
        provider=str(existing_row.get("provider") or ""),
        provider_environment=str(existing_row.get("provider_environment") or "production"),
    )) or {}
