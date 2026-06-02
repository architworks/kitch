# Kitch: Supabase Production Client Wrapper

import os
from datetime import datetime, timezone
import json
from typing import Dict, List, Any
from uuid import uuid4
from dotenv import load_dotenv
from supabase import create_client, Client
from app.household_config import (
    DEFAULT_HOUSEHOLD_SIZE,
    HOUSEHOLD_NAME,
    canonical_user_name,
    get_household_profile_id,
    get_user_id,
)

load_dotenv()

# 1. Initialize Supabase Connection Client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials missing! Set SUPABASE_URL and SUPABASE_KEY in your .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

_grocery_cart_fallback: List[Dict[str, Any]] = []
_recipe_grocery_plan_fallback: List[Dict[str, Any]] = []

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

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
        return value.strip().lower() in {"1", "true", "yes", "y", "checked", "stocked"}
    return bool(value)

def _normalize_grocery_item(item: Dict[str, Any]) -> Dict[str, Any] | None:
    """Normalize agent/UI grocery items into the frontend cart shape."""
    name = str(item.get("name") or item.get("ingredient_name") or item.get("item") or "").strip()
    if not name:
        return None

    try:
        amount = float(item.get("amount", item.get("quantity", item.get("qty", 1))) or 1)
    except (TypeError, ValueError):
        amount = 1
    source = str(item.get("source") or "agent").strip().lower() or "agent"
    if source not in {"agent", "manual"}:
        source = "agent"

    return {
        "id": item.get("id") or f"local-{uuid4()}",
        "name": name,
        "amount": amount,
        "unit": str(item.get("unit") or "piece").strip() or "piece",
        "category": str(item.get("category") or item.get("section") or "General").strip() or "General",
        "source": source,
        "checked": _coerce_bool(item.get("checked", False)),
        "alreadyStocked": _coerce_bool(item.get("alreadyStocked", item.get("already_stocked", False))),
        "stockNote": str(item.get("stockNote") or item.get("stock_note") or "").strip(),
        "recipeGroceryPlanId": item.get("recipeGroceryPlanId") or item.get("recipe_grocery_plan_id"),
    }

