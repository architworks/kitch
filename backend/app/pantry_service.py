"""Application services for independent pantry changes and explicit cart reconciliation."""

from __future__ import annotations

import json
import math
from typing import Any
from uuid import uuid4

from google.genai.types import Content, Part

from app.agent.structured_models import PantryReconciliation
from app.household_config import get_household_profile_id
from app.supabase_client import (
    apply_pantry_inventory_change,
    apply_pantry_cart_reconciliation,
    get_grocery_cart,
    get_pantry_state,
)


class PantryReconciliationError(RuntimeError):
    pass


def _propose_inventory(
    current: list[dict[str, Any]], mode: str, operations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if mode == "replace":
        proposed = [
            {"id": item.get("id"), "name": str(item.get("name") or "").strip(),
             "amount": float(item.get("amount") or 0), "unit": str(item.get("unit") or "piece")}
            for item in operations if str(item.get("name") or "").strip() and float(item.get("amount") or 0) > 0
        ]
        names = [item["name"].casefold() for item in proposed]
        if len(names) != len(set(names)):
            raise PantryReconciliationError("A full pantry replacement cannot contain duplicate item names")
        return proposed
    inventory = [dict(item) for item in current]
    for operation in operations:
        action = str(operation.get("action") or "").lower()
        target = next((item for item in inventory if (
            operation.get("id") is not None and str(item.get("id")) == str(operation.get("id"))
        ) or (
            operation.get("id") is None and str(item.get("name") or "").casefold() == str(operation.get("name") or "").casefold()
        )), None)
        if action == "add":
            if target:
                target["amount"] = float(target.get("amount") or 0) + float(operation.get("amount") or 0)
            else:
                inventory.append({"name": operation.get("name"), "amount": float(operation.get("amount") or 0), "unit": operation.get("unit") or "piece"})
        elif action == "set":
            if target:
                target.update({"name": operation.get("name") or target.get("name"), "amount": float(operation.get("amount") or 0), "unit": operation.get("unit") or target.get("unit")})
            elif operation.get("id") is None and str(operation.get("name") or "").strip():
                inventory.append({"name": str(operation["name"]).strip(), "amount": float(operation.get("amount") or 0), "unit": operation.get("unit") or "piece"})
            else:
                raise PantryReconciliationError("Pantry set referenced an item that no longer exists")
        elif action == "adjust" and target:
            target["amount"] = max(0, float(target.get("amount") or 0) + float(operation.get("amount") or 0))
        elif action in {"remove", "delete"} and target:
            inventory.remove(target)
        elif action in {"adjust", "remove", "delete"}:
            raise PantryReconciliationError("Pantry operation referenced an item that no longer exists")
        elif action not in {"add", "set", "adjust", "remove", "delete"}:
            raise PantryReconciliationError(f"Unsupported pantry action: {action or '(missing)'}")
    return [item for item in inventory if float(item.get("amount") or 0) > 0]


async def _reconcile_with_agent(
    proposed_pantry: list[dict[str, Any]], cart: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not cart:
        return []
    from app.agent.core import pantry_reconciliation_runner

    session_id = f"pantry-reconciliation-{uuid4()}"
    prompt = (
        "Reconcile the proposed pantry against every native grocery row. Understand semantic "
        "units and partial coverage. Return exactly one allocation for each cart row ID. "
        "purchase_amount is the nonnegative amount still required for purchase; preserve the "
        "cart's purchase unit when conversion is uncertain. Each pantry_allocation must state its "
        "total allocated amount/unit and source pantry item names, IDs when present, quantities, "
        "and units. Never invent or omit IDs.\n"
        f"PROPOSED PANTRY:\n{json.dumps(proposed_pantry, ensure_ascii=False)}\n"
        f"NATIVE CART:\n{json.dumps(cart, ensure_ascii=False)}"
    )
    text = ""
    async for event in pantry_reconciliation_runner.run_async(
        user_id=get_household_profile_id(), session_id=session_id,
        new_message=Content(parts=[Part(text=prompt)], role="user"),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text or ""
    try:
        result = PantryReconciliation.model_validate_json(text)
    except Exception as error:
        raise PantryReconciliationError("Pantry reconciliation returned invalid structured data") from error
    expected_ids = {int(item["id"]) for item in cart}
    actual_ids = {allocation.id for allocation in result.allocations}
    if actual_ids != expected_ids or len(result.allocations) != len(expected_ids):
        raise PantryReconciliationError("Pantry reconciliation did not cover the exact native cart")
    if any(not math.isfinite(allocation.purchase_amount) for allocation in result.allocations):
        raise PantryReconciliationError("Pantry reconciliation returned a non-finite quantity")
    proposed_ids = {int(item["id"]) for item in proposed_pantry if item.get("id") is not None}
    proposed_names = {str(item.get("name") or "").casefold() for item in proposed_pantry}
    for allocation in result.allocations:
        detail = allocation.pantry_allocation
        if not math.isfinite(detail.allocated_amount):
            raise PantryReconciliationError("Pantry reconciliation returned a non-finite allocation")
        for source in detail.sources:
            if not math.isfinite(source.amount):
                raise PantryReconciliationError("Pantry reconciliation returned a non-finite source quantity")
            if source.pantry_item_id is not None and source.pantry_item_id not in proposed_ids:
                raise PantryReconciliationError("Pantry reconciliation invented a pantry item ID")
            if source.pantry_item_name.casefold() not in proposed_names:
                raise PantryReconciliationError("Pantry reconciliation invented a pantry item name")
    cart_by_id = {int(item["id"]): item for item in cart}
    return [
        {
            **allocation.model_dump(),
            "pantry_allocation": allocation.pantry_allocation.model_dump(),
            "required_name": str(cart_by_id[allocation.id].get("name") or ""),
            "required_amount": float(cart_by_id[allocation.id].get("amount") or 0),
            "required_unit": str(cart_by_id[allocation.id].get("unit") or "piece"),
        }
        for allocation in result.allocations
    ]


async def mutate_pantry(
    *, expected_revision: int, mode: str, items: list[dict[str, Any]]
) -> dict[str, Any]:
    state = get_pantry_state()
    if int(expected_revision) != int(state["revision"]):
        raise PantryReconciliationError("Pantry revision conflict; refresh and try again")
    _propose_inventory(state["items"], mode, items)
    return apply_pantry_inventory_change(
        expected_revision=expected_revision, mode=mode, items=items,
    )


async def reconcile_native_cart_with_pantry(*, expected_revision: int) -> dict[str, Any]:
    """Explicitly recalculate native purchase intent from the current pantry."""
    state = get_pantry_state()
    if int(expected_revision) != int(state["revision"]):
        raise PantryReconciliationError("Pantry revision conflict; refresh and try again")
    cart = get_grocery_cart()
    allocations = await _reconcile_with_agent(state["items"], cart)
    return apply_pantry_cart_reconciliation(
        expected_revision=expected_revision,
        cart_reconciliation=allocations,
    )
