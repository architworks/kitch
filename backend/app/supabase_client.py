"""Supabase access for Kitch's durable structured state.

Every provider failure is converted to a typed PersistenceError. Empty query
results remain valid, but writes must return provider-confirmed rows.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List
from uuid import uuid4

from dotenv import load_dotenv
from supabase import Client, create_client

from app.household_config import (
    DEFAULT_HOUSEHOLD_SIZE,
    HOUSEHOLD_NAME,
    canonical_user_name,
    get_household_profile_id,
    get_user_id,
)
from app.persistence import (
    PersistenceConfigurationError,
    PersistenceError,
    malformed_persistence_response,
    persistence_error_from_exception,
    resolve_supabase_credentials,
)


load_dotenv()

SUPABASE_URL, _SUPABASE_ELEVATED_KEY, SUPABASE_KEY_TYPE = (
    resolve_supabase_credentials(os.environ)
)
supabase: Client = create_client(SUPABASE_URL, _SUPABASE_ELEVATED_KEY)

REQUIRED_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "profiles": (
        "id",
        "full_name",
        "diet_preference",
        "household_size",
        "daily_calorie_target",
        "created_at",
    ),
    "meal_plans": (
        "id",
        "profile_id",
        "day",
        "breakfast_recipe_id",
        "lunch_recipe_id",
        "dinner_recipe_id",
        "snack_recipe_id",
        "updated_at",
    ),
    "pantry_stock": (
        "id",
        "profile_id",
        "ingredient_name",
        "amount",
        "unit",
        "updated_at",
    ),
    "recipe_grocery_plans": (
        "id",
        "profile_id",
        "scope",
        "request_text",
        "recipe_cards",
        "ingredients",
        "pantry_considerations",
        "household_size",
        "notes",
        "source",
        "updates_cart",
        "cart_item_count",
        "created_at",
        "updated_at",
    ),
    "grocery_cart_items": (
        "id",
        "profile_id",
        "recipe_grocery_plan_id",
        "ingredient_name",
        "amount",
        "unit",
        "category",
        "source",
        "checked",
        "already_stocked",
        "stock_note",
        "created_at",
        "updated_at",
    ),
    "macro_diary": (
        "id",
        "profile_id",
        "meal_name",
        "calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "fiber_g",
        "logged_at",
    ),
    "provider_checkout_drafts": (
        "id",
        "profile_id",
        "provider",
        "selected_address_id",
        "selected_native_item_ids",
        "native_items",
        "mapped_items",
        "matched_items",
        "unavailable_items",
        "replacements",
        "changes",
        "provider_cart",
        "cart_summary",
        "checkout_context",
        "store_context",
        "selected_payment_method_id",
        "order_review_acknowledged",
        "can_place_order",
        "order_blockers",
        "confirmation_token",
        "snapshot_hash",
        "status",
        "last_validated_at",
        "operation_id",
        "lease_expires_at",
        "created_at",
        "updated_at",
    ),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _execute(operation: str, table: str, query: Callable[[], Any]) -> Any:
    try:
        response = query()
    except PersistenceError:
        raise
    except Exception as error:
        raise persistence_error_from_exception(operation, table, error) from error
    if response is None or not hasattr(response, "data"):
        raise malformed_persistence_response(operation, table)
    return response.data


def _read_rows(operation: str, table: str, query: Callable[[], Any]) -> list[dict[str, Any]]:
    data = _execute(operation, table, query)
    if not isinstance(data, list):
        raise malformed_persistence_response(operation, table)
    return data


def _confirmed_row(
    operation: str,
    table: str,
    query: Callable[[], Any],
) -> dict[str, Any]:
    rows = _read_rows(operation, table, query)
    if not rows or not isinstance(rows[0], dict):
        raise malformed_persistence_response(operation, table)
    return rows[0]


def _coerce_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "checked",
            "stocked",
        }
    return bool(value)


def _normalize_grocery_item(item: Dict[str, Any]) -> Dict[str, Any] | None:
    name = str(
        item.get("name")
        or item.get("ingredient_name")
        or item.get("item")
        or ""
    ).strip()
    if not name:
        return None
    try:
        amount = float(
            item.get("amount", item.get("quantity", item.get("qty", 1))) or 1
        )
    except (TypeError, ValueError):
        amount = 1
    source = str(item.get("source") or "agent").strip().lower() or "agent"
    if source not in {"agent", "manual"}:
        source = "agent"
    return {
        "id": item.get("id"),
        "name": name,
        "amount": amount,
        "unit": str(item.get("unit") or "piece").strip() or "piece",
        "category": str(
            item.get("category") or item.get("section") or "General"
        ).strip()
        or "General",
        "source": source,
        "checked": _coerce_bool(item.get("checked", False)),
        "alreadyStocked": _coerce_bool(
            item.get("alreadyStocked", item.get("already_stocked", False))
        ),
        "stockNote": str(
            item.get("stockNote") or item.get("stock_note") or ""
        ).strip(),
        "recipeGroceryPlanId": (
            item.get("recipeGroceryPlanId")
            or item.get("recipe_grocery_plan_id")
        ),
    }


def _grocery_rows_to_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for row in rows:
        item = _normalize_grocery_item(row)
        if item:
            mapped.append(item)
    return mapped


def _grocery_item_to_row(
    item: Dict[str, Any],
    profile_id: str | None = None,
    recipe_grocery_plan_id: str | None = None,
) -> Dict[str, Any]:
    row = {
        "ingredient_name": item["name"],
        "amount": item["amount"],
        "unit": item["unit"],
        "category": item["category"],
        "source": item["source"],
        "checked": item["checked"],
        "already_stocked": item["alreadyStocked"],
        "stock_note": item["stockNote"],
    }
    if profile_id:
        row["profile_id"] = profile_id
    plan_id = (
        item.get("recipeGroceryPlanId")
        or item.get("recipe_grocery_plan_id")
        or recipe_grocery_plan_id
    )
    if plan_id:
        row["recipe_grocery_plan_id"] = plan_id
    return row


def _recipe_card_ingredients(recipe_cards: List[Dict[str, Any]]) -> List[Any]:
    ingredients: list[Any] = []
    for card in recipe_cards:
        if isinstance(card, dict):
            card_ingredients = (
                card.get("ingredients")
                or card.get("ingredientList")
                or card.get("ingredient_list")
                or []
            )
            if isinstance(card_ingredients, list):
                ingredients.extend(card_ingredients)
    return ingredients


def _normalize_recipe_grocery_plan(
    plan: Dict[str, Any],
    cart_items: List[Dict[str, Any]] | None = None,
    update_cart: bool = False,
) -> Dict[str, Any] | None:
    if not isinstance(plan, dict):
        return None
    scope = _coerce_json(plan.get("scope") or plan.get("scope_metadata") or {}, {})
    if not isinstance(scope, dict):
        scope = {"label": str(scope)}
    raw_cards = (
        plan.get("recipeCards")
        or plan.get("recipe_cards")
        or plan.get("recipes")
        or plan.get("recipe")
        or []
    )
    if isinstance(raw_cards, dict):
        raw_cards = [raw_cards]
    if not isinstance(raw_cards, list):
        raw_cards = []
    recipe_cards = [
        card if isinstance(card, dict) else {"title": str(card).strip()}
        for card in raw_cards
        if isinstance(card, dict) or str(card).strip()
    ]
    ingredients = (
        plan.get("ingredients")
        or plan.get("ingredientList")
        or plan.get("ingredient_list")
        or _recipe_card_ingredients(recipe_cards)
    )
    if isinstance(ingredients, dict):
        ingredients = [ingredients]
    if not isinstance(ingredients, list):
        ingredients = []
    pantry_considerations = (
        plan.get("pantryConsiderations")
        or plan.get("pantry_considerations")
        or plan.get("pantryNotes")
        or plan.get("pantry_notes")
        or []
    )
    if isinstance(pantry_considerations, str):
        pantry_considerations = [pantry_considerations]
    if not isinstance(pantry_considerations, list):
        pantry_considerations = []
    try:
        household_size = int(
            plan.get("householdSize")
            or plan.get("household_size")
            or DEFAULT_HOUSEHOLD_SIZE
        )
    except (TypeError, ValueError):
        household_size = DEFAULT_HOUSEHOLD_SIZE
    source = str(plan.get("source") or "agent").strip().lower()
    if source not in {"agent", "manual"}:
        source = "agent"
    created_at = plan.get("createdAt") or plan.get("created_at") or _now_iso()
    updated_at = plan.get("updatedAt") or plan.get("updated_at") or created_at
    return {
        "id": str(plan.get("id") or uuid4()),
        "scope": scope,
        "scopeLabel": str(
            plan.get("scopeLabel")
            or plan.get("scope_label")
            or scope.get("label")
            or scope.get("type")
            or "Recipe + grocery plan"
        ),
        "request": str(
            plan.get("request")
            or plan.get("requestText")
            or plan.get("request_text")
            or ""
        ).strip(),
        "recipeCards": recipe_cards,
        "ingredients": ingredients,
        "pantryConsiderations": pantry_considerations,
        "householdSize": max(1, household_size),
        "notes": str(plan.get("notes") or plan.get("instructions") or "").strip(),
        "source": source,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "updatesCart": bool(update_cart),
        "cartItemCount": len(cart_items or []) if update_cart else 0,
    }


def _recipe_rows_to_plans(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for row in rows:
        scope = _coerce_json(row.get("scope"), {})
        cards = _coerce_json(row.get("recipe_cards"), [])
        ingredients = _coerce_json(row.get("ingredients"), [])
        pantry = _coerce_json(row.get("pantry_considerations"), [])
        plan = {
            "id": str(row.get("id")),
            "scope": scope if isinstance(scope, dict) else {},
            "scopeLabel": (
                (scope or {}).get("label")
                if isinstance(scope, dict)
                else "Recipe + grocery plan"
            ),
            "request": row.get("request_text") or "",
            "recipeCards": cards if isinstance(cards, list) else [],
            "ingredients": ingredients if isinstance(ingredients, list) else [],
            "pantryConsiderations": pantry if isinstance(pantry, list) else [],
            "householdSize": row.get("household_size") or DEFAULT_HOUSEHOLD_SIZE,
            "notes": row.get("notes") or "",
            "source": row.get("source") or "agent",
            "updatesCart": bool(row.get("updates_cart", False)),
            "cartItemCount": row.get("cart_item_count", 0),
            "createdAt": row.get("created_at"),
            "updatedAt": row.get("updated_at"),
        }
        plan["recipeCount"] = len(plan["recipeCards"])
        plan["ingredientCount"] = len(plan["ingredients"])
        plans.append(plan)
    return plans


def _recipe_plan_metadata(
    plan: Dict[str, Any] | None,
) -> Dict[str, Any] | None:
    if not plan:
        return None
    return {
        "id": plan.get("id"),
        "scope": plan.get("scope") or {},
        "scopeLabel": plan.get("scopeLabel") or "Recipe + grocery plan",
        "request": plan.get("request") or "",
        "householdSize": plan.get("householdSize") or DEFAULT_HOUSEHOLD_SIZE,
        "recipeCount": len(plan.get("recipeCards") or []),
        "ingredientCount": len(plan.get("ingredients") or []),
        "updatesCart": bool(plan.get("updatesCart")),
        "cartItemCount": plan.get("cartItemCount", 0),
        "createdAt": plan.get("createdAt"),
        "updatedAt": plan.get("updatedAt"),
    }


# Profiles
def get_profile(user_name: str) -> Dict[str, Any]:
    profile_id = get_user_id(user_name)
    rows = _read_rows(
        "get_profile",
        "profiles",
        lambda: supabase.table("profiles")
        .select("*")
        .eq("id", profile_id)
        .limit(1)
        .execute(),
    )
    return rows[0] if rows else {}


def get_household_profile() -> Dict[str, Any]:
    rows = _read_rows(
        "get_household_profile",
        "profiles",
        lambda: supabase.table("profiles")
        .select("*")
        .eq("id", get_household_profile_id())
        .limit(1)
        .execute(),
    )
    if not rows:
        error = PersistenceError(
            operation="get_household_profile",
            table="profiles",
            supabase_code="household_profile_missing",
            retryable=False,
        )
        from app.persistence import record_persistence_failure

        record_persistence_failure(error)
        raise error
    return rows[0]


def update_profile(
    user_name: str,
    diet_preference: str,
    household_size: int,
    daily_calorie_target: int = 2000,
) -> Dict[str, Any]:
    user_name = canonical_user_name(user_name)
    return _confirmed_row(
        "update_profile",
        "profiles",
        lambda: supabase.table("profiles")
        .upsert(
            {
                "id": get_user_id(user_name),
                "full_name": user_name,
                "diet_preference": diet_preference,
                "household_size": household_size,
                "daily_calorie_target": daily_calorie_target,
            }
        )
        .execute(),
    )


def update_household_profile(
    diet_preference: str,
    household_size: int,
    daily_calorie_target: int = 2000,
) -> Dict[str, Any]:
    return _confirmed_row(
        "update_household_profile",
        "profiles",
        lambda: supabase.table("profiles")
        .upsert(
            {
                "id": get_household_profile_id(),
                "full_name": HOUSEHOLD_NAME,
                "diet_preference": diet_preference,
                "household_size": household_size,
                "daily_calorie_target": daily_calorie_target,
            }
        )
        .execute(),
    )


# Meal plans
def get_weekly_schedule(user_name: str | None = None) -> Dict[str, Dict[str, str]]:
    rows = _read_rows(
        "get_weekly_schedule",
        "meal_plans",
        lambda: supabase.table("meal_plans")
        .select("*")
        .eq("profile_id", get_household_profile_id())
        .execute(),
    )
    plan: dict[str, dict[str, str]] = {}
    for row in rows:
        day = str(row.get("day") or "").strip().capitalize()
        meals = {
            "breakfast": str(row.get("breakfast_recipe_id") or "").strip(),
            "lunch": str(row.get("lunch_recipe_id") or "").strip(),
            "dinner": str(row.get("dinner_recipe_id") or "").strip(),
        }
        if day and any(meals.values()):
            plan[day] = meals
    return plan


def save_weekly_plan(weekly_plan: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
    profile_id = get_household_profile_id()
    rows: list[dict[str, Any]] = []
    for day, meals in weekly_plan.items():
        if not isinstance(meals, dict):
            continue
        rows.append(
            {
                "profile_id": profile_id,
                "day": str(day).strip().capitalize(),
                "breakfast_recipe_id": str(meals.get("breakfast") or "").strip(),
                "lunch_recipe_id": str(meals.get("lunch") or "").strip(),
                "dinner_recipe_id": str(meals.get("dinner") or "").strip(),
                "snack_recipe_id": "",
            }
        )
    if not rows:
        return []
    saved = _read_rows(
        "save_weekly_plan",
        "meal_plans",
        lambda: supabase.table("meal_plans")
        .upsert(rows, on_conflict="profile_id,day")
        .execute(),
    )
    if len(saved) != len(rows):
        raise malformed_persistence_response("save_weekly_plan", "meal_plans")
    return saved


def update_single_meal(
    day: str,
    meal_category: str,
    new_recipe_name: str,
) -> Dict[str, Any]:
    category = meal_category.lower().strip()
    allowed = {
        "breakfast": "breakfast_recipe_id",
        "lunch": "lunch_recipe_id",
        "dinner": "dinner_recipe_id",
    }
    if category not in allowed:
        raise ValueError("meal_category must be breakfast, lunch, or dinner")
    day_clean = day.strip().capitalize()
    profile_id = get_household_profile_id()
    existing = _read_rows(
        "get_meal_plan_day",
        "meal_plans",
        lambda: supabase.table("meal_plans")
        .select("*")
        .eq("profile_id", profile_id)
        .eq("day", day_clean)
        .limit(1)
        .execute(),
    )
    row = existing[0] if existing else {}
    payload = {
        "profile_id": profile_id,
        "day": day_clean,
        "breakfast_recipe_id": row.get("breakfast_recipe_id") or "",
        "lunch_recipe_id": row.get("lunch_recipe_id") or "",
        "dinner_recipe_id": row.get("dinner_recipe_id") or "",
        "snack_recipe_id": row.get("snack_recipe_id") or "",
        allowed[category]: new_recipe_name.strip(),
    }
    return _confirmed_row(
        "update_single_meal",
        "meal_plans",
        lambda: supabase.table("meal_plans")
        .upsert(payload, on_conflict="profile_id,day")
        .execute(),
    )


# Pantry
def get_pantry_stock(user_name: str | None = None) -> List[Dict[str, Any]]:
    rows = _read_rows(
        "get_pantry_stock",
        "pantry_stock",
        lambda: supabase.table("pantry_stock")
        .select("*")
        .eq("profile_id", get_household_profile_id())
        .execute(),
    )
    return [
        {
            "id": row.get("id"),
            "name": row["ingredient_name"],
            "amount": float(row["amount"]),
            "unit": row["unit"],
        }
        for row in rows
    ]


def add_to_pantry(
    user_name: str | None,
    name: str,
    amount: float,
    unit: str = "piece",
) -> Dict[str, Any]:
    profile_id = get_household_profile_id()
    name_clean = name.strip()
    existing = next(
        (
            item
            for item in get_pantry_stock()
            if item["name"].lower() == name_clean.lower()
        ),
        None,
    )
    if existing:
        return _confirmed_row(
            "add_to_pantry",
            "pantry_stock",
            lambda: supabase.table("pantry_stock")
            .update(
                {
                    "amount": float(existing["amount"]) + float(amount),
                    "unit": unit,
                }
            )
            .eq("profile_id", profile_id)
            .eq("id", existing["id"])
            .execute(),
        )
    return _confirmed_row(
        "add_to_pantry",
        "pantry_stock",
        lambda: supabase.table("pantry_stock")
        .insert(
            {
                "profile_id": profile_id,
                "ingredient_name": name_clean,
                "amount": amount,
                "unit": unit,
            }
        )
        .execute(),
    )


def remove_from_pantry(user_name: str | None, name: str) -> bool:
    profile_id = get_household_profile_id()
    _execute(
        "remove_from_pantry",
        "pantry_stock",
        lambda: supabase.table("pantry_stock")
        .delete()
        .eq("profile_id", profile_id)
        .eq("ingredient_name", name)
        .execute(),
    )
    remaining = get_pantry_stock()
    return not any(item["name"] == name for item in remaining)


# Grocery cart
def get_grocery_cart(user_name: str | None = None) -> List[Dict[str, Any]]:
    rows = _read_rows(
        "get_grocery_cart",
        "grocery_cart_items",
        lambda: supabase.table("grocery_cart_items")
        .select("*")
        .eq("profile_id", get_household_profile_id())
        .order("category")
        .order("ingredient_name")
        .execute(),
    )
    return _grocery_rows_to_items(rows)


def replace_planned_grocery_cart(
    items: List[Dict[str, Any]],
    user_name: str | None = None,
    recipe_grocery_plan_id: str | None = None,
) -> List[Dict[str, Any]]:
    normalized = [
        item
        for item in (
            _normalize_grocery_item({**raw, "source": "agent"}) for raw in items
        )
        if item
    ]
    cart_rows = [_grocery_item_to_row(item) for item in normalized]
    data = _execute(
        "replace_planned_grocery_cart",
        "grocery_cart_items",
        lambda: supabase.rpc(
            "replace_planned_grocery_cart",
            {
                "p_profile_id": get_household_profile_id(),
                "p_cart_items": cart_rows,
                "p_recipe_grocery_plan_id": recipe_grocery_plan_id,
            },
        ).execute(),
    )
    if not isinstance(data, list):
        raise malformed_persistence_response(
            "replace_planned_grocery_cart", "grocery_cart_items"
        )
    return _grocery_rows_to_items(data)


def add_grocery_cart_item(
    item: Dict[str, Any],
    user_name: str | None = None,
) -> Dict[str, Any]:
    normalized = _normalize_grocery_item(
        {**item, "source": item.get("source") or "manual"}
    )
    if not normalized:
        raise ValueError("A grocery item name is required.")
    row = _confirmed_row(
        "add_grocery_cart_item",
        "grocery_cart_items",
        lambda: supabase.table("grocery_cart_items")
        .insert(
            _grocery_item_to_row(normalized, get_household_profile_id())
        )
        .execute(),
    )
    return _grocery_rows_to_items([row])[0]


def update_grocery_cart_item(
    item_id: str,
    updates: Dict[str, Any],
    user_name: str | None = None,
) -> Dict[str, Any]:
    field_map = {
        "name": "ingredient_name",
        "amount": "amount",
        "unit": "unit",
        "category": "category",
        "source": "source",
        "checked": "checked",
        "alreadyStocked": "already_stocked",
        "already_stocked": "already_stocked",
        "stockNote": "stock_note",
        "stock_note": "stock_note",
    }
    allowed_updates = {
        field_map[key]: value
        for key, value in updates.items()
        if key in field_map
    }
    if not allowed_updates:
        raise ValueError("No supported grocery item fields were provided.")
    row = _confirmed_row(
        "update_grocery_cart_item",
        "grocery_cart_items",
        lambda: supabase.table("grocery_cart_items")
        .update(allowed_updates)
        .eq("profile_id", get_household_profile_id())
        .eq("id", item_id)
        .execute(),
    )
    return _grocery_rows_to_items([row])[0]


def delete_grocery_cart_item(
    item_id: str,
    user_name: str | None = None,
) -> bool:
    _confirmed_row(
        "delete_grocery_cart_item",
        "grocery_cart_items",
        lambda: supabase.table("grocery_cart_items")
        .delete()
        .eq("profile_id", get_household_profile_id())
        .eq("id", item_id)
        .execute(),
    )
    return True


def clear_planned_grocery_cart(user_name: str | None = None) -> bool:
    profile_id = get_household_profile_id()
    replace_planned_grocery_cart([], user_name=user_name)
    return not any(
        item.get("source") == "agent" for item in get_grocery_cart(user_name)
    )


# Durable provider checkout drafts
_PROVIDER_DRAFT_JSON_FIELDS = {
    "selected_native_item_ids",
    "native_items",
    "mapped_items",
    "matched_items",
    "unavailable_items",
    "replacements",
    "changes",
    "provider_cart",
    "cart_summary",
    "checkout_context",
    "store_context",
    "order_blockers",
}

_PROVIDER_DRAFT_WRITABLE_FIELDS = {
    "selected_address_id",
    "selected_native_item_ids",
    "native_items",
    "mapped_items",
    "matched_items",
    "unavailable_items",
    "replacements",
    "changes",
    "provider_cart",
    "cart_summary",
    "checkout_context",
    "store_context",
    "selected_payment_method_id",
    "order_review_acknowledged",
    "can_place_order",
    "order_blockers",
    "confirmation_token",
    "snapshot_hash",
    "status",
    "last_validated_at",
}


def _normalize_provider_checkout_draft_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    for field in _PROVIDER_DRAFT_JSON_FIELDS:
        default = {} if field in {
            "cart_summary",
            "checkout_context",
            "store_context",
        } else []
        normalized[field] = _coerce_json(normalized.get(field), default)
    return normalized


def get_provider_checkout_draft(provider: str = "zepto") -> Dict[str, Any] | None:
    rows = _read_rows(
        "get_provider_checkout_draft",
        "provider_checkout_drafts",
        lambda: supabase.table("provider_checkout_drafts")
        .select("*")
        .eq("profile_id", get_household_profile_id())
        .eq("provider", provider)
        .limit(1)
        .execute(),
    )
    return _normalize_provider_checkout_draft_row(rows[0]) if rows else None


def save_provider_checkout_draft(
    draft: Dict[str, Any],
    provider: str = "zepto",
) -> Dict[str, Any]:
    payload = {
        key: value
        for key, value in draft.items()
        if key in _PROVIDER_DRAFT_WRITABLE_FIELDS
    }
    payload.update(
        {
            "profile_id": get_household_profile_id(),
            "provider": provider,
            "updated_at": _now_iso(),
        }
    )
    row = _confirmed_row(
        "save_provider_checkout_draft",
        "provider_checkout_drafts",
        lambda: supabase.table("provider_checkout_drafts")
        .upsert(payload, on_conflict="profile_id,provider")
        .execute(),
    )
    return _normalize_provider_checkout_draft_row(row)


def delete_provider_checkout_draft(provider: str = "zepto") -> bool:
    _confirmed_row(
        "delete_provider_checkout_draft",
        "provider_checkout_drafts",
        lambda: supabase.table("provider_checkout_drafts")
        .delete()
        .eq("profile_id", get_household_profile_id())
        .eq("provider", provider)
        .execute(),
    )
    return True


def claim_provider_checkout_operation(
    operation_id: str,
    provider: str = "zepto",
    lease_seconds: int = 120,
) -> bool:
    data = _execute(
        "claim_provider_checkout_operation",
        "provider_checkout_drafts",
        lambda: supabase.rpc(
            "claim_provider_checkout_operation",
            {
                "p_profile_id": get_household_profile_id(),
                "p_provider": provider,
                "p_operation_id": operation_id,
                "p_lease_seconds": lease_seconds,
            },
        ).execute(),
    )
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, bool):
        raise malformed_persistence_response(
            "claim_provider_checkout_operation", "provider_checkout_drafts"
        )
    return data


def release_provider_checkout_operation(
    operation_id: str,
    provider: str = "zepto",
) -> bool:
    data = _execute(
        "release_provider_checkout_operation",
        "provider_checkout_drafts",
        lambda: supabase.rpc(
            "release_provider_checkout_operation",
            {
                "p_profile_id": get_household_profile_id(),
                "p_provider": provider,
                "p_operation_id": operation_id,
            },
        ).execute(),
    )
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, bool):
        raise malformed_persistence_response(
            "release_provider_checkout_operation", "provider_checkout_drafts"
        )
    return data


# Recipe and grocery artifacts
def save_recipe_grocery_plan(
    plan: Dict[str, Any],
    cart_items: List[Dict[str, Any]] | None = None,
    update_cart: bool = False,
    user_name: str | None = None,
) -> Dict[str, Any]:
    cart_items = cart_items or []
    normalized_plan = _normalize_recipe_grocery_plan(
        plan, cart_items, update_cart
    )
    if not normalized_plan:
        raise ValueError("A structured recipe grocery plan is required.")
    normalized_cart = [
        item
        for item in (
            _normalize_grocery_item({**raw, "source": "agent"})
            for raw in cart_items
        )
        if item
    ]
    rpc_cart_rows = [_grocery_item_to_row(item) for item in normalized_cart]
    data = _execute(
        "save_recipe_grocery_plan",
        "recipe_grocery_plans,grocery_cart_items",
        lambda: supabase.rpc(
            "save_recipe_grocery_plan_with_cart",
            {
                "p_plan_id": normalized_plan["id"],
                "p_profile_id": get_household_profile_id(),
                "p_scope": normalized_plan["scope"],
                "p_request_text": normalized_plan["request"],
                "p_recipe_cards": normalized_plan["recipeCards"],
                "p_ingredients": normalized_plan["ingredients"],
                "p_pantry_considerations": normalized_plan[
                    "pantryConsiderations"
                ],
                "p_household_size": normalized_plan["householdSize"],
                "p_notes": normalized_plan["notes"],
                "p_source": normalized_plan["source"],
                "p_updates_cart": bool(update_cart),
                "p_cart_items": rpc_cart_rows,
                "p_created_at": normalized_plan["createdAt"],
                "p_updated_at": normalized_plan["updatedAt"],
            },
        ).execute(),
    )
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict):
        raise malformed_persistence_response(
            "save_recipe_grocery_plan",
            "recipe_grocery_plans,grocery_cart_items",
        )
    plan_row = data.get("plan")
    cart_rows = data.get("cart")
    if not isinstance(plan_row, dict) or not isinstance(cart_rows, list):
        raise malformed_persistence_response(
            "save_recipe_grocery_plan",
            "recipe_grocery_plans,grocery_cart_items",
        )
    saved_plan = _recipe_rows_to_plans([plan_row])[0]
    if update_cart:
        saved_plan["cart"] = _grocery_rows_to_items(cart_rows)
    return saved_plan


def get_recipe_grocery_plan(
    plan_id: str,
    user_name: str | None = None,
) -> Dict[str, Any] | None:
    rows = _read_rows(
        "get_recipe_grocery_plan",
        "recipe_grocery_plans",
        lambda: supabase.table("recipe_grocery_plans")
        .select("*")
        .eq("profile_id", get_household_profile_id())
        .eq("id", plan_id)
        .limit(1)
        .execute(),
    )
    plans = _recipe_rows_to_plans(rows)
    return plans[0] if plans else None


def list_recipe_grocery_plans(
    limit: int = 10,
    user_name: str | None = None,
) -> List[Dict[str, Any]]:
    try:
        safe_limit = max(1, min(int(limit or 10), 50))
    except (TypeError, ValueError):
        safe_limit = 10
    rows = _read_rows(
        "list_recipe_grocery_plans",
        "recipe_grocery_plans",
        lambda: supabase.table("recipe_grocery_plans")
        .select("*")
        .eq("profile_id", get_household_profile_id())
        .order("created_at", desc=True)
        .limit(safe_limit)
        .execute(),
    )
    return _recipe_rows_to_plans(rows)


def get_latest_recipe_grocery_plan_metadata(
    user_name: str | None = None,
) -> Dict[str, Any] | None:
    plans = list_recipe_grocery_plans(limit=1, user_name=user_name)
    return _recipe_plan_metadata(plans[0]) if plans else None


# Macro diary
def get_macro_diary(user_name: str) -> List[Dict[str, Any]]:
    rows = _read_rows(
        "get_macro_diary",
        "macro_diary",
        lambda: supabase.table("macro_diary")
        .select("*")
        .eq("profile_id", get_user_id(user_name))
        .execute(),
    )
    return [
        {
            "id": row.get("id"),
            "name": row["meal_name"],
            "calories": row["calories"],
            "macros": {
                "protein": row["protein_g"],
                "carbs": row["carbs_g"],
                "fat": row["fat_g"],
                "fiber": row["fiber_g"],
            },
            "time": row["logged_at"],
        }
        for row in rows
    ]


def log_macros(
    user_name: str,
    meal_name: str,
    calories: int,
    protein: int,
    carbs: int,
    fat: int,
    fiber: int = 0,
) -> Dict[str, Any]:
    return _confirmed_row(
        "log_macros",
        "macro_diary",
        lambda: supabase.table("macro_diary")
        .insert(
            {
                "profile_id": get_user_id(user_name),
                "meal_name": meal_name,
                "calories": calories,
                "protein_g": protein,
                "carbs_g": carbs,
                "fat_g": fat,
                "fiber_g": fiber,
            }
        )
        .execute(),
    )


def clear_macro_diary(user_name: str) -> bool:
    profile_id = get_user_id(user_name)
    _execute(
        "clear_macro_diary",
        "macro_diary",
        lambda: supabase.table("macro_diary")
        .delete()
        .eq("profile_id", profile_id)
        .execute(),
    )
    return len(get_macro_diary(user_name)) == 0


def validate_persistence_readiness() -> Dict[str, Any]:
    """Verify credential access, required schema, and household configuration."""
    for table, columns in REQUIRED_TABLE_COLUMNS.items():
        _read_rows(
            "readiness_check",
            table,
            lambda table=table, columns=columns: supabase.table(table)
            .select(",".join(columns))
            .limit(1)
            .execute(),
        )
    try:
        profile = get_household_profile()
    except PersistenceError as error:
        if error.supabase_code == "household_profile_missing":
            raise PersistenceConfigurationError(
                "The configured household profile is missing from public.profiles."
            ) from error
        raise
    return {
        "status": "ready",
        "credential_type": SUPABASE_KEY_TYPE,
        "tables": list(REQUIRED_TABLE_COLUMNS),
        "household_profile_id": profile["id"],
    }