def _set_grocery_fallback(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    global _grocery_cart_fallback
    _grocery_cart_fallback = [item for item in (_normalize_grocery_item(i) for i in items) if item]
    return [dict(item) for item in _grocery_cart_fallback]

def _grocery_rows_to_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mapped = []
    for row in rows or []:
        item = _normalize_grocery_item({
            "id": row.get("id"),
            "name": row.get("ingredient_name"),
            "amount": row.get("amount"),
            "unit": row.get("unit"),
            "category": row.get("category"),
            "source": row.get("source"),
            "checked": row.get("checked"),
            "already_stocked": row.get("already_stocked"),
            "stock_note": row.get("stock_note"),
            "recipe_grocery_plan_id": row.get("recipe_grocery_plan_id"),
        })
        if item:
            mapped.append(item)
    return mapped

def _grocery_item_to_row(item: Dict[str, Any], profile_id: str, recipe_grocery_plan_id: str | None = None) -> Dict[str, Any]:
    row = {
        "profile_id": profile_id,
        "ingredient_name": item["name"],
        "amount": item["amount"],
        "unit": item["unit"],
        "category": item["category"],
        "source": item["source"],
        "checked": item["checked"],
        "already_stocked": item["alreadyStocked"],
        "stock_note": item["stockNote"],
    }
    plan_id = item.get("recipeGroceryPlanId") or item.get("recipe_grocery_plan_id") or recipe_grocery_plan_id
    if plan_id:
        row["recipe_grocery_plan_id"] = plan_id
    return row

def _recipe_card_ingredients(recipe_cards: List[Dict[str, Any]]) -> List[Any]:
    ingredients: List[Any] = []
    for card in recipe_cards:
        if isinstance(card, dict):
            card_ingredients = card.get("ingredients") or card.get("ingredientList") or card.get("ingredient_list") or []
            if isinstance(card_ingredients, list):
                ingredients.extend(card_ingredients)
    return ingredients

def _normalize_recipe_grocery_plan(plan: Dict[str, Any], cart_items: List[Dict[str, Any]] | None = None, update_cart: bool = False) -> Dict[str, Any] | None:
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

    recipe_cards = []
    for card in raw_cards:
        if isinstance(card, dict):
            recipe_cards.append(card)
        elif str(card).strip():
            recipe_cards.append({"title": str(card).strip()})

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

    household = get_household_profile()
    try:
        household_size = int(plan.get("householdSize") or plan.get("household_size") or household.get("household_size") or DEFAULT_HOUSEHOLD_SIZE)
    except (TypeError, ValueError):
        household_size = DEFAULT_HOUSEHOLD_SIZE

    created_at = plan.get("createdAt") or plan.get("created_at") or _now_iso()
    updated_at = plan.get("updatedAt") or plan.get("updated_at") or created_at

    return {
        "id": str(plan.get("id") or uuid4()),
        "scope": scope,
        "scopeLabel": str(plan.get("scopeLabel") or plan.get("scope_label") or scope.get("label") or scope.get("type") or "Recipe + grocery plan"),
        "request": str(plan.get("request") or plan.get("requestText") or plan.get("request_text") or "").strip(),
        "recipeCards": recipe_cards,
        "ingredients": ingredients,
        "pantryConsiderations": pantry_considerations,
        "householdSize": household_size,
        "notes": str(plan.get("notes") or plan.get("instructions") or "").strip(),
        "source": str(plan.get("source") or "agent").strip().lower() or "agent",
        "createdAt": created_at,
        "updatedAt": updated_at,
        "updatesCart": bool(update_cart),
        "cartItemCount": len(cart_items or []),
    }

def _recipe_plan_to_row(plan: Dict[str, Any], profile_id: str) -> Dict[str, Any]:
    return {
        "id": plan["id"],
        "profile_id": profile_id,
        "scope": plan["scope"],
        "request_text": plan["request"],
        "recipe_cards": plan["recipeCards"],
        "ingredients": plan["ingredients"],
        "pantry_considerations": plan["pantryConsiderations"],
        "household_size": plan["householdSize"],
        "notes": plan["notes"],
        "source": plan["source"],
        "updates_cart": plan["updatesCart"],
        "cart_item_count": plan["cartItemCount"],
        "created_at": plan["createdAt"],
        "updated_at": plan["updatedAt"],
    }

def _recipe_rows_to_plans(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    plans = []
    for row in rows or []:
        scope = _coerce_json(row.get("scope"), {})
        recipe_cards = _coerce_json(row.get("recipe_cards"), [])
        ingredients = _coerce_json(row.get("ingredients"), [])
        pantry_considerations = _coerce_json(row.get("pantry_considerations"), [])
        plan = {
            "id": str(row.get("id")),
            "scope": scope if isinstance(scope, dict) else {},
            "scopeLabel": (scope or {}).get("label") if isinstance(scope, dict) else "Recipe + grocery plan",
            "request": row.get("request_text") or "",
            "recipeCards": recipe_cards if isinstance(recipe_cards, list) else [],
            "ingredients": ingredients if isinstance(ingredients, list) else [],
            "pantryConsiderations": pantry_considerations if isinstance(pantry_considerations, list) else [],
            "householdSize": row.get("household_size") or DEFAULT_HOUSEHOLD_SIZE,
            "notes": row.get("notes") or "",
            "source": row.get("source") or "agent",
            "updatesCart": bool(row.get("updates_cart", False)),
            "cartItemCount": row.get("cart_item_count"),
            "createdAt": row.get("created_at"),
            "updatedAt": row.get("updated_at"),
        }
        plan["recipeCount"] = len(plan["recipeCards"])
        plan["ingredientCount"] = len(plan["ingredients"])
        plans.append(plan)
    return plans

def _recipe_plan_metadata(plan: Dict[str, Any] | None) -> Dict[str, Any] | None:
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
        "cartItemCount": plan.get("cartItemCount"),
        "createdAt": plan.get("createdAt"),
        "updatedAt": plan.get("updatedAt"),
    }

# 2. Profiles CRUD
def get_profile(user_name: str) -> Dict[str, Any]:
    """Fetches user profile information from Supabase."""
    profile_id = get_user_id(user_name)
    try:
        response = supabase.table("profiles").select("*").eq("id", profile_id).execute()
        if response.data:
            return response.data[0]
        return {}
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return {}

def get_household_profile() -> Dict[str, Any]:
    """Fetches the shared household profile settings."""
    try:
        response = supabase.table("profiles").select("*").eq("id", get_household_profile_id()).execute()
        if response.data:
            return response.data[0]
        return {
            "full_name": HOUSEHOLD_NAME,
            "diet_preference": "balanced",
            "household_size": DEFAULT_HOUSEHOLD_SIZE,
            "daily_calorie_target": 2000
        }
    except Exception as e:
        print(f"Error fetching household profile: {e}")
        return {
            "full_name": HOUSEHOLD_NAME,
            "diet_preference": "balanced",
            "household_size": DEFAULT_HOUSEHOLD_SIZE,
            "daily_calorie_target": 2000
        }

def update_profile(user_name: str, diet_preference: str, household_size: int, daily_calorie_target: int = 2000) -> Dict[str, Any]:
    """Updates user profile information in Supabase."""
    user_name = canonical_user_name(user_name)
    profile_id = get_user_id(user_name)
    data = {
        "full_name": user_name,
        "diet_preference": diet_preference,
        "household_size": household_size,
        "daily_calorie_target": daily_calorie_target
    }
    try:
        response = supabase.table("profiles").upsert({"id": profile_id, **data}).execute()
        return response.data[0] if response.data else {}
    except Exception as e:
        print(f"Error updating profile: {e}")
        return {}

def update_household_profile(diet_preference: str, household_size: int, daily_calorie_target: int = 2000) -> Dict[str, Any]:
    """Updates shared household planning settings."""
    data = {
        "id": get_household_profile_id(),
        "full_name": HOUSEHOLD_NAME,
        "diet_preference": diet_preference,
        "household_size": household_size,
        "daily_calorie_target": daily_calorie_target
    }
    try:
        response = supabase.table("profiles").upsert(data).execute()
        return response.data[0] if response.data else {}
    except Exception as e:
        print(f"Error updating household profile: {e}")
        return {}

# 3. Pantry & Fridge Stock CRUD
def get_pantry_stock(user_name: str | None = None) -> List[Dict[str, Any]]:
    """Fetches shared household pantry stock levels from Supabase."""
    profile_id = get_household_profile_id()
    try:
        response = supabase.table("pantry_stock").select("*").eq("profile_id", profile_id).execute()
        # Map DB keys to frontend state format
        mapped = []
        for row in response.data or []:
            mapped.append({
                "name": row["ingredient_name"],
                "amount": float(row["amount"]),
                "unit": row["unit"]
            })
        return mapped
    except Exception as e:
        print(f"Error fetching pantry stock: {e}")
        return []

def add_to_pantry(user_name: str | None, name: str, amount: float, unit: str = "piece") -> Dict[str, Any]:
    """Adds or updates an ingredient in the shared household pantry."""
    profile_id = get_household_profile_id()
    name_clean = name.strip()
    try:
        # Check if item already exists case-insensitively
        pantry_items = get_pantry_stock()
        existing = next((i for i in pantry_items if i["name"].lower() == name_clean.lower()), None)
        
        if existing:
            # Update quantity
            new_amount = float(existing["amount"]) + float(amount)
            response = supabase.table("pantry_stock").update({
                "amount": new_amount,
                "unit": unit
            }).eq("profile_id", profile_id).eq("ingredient_name", existing["name"]).execute()
            return response.data[0] if response.data else {}
        else:
            # Insert new
            data = {
                "profile_id": profile_id,
                "ingredient_name": name_clean,
                "amount": amount,
                "unit": unit
            }
            response = supabase.table("pantry_stock").insert(data).execute()
            return response.data[0] if response.data else {}
    except Exception as e:
        print(f"Error adding to pantry: {e}")
        return {}

def remove_from_pantry(user_name: str | None, name: str) -> bool:
    """Removes a pantry item from the shared household pantry."""
    profile_id = get_household_profile_id()
    try:
        supabase.table("pantry_stock").delete().eq("profile_id", profile_id).eq("ingredient_name", name).execute()
        return True
    except Exception as e:
        print(f"Error removing from pantry: {e}")
        return False

# 4. Shared Grocery Cart CRUD
def get_grocery_cart(user_name: str | None = None) -> List[Dict[str, Any]]:
    """
    Fetches the shared household intermediary grocery cart.

    If the optional Supabase table has not been migrated yet, returns the current
    process fallback so local development still reflects agent-generated carts.
    """
    profile_id = get_household_profile_id()
    try:
        response = (
            supabase.table("grocery_cart_items")
            .select("*")
            .eq("profile_id", profile_id)
            .order("category")
            .order("ingredient_name")
            .execute()
        )
        return _grocery_rows_to_items(response.data or [])
    except Exception as e:
        print(f"Error fetching grocery cart, using process fallback: {e}")
        return [dict(item) for item in _grocery_cart_fallback]

def replace_planned_grocery_cart(
    items: List[Dict[str, Any]],
    user_name: str | None = None,
    recipe_grocery_plan_id: str | None = None
) -> List[Dict[str, Any]]:
    """
    Replaces agent-planned grocery cart rows while preserving manual rows.

    This is intentionally provider-agnostic. Blinkit/Zepto payload preparation
    remains a later export step.
    """
    profile_id = get_household_profile_id()
    normalized = []
    for raw in items:
        enriched = {**raw, "source": "agent"}
        item = _normalize_grocery_item(enriched)
        if item:
            normalized.append(item)

    try:
        supabase.table("grocery_cart_items").delete().eq("profile_id", profile_id).eq("source", "agent").execute()
        if normalized:
            rows = [_grocery_item_to_row(item, profile_id, recipe_grocery_plan_id) for item in normalized]
            try:
                supabase.table("grocery_cart_items").insert(rows).execute()
            except Exception as insert_error:
                if recipe_grocery_plan_id and "recipe_grocery_plan_id" in str(insert_error):
                    for row in rows:
                        row.pop("recipe_grocery_plan_id", None)
                    supabase.table("grocery_cart_items").insert(rows).execute()
                else:
                    raise
        return get_grocery_cart()
    except Exception as e:
        print(f"Error replacing planned grocery cart, using process fallback: {e}")
        manual_rows = [item for item in _grocery_cart_fallback if item.get("source") == "manual"]
        if recipe_grocery_plan_id:
            normalized = [{**item, "recipeGroceryPlanId": recipe_grocery_plan_id} for item in normalized]
        return _set_grocery_fallback([*manual_rows, *normalized])

def add_grocery_cart_item(item: Dict[str, Any], user_name: str | None = None) -> Dict[str, Any]:
    """Adds a manual grocery cart item to the shared household cart."""
    profile_id = get_household_profile_id()
    normalized = _normalize_grocery_item({**item, "source": item.get("source") or "manual"})
    if not normalized:
        return {}

    try:
        response = supabase.table("grocery_cart_items").insert(_grocery_item_to_row(normalized, profile_id)).execute()
        saved = _grocery_rows_to_items(response.data or [])
        return saved[0] if saved else normalized
    except Exception as e:
        print(f"Error adding grocery cart item, using process fallback: {e}")
        _grocery_cart_fallback.append(normalized)
        return dict(normalized)

def update_grocery_cart_item(item_id: str, updates: Dict[str, Any], user_name: str | None = None) -> Dict[str, Any]:
    """Updates a grocery cart row by id."""
    profile_id = get_household_profile_id()
    allowed_updates = {}
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
    for key, value in updates.items():
        db_key = field_map.get(key)
        if db_key:
            allowed_updates[db_key] = value

    if not allowed_updates:
        return {}

    try:
        response = (
            supabase.table("grocery_cart_items")
            .update(allowed_updates)
            .eq("profile_id", profile_id)
            .eq("id", item_id)
            .execute()
        )
        saved = _grocery_rows_to_items(response.data or [])
        return saved[0] if saved else {}
    except Exception as e:
        print(f"Error updating grocery cart item, using process fallback: {e}")
        for item in _grocery_cart_fallback:
            if str(item.get("id")) == str(item_id):
                normalized = _normalize_grocery_item({**item, **updates, "id": item.get("id")})
                if normalized:
                    item.update(normalized)
                    return dict(item)
        return {}

def delete_grocery_cart_item(item_id: str, user_name: str | None = None) -> bool:
    """Deletes a grocery cart row by id."""
    profile_id = get_household_profile_id()
    try:
        supabase.table("grocery_cart_items").delete().eq("profile_id", profile_id).eq("id", item_id).execute()
        return True
    except Exception as e:
        print(f"Error deleting grocery cart item, using process fallback: {e}")
        before = len(_grocery_cart_fallback)
        _grocery_cart_fallback[:] = [item for item in _grocery_cart_fallback if str(item.get("id")) != str(item_id)]
        return len(_grocery_cart_fallback) != before

def clear_planned_grocery_cart(user_name: str | None = None) -> bool:
    """Deletes only agent-generated grocery cart rows."""
    profile_id = get_household_profile_id()
    try:
        supabase.table("grocery_cart_items").delete().eq("profile_id", profile_id).eq("source", "agent").execute()
        return True
    except Exception as e:
        print(f"Error clearing planned grocery cart, using process fallback: {e}")
        _grocery_cart_fallback[:] = [item for item in _grocery_cart_fallback if item.get("source") != "agent"]
        return True

# 5. Recipe + Grocery Plan Artifacts
def save_recipe_grocery_plan(
    plan: Dict[str, Any],
    cart_items: List[Dict[str, Any]] | None = None,
    update_cart: bool = False,
    user_name: str | None = None
) -> Dict[str, Any]:
    """
    Persists a recipe+ingredient artifact. Grocery requests may also replace
    agent-generated native cart rows linked back to this artifact.
    """
    profile_id = get_household_profile_id()
    cart_items = cart_items or []
    normalized_plan = _normalize_recipe_grocery_plan(plan, cart_items, update_cart)
    if not normalized_plan:
        return {}

    saved_plan = dict(normalized_plan)
    try:
        response = supabase.table("recipe_grocery_plans").upsert(
            _recipe_plan_to_row(normalized_plan, profile_id)
        ).execute()
        saved_rows = _recipe_rows_to_plans(response.data or [])
        if saved_rows:
            saved_plan = {**saved_plan, **saved_rows[0], "updatesCart": bool(update_cart), "cartItemCount": len(cart_items)}
    except Exception as e:
        print(f"Error saving recipe grocery plan, using process fallback: {e}")
        existing_index = next(
            (idx for idx, item in enumerate(_recipe_grocery_plan_fallback) if str(item.get("id")) == str(saved_plan["id"])),
            None
        )
        if existing_index is None:
            _recipe_grocery_plan_fallback.append(saved_plan)
        else:
            _recipe_grocery_plan_fallback[existing_index] = saved_plan

    if update_cart:
        saved_plan["cart"] = replace_planned_grocery_cart(
            cart_items,
            user_name=user_name,
            recipe_grocery_plan_id=saved_plan["id"]
        )
    return saved_plan

def get_recipe_grocery_plan(plan_id: str, user_name: str | None = None) -> Dict[str, Any] | None:
    """Fetches one recipe+grocery artifact by id."""
    profile_id = get_household_profile_id()
    try:
        response = (
            supabase.table("recipe_grocery_plans")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("id", plan_id)
            .limit(1)
            .execute()
        )
        plans = _recipe_rows_to_plans(response.data or [])
        return plans[0] if plans else None
    except Exception as e:
        print(f"Error fetching recipe grocery plan, using process fallback: {e}")
        return next((dict(plan) for plan in _recipe_grocery_plan_fallback if str(plan.get("id")) == str(plan_id)), None)

def list_recipe_grocery_plans(limit: int = 10, user_name: str | None = None) -> List[Dict[str, Any]]:
    """Lists recent recipe+grocery artifacts for the shared household."""
    profile_id = get_household_profile_id()
    try:
        safe_limit = max(1, min(int(limit or 10), 50))
    except (TypeError, ValueError):
        safe_limit = 10
    try:
        response = (
            supabase.table("recipe_grocery_plans")
            .select("*")
            .eq("profile_id", profile_id)
            .order("created_at", desc=True)
            .limit(safe_limit)
            .execute()
        )
        return _recipe_rows_to_plans(response.data or [])
    except Exception as e:
        print(f"Error listing recipe grocery plans, using process fallback: {e}")
        return [
            dict(plan)
            for plan in sorted(
                _recipe_grocery_plan_fallback,
                key=lambda item: str(item.get("createdAt") or ""),
                reverse=True
            )[:safe_limit]
        ]

def get_latest_recipe_grocery_plan_metadata(user_name: str | None = None) -> Dict[str, Any] | None:
    """Returns compact metadata for the latest recipe+grocery artifact."""
    plans = list_recipe_grocery_plans(limit=1, user_name=user_name)
    return _recipe_plan_metadata(plans[0]) if plans else None

# 6. Macro Intake Diary CRUD
def get_macro_diary(user_name: str) -> List[Dict[str, Any]]:
    """Fetches macro log records from Supabase."""
    profile_id = get_user_id(user_name)
    try:
        response = supabase.table("macro_diary").select("*").eq("profile_id", profile_id).execute()
        # Map database format to frontend state layout
        mapped = []
        for row in response.data or []:
            mapped.append({
                "name": row["meal_name"],
                "calories": row["calories"],
                "macros": {
                    "protein": row["protein_g"],
                    "carbs": row["carbs_g"],
                    "fat": row["fat_g"],
                    "fiber": row["fiber_g"]
                },
                "time": row["logged_at"] # In production, format timestamp nicely
            })
        return mapped
    except Exception as e:
        print(f"Error fetching macro diary: {e}")
        return []

def log_macros(
    user_name: str, 
    meal_name: str, 
    calories: int, 
    protein: int, 
    carbs: int, 
    fat: int, 
    fiber: int = 0
) -> Dict[str, Any]:
    """Logs a macro plate record in Supabase."""
    profile_id = get_user_id(user_name)
    data = {
        "profile_id": profile_id,
        "meal_name": meal_name,
        "calories": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "fiber_g": fiber
    }
    try:
        response = supabase.table("macro_diary").insert(data).execute()
        return response.data[0] if response.data else {}
    except Exception as e:
        print(f"Error logging macros: {e}")
        return {}

def clear_macro_diary(user_name: str) -> bool:
    """Deletes all macro logs for the active user."""
    profile_id = get_user_id(user_name)
    try:
        supabase.table("macro_diary").delete().eq("profile_id", profile_id).execute()
        return True
    except Exception as e:
        print(f"Error clearing macro logs: {e}")
        return False
