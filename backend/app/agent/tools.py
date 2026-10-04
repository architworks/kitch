# Kitch: Core ADK 2.0 Custom Tools

import json as _json
import math
from typing import List, Dict, Any
from google.adk.tools import ToolContext
from app.household_config import DEFAULT_ACTIVE_USER
from app.household_config import canonical_user_name
from app.planning_calendar import calendar_context, parse_iso_date
from app.supabase_client import (
    apply_meal_plan_edits as db_apply_meal_plan_edits,
    get_household_timezone,
    get_meal_schedule as db_get_meal_schedule,
    replace_meal_plan_range as db_replace_meal_plan_range,
    get_pantry_stock as db_get_pantry_stock,
    get_pantry_state as db_get_pantry_state,
    log_macros as db_log_macros,
    get_macro_diary as db_get_macro_diary,
    get_grocery_cart as db_get_grocery_cart,
    apply_native_grocery_cart_changes as db_apply_native_grocery_cart_changes,
    clear_planned_grocery_cart as db_clear_planned_grocery_cart,
    save_recipe_grocery_plan as db_save_recipe_grocery_plan,
    get_recipe_grocery_plan as db_get_recipe_grocery_plan,
    list_recipe_grocery_plans as db_list_recipe_grocery_plans,
    update_macro_entry as db_update_macro_entry,
    delete_macro_entry as db_delete_macro_entry,
    update_nutrition_targets as db_update_nutrition_targets,
    update_household_profile as db_update_household_profile,
    get_household_profile as db_get_household_profile,
    create_pending_agent_action as db_create_pending_agent_action,
    remove_future_meal_plan_entries as db_remove_future_meal_plan_entries,
    update_recipe_grocery_plan as db_update_recipe_grocery_plan,
    delete_recipe_grocery_plan as db_delete_recipe_grocery_plan,
)
from app.providers.registry import provider_registry
from app.agent.memory import search_household_memory_tool

# --- Safety Parsing Helper ---
def _ensure_dict(val):
  """Parse val if it's a JSON string, otherwise return as-is."""
  if isinstance(val, str):
    try:
      return _json.loads(val)
    except _json.JSONDecodeError:
      return val
  return val


def _request_user(user_name: str = "", tool_context: ToolContext = None) -> str:
  """Bind user-specific agent tools to the server-owned active-user session."""
  scoped_user = ""
  if tool_context is not None:
    state = getattr(tool_context, "state", None)
    if state is not None:
      scoped_user = str(state.get("user:profile_name", "") or "").strip()
  return canonical_user_name(scoped_user or user_name or DEFAULT_ACTIVE_USER)

# --- Section 1: Standard Meal Planning & Supabase Helpers ---

def get_current_datetime() -> str:
  """
  Returns the current date, time, and day of the week.
  Use this to answer questions like "what day is today", "what's for dinner tonight", etc.
  """
  context = calendar_context(get_household_timezone())
  now = context["now"]
  return (
    now.strftime("Today is %A, %B %d, %Y (%Y-%m-%d). The current time is %I:%M %p. ")
    + f"Household timezone: {context['timezone']}. "
    + f"Tomorrow is {context['tomorrow'].strftime('%A, %B %d, %Y (%Y-%m-%d)')}. "
    + f"The current week ends {context['current_week_end'].strftime('%A, %B %d, %Y (%Y-%m-%d)')}. "
    + f"The next calendar week runs from {context['next_week_start'].strftime('%A, %B %d, %Y (%Y-%m-%d)')} "
    + f"through {context['next_week_end'].strftime('%A, %B %d, %Y (%Y-%m-%d)')}."
  )

def get_meal_schedule_dict(
  start_date: str,
  end_date: str,
  user_name: str = "",
) -> Dict[str, Dict[str, str]]:
  """
  Fetch the shared household schedule for an explicit inclusive ISO date range.
  """
  return {
    row["plan_date"]: {
      "weekday": row["weekday"],
      "breakfast": row["breakfast"],
      "lunch": row["lunch"],
      "dinner": row["dinner"],
    }
    for row in db_get_meal_schedule(start_date, end_date)
  }

def get_meal_schedule_tool(
  start_date: str,
  end_date: str,
  user_name: str = "",
) -> Dict[str, Dict[str, str]]:
  """
  Fetch planned meal names for an explicit inclusive ISO date range. Missing
  dates are unplanned; never substitute a same-named weekday from another week.
  """
  return get_meal_schedule_dict(start_date, end_date, user_name)

def replace_meal_plan_range_tool(
  start_date: str,
  end_date: str,
  meal_plan: List[Dict[str, Any]],
  user_name: str = "",
) -> Dict[str, Any]:
  """
  Atomically replace every date in an explicit range with breakfast, lunch,
  and dinner meal-name strings. The list must contain exactly one object per
  date with plan_date, breakfast, lunch, and dinner. Use targeted edits for
  modifications instead.
  """
  meal_plan = _ensure_dict(meal_plan)
  if not isinstance(meal_plan, list):
    return {"status": "error", "message": "meal_plan must be a list of dated plan objects"}
  context = calendar_context(get_household_timezone())
  if parse_iso_date(start_date) < context["today"]:
    return {"status": "error", "message": "Past meal-plan dates cannot be created or replaced."}
  saved = db_replace_meal_plan_range(start_date, end_date, meal_plan)
  return {
    "status": "success",
    "affected_dates": [row["plan_date"] for row in saved],
    "message": f"Successfully replaced {len(saved)} dated meal-plan days in durable storage."
  }

def update_dated_meals_tool(
  edits: List[Dict[str, Any]],
  user_name: str = "",
) -> Dict[str, Any]:
  """
  Atomically apply targeted dated meal edits while preserving every unrelated
  date and meal slot. Each edit requires plan_date, meal_slot, and meal_name.
  """
  edits = _ensure_dict(edits)
  if not isinstance(edits, list) or not edits:
    return {"status": "error", "message": "edits must be a non-empty list"}
  context = calendar_context(get_household_timezone())
  if any(parse_iso_date(str(edit.get("plan_date") or "")) < context["today"] for edit in edits):
    return {"status": "error", "message": "Past meal-plan dates cannot be modified."}
  saved = db_apply_meal_plan_edits(edits)
  return {
    "status": "success",
    "affected_dates": [row["plan_date"] for row in saved],
    "message": f"Successfully updated {len(saved)} dated meal-plan days in durable storage."
  }


def remove_future_meals_tool(
  operations: List[Dict[str, Any]], user_name: str = DEFAULT_ACTIVE_USER,
) -> Dict[str, Any]:
  """
  Remove future meal slots, dates, ranges, or every saved future plan.

  Supported actions are slot, date, range, and all. The all action resolves the
  household's actual saved future dates before asking for confirmation. Past
  plans are never included.
  """
  from app.agent_confirmation import record_confirmation
  parsed = _ensure_dict(operations)
  if not isinstance(parsed, list) or not parsed:
    return {"status": "error", "message": "operations must be a non-empty list"}

  context = calendar_context(get_household_timezone())
  today = context["today"]
  aliases = {
    "remove_slot": "slot", "delete_slot": "slot", "clear_slot": "slot", "remove_meal": "slot",
    "day": "date", "remove_date": "date", "delete_date": "date", "clear_date": "date",
    "remove_range": "range", "delete_range": "range", "clear_range": "range",
  }
  all_actions = {
    "all", "clear", "clear_all", "delete_all", "remove_all", "all_future",
    "clear_future", "clear_all_future", "clear_all_meal_plans", "remove_all_meal_plans",
  }
  normalized: List[Dict[str, Any]] = []

  for raw_operation in parsed:
    if not isinstance(raw_operation, dict):
      return {"status": "error", "message": "Each meal removal operation must be an object."}
    operation = dict(raw_operation)
    raw_action = str(operation.get("action") or "").strip().lower().replace("-", "_").replace(" ", "_")
    has_dates = any(operation.get(key) for key in ("start_date", "end_date", "plan_date", "date"))
    if raw_action in all_actions and not has_dates:
      future_days = db_get_meal_schedule(today.isoformat(), None)
      future_dates = sorted({str(day.get("plan_date") or "") for day in future_days if day.get("plan_date")})
      if not future_dates:
        return {
          "status": "success", "affected_dates": [],
          "message": "There are no saved future meal plans to remove.",
        }
      normalized.append({
        "action": "range", "start_date": future_dates[0], "end_date": future_dates[-1],
      })
      continue

    action = aliases.get(raw_action, raw_action)
    if not action:
      action = "slot" if operation.get("meal_slot") else (
        "range" if operation.get("end_date") else "date"
      )
    if action not in {"slot", "date", "range"}:
      return {
        "status": "error",
        "message": "Meal removals must target a future meal slot, date, date range, or all future plans.",
      }

    start_value = operation.get("start_date") or operation.get("plan_date") or operation.get("date")
    end_value = operation.get("end_date") or start_value
    if not start_value:
      return {"status": "error", "message": "Meal removal requires an exact future date."}
    try:
      start_date = parse_iso_date(str(start_value))
      end_date = parse_iso_date(str(end_value))
    except ValueError:
      return {"status": "error", "message": "Meal removal dates must use exact ISO calendar dates."}
    if start_date < today or end_date < today:
      return {"status": "error", "message": "Past meal plans cannot be modified."}
    if end_date < start_date:
      return {"status": "error", "message": "Meal removal end date cannot precede its start date."}

    normalized_operation: Dict[str, Any] = {
      "action": action, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
    }
    if action == "slot":
      meal_slot = str(operation.get("meal_slot") or "").strip().lower()
      if meal_slot not in {"breakfast", "lunch", "dinner"}:
        return {"status": "error", "message": "A meal-slot removal must name breakfast, lunch, or dinner."}
      if end_date != start_date:
        return {"status": "error", "message": "A meal-slot removal can target only one exact date."}
      normalized_operation["meal_slot"] = meal_slot
    elif action == "date":
      normalized_operation["end_date"] = start_date.isoformat()
    normalized.append(normalized_operation)

  is_bulk = len(normalized) > 1 or any(op["action"] == "range" for op in normalized)
  if not is_bulk:
    return {"status": "success", **db_remove_future_meal_plan_entries(normalized)}

  if len(normalized) == 1 and normalized[0]["action"] == "range":
    impact_message = (
      f"This removes saved meals from {normalized[0]['start_date']} through "
      f"{normalized[0]['end_date']}. Past meal plans remain unchanged."
    )
  else:
    targets = ", ".join(
      f"{op.get('meal_slot') + ' on ' if op.get('meal_slot') else ''}{op['start_date']}"
      for op in normalized
    )
    impact_message = f"This removes the requested future meal-plan scopes: {targets}."
  pending = db_create_pending_agent_action(
    active_user=user_name, action_type="remove_meal_plans", payload={"operations": normalized},
    impact_summary={"title": "Remove these planned meals?", "message": impact_message},
  )
  action = {"type": "CONFIRM_DESTRUCTIVE_ACTION", "action_id": pending["id"], "impact": pending["impact_summary"]}
  record_confirmation(action)
  return {"status": "confirmation_required", **action}

# --- Section 2: Supabase Pantry Stock & Logs ---
def get_pantry_stock_tool(user_name: str = "") -> List[Dict[str, Any]]:
  """
  Query Supabase to fetch current shared household pantry stock levels.
  """
  return db_get_pantry_stock()

def get_grocery_cart_tool(user_name: str = "") -> List[Dict[str, Any]]:
  """
  Fetch the current provider-agnostic shared household grocery cart.
  """
  return db_get_grocery_cart()

def modify_native_grocery_cart_tool(
  changes: List[Dict[str, Any]],
  user_name: str = "",
) -> Dict[str, Any]:
  """Apply explicit standalone item changes to the durable native Kitch cart.

  This tool is owned by the grocery specialist. It does not generate recipes,
  search an ordering provider, synchronize a provider cart, or place an order.

  Each change requires an action:
  - add: add the amount to an exact existing name/unit row, or create a manual row.
  - set/update: set fields on a row resolved by item_id or exact name.
  - remove/delete: delete a row resolved by item_id or exact name.
  """
  parsed = _ensure_dict(changes)
  if not isinstance(parsed, list) or not parsed:
    return {"status": "error", "message": "changes must be a non-empty list"}

  if not all(isinstance(change, dict) for change in parsed):
    return {"status": "error", "message": "Each native-cart change must be an object."}
  cart = db_apply_native_grocery_cart_changes(parsed)
  return {
    "status": "success",
    "message": f"Applied {len(parsed)} standalone native-cart change(s) atomically.",
    "applied_changes": parsed,
    "grocery_cart": cart,
    "provider_cart_changed": False,
  }

def clear_planned_grocery_cart_tool(user_name: str = "") -> Dict[str, Any]:
  """
  Clear only agent-generated grocery rows. Manual user-added rows remain.
  """
  ok = db_clear_planned_grocery_cart()
  return {"status": "success" if ok else "error"}

def save_recipe_grocery_plan_tool(
    plan: Dict[str, Any],
    cart_items: List[Dict[str, Any]] | None = None,
    update_cart: bool = False,
    user_name: str = ""
) -> Dict[str, Any]:
  """
  Save a recipe+ingredient artifact. For grocery requests, also replace
  agent-generated native cart rows with rows derived from the same recipe cards.

  Args:
      plan: Structured recipe+grocery artifact. Include scope, request,
            recipeCards, ingredients, pantryConsiderations, householdSize, notes.
      cart_items: Structured native cart rows derived from the plan's ingredients.
      update_cart: True only when the user asked for groceries/cart/buy/order.
      user_name: Ignored for now. Artifacts are shared household state.
  """
  plan = _ensure_dict(plan)
  cart_items = _ensure_dict(cart_items or [])

  if not isinstance(plan, dict):
    return {"status": "error", "message": f"Expected a dict for plan, got {type(plan).__name__}"}
  if not isinstance(cart_items, list):
    return {"status": "error", "message": f"Expected a list for cart_items, got {type(cart_items).__name__}"}

  saved = db_save_recipe_grocery_plan(plan=plan, cart_items=cart_items, update_cart=bool(update_cart), user_name=user_name)
  if not saved:
    return {"status": "error", "message": "Recipe+grocery plan could not be saved."}

  return {
    "status": "success",
    "message": (
      "Saved recipe+ingredient artifact"
      + (" and updated the native household grocery cart." if update_cart else ".")
    ),
    "plan": saved,
    "cart": saved.get("cart")
  }

def get_recipe_grocery_plan_tool(plan_id: str) -> Dict[str, Any]:
  """
  Fetch a saved recipe+grocery artifact by id.
  """
  plan = db_get_recipe_grocery_plan(str(plan_id).strip())
  if not plan:
    return {"status": "not_found", "plan": None}
  return {"status": "success", "plan": plan}

def list_recipe_grocery_plans_tool(limit: int = 10) -> Dict[str, Any]:
  """
  List recent saved recipe+grocery artifacts.
  """
  try:
    safe_limit = max(1, min(int(limit or 10), 50))
  except (TypeError, ValueError):
    safe_limit = 10
  return {"status": "success", "plans": db_list_recipe_grocery_plans(limit=safe_limit)}


def update_recipe_grocery_plan_tool(
  plan_id: str, plan: Dict[str, Any], cart_items: List[Dict[str, Any]] | None = None,
  update_cart: bool = False,
) -> Dict[str, Any]:
  """Revise an existing recipe artifact in place and update its linked planned rows when requested."""
  saved = db_update_recipe_grocery_plan(plan_id, _ensure_dict(plan), _ensure_dict(cart_items or []), update_cart)
  return {"status": "success", "plan": saved}


def delete_recipe_grocery_plan_tool(plan_id: str) -> Dict[str, Any]:
  """Delete one explicitly identified recipe and its linked agent-generated cart rows."""
  return {"status": "success" if db_delete_recipe_grocery_plan(plan_id) else "not_found"}

async def apply_zepto_brand_memory_to_cart_items(
  items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
  """Preserve Zepto's existing preference-enriched search terms only.

  Instamart never calls this mapper; its dedicated cart agent reads ordering
  preferences directly and reasons over the live MCP catalogue.
  """
  mapped_items: List[Dict[str, Any]] = []
  for item in items:
    item_name = str(item.get("name") or item.get("item") or "").strip()
    mapped = dict(item)
    mapped["search_name"] = item_name
    if item_name:
      memory_result = await search_household_memory_tool(
        f"Household brand, pack, or product preference specifically relevant to {item_name}"
      )
      if memory_result.get("status") == "success" and memory_result.get("memories"):
        text = str(memory_result["memories"][0].get("text") or "").strip()
        if text and len(text) < 160:
          mapped["search_name"] = f"{item_name} {text}"
    mapped_items.append(mapped)
  return mapped_items

def list_grocery_providers_tool() -> Dict[str, Any]:
  """Read provider availability without exposing credentials or mutation tools."""
  return {"status": "success", "providers": provider_registry.descriptors()}


async def get_provider_cart_tool(provider: str = "") -> Dict[str, Any]:
  """
  Read the current ordering-app cart without changing it. The provider is
  optional; omit it to use the ordering app most recently selected in the UI.
  Canonical provider IDs are `swiggy_instamart` and `zepto`; natural aliases
  such as `Instamart` and `Swiggy` are also accepted by the backend.
  """
  from app.main import grocery_checkout_service

  return await grocery_checkout_service.read_cart_from_chat(
    provider_id=str(provider or "").strip(),
  )

async def sync_provider_cart_tool(
  user_request: str,
  provider: str = "",
  cart_item_ids: List[str] | None = None,
  selected_address_id: str = "",
  native_cart_changes: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
  """
  Synchronize the native household grocery cart to an explicitly named
  provider or the provider most recently selected in the UI. This reversible
  operation can never authenticate, change the default provider, or order.
  """
  from app.main import grocery_checkout_service

  request = str(user_request or "").strip()
  if not request:
    return {
      "status": "error",
      "message": "An explicit user request to synchronize an ordering app is required.",
    }
  result = await grocery_checkout_service.sync_from_chat(
    provider_id=str(provider or "").strip(),
    cart_item_ids=[str(value) for value in (cart_item_ids or [])],
    selected_address_id=str(selected_address_id or ""),
    user_instruction=request,
    native_cart_changes=native_cart_changes or [],
  )
  review = result.get("review") or {}
  provider_cart_changed = bool(review) and result.get("status") != "error"
  return {
    "status": result.get("status"),
    "provider": result.get("provider") or provider,
    "matched_item_count": len(review.get("matched_items") or []),
    "unavailable_items": review.get("unavailable_items") or [],
    "selected_address_id": review.get("selected_address_id"),
    "address_selection": result.get("address_selection"),
    "native_cart_changed": bool(result.get("native_cart_changed")),
    "provider_cart_changed": provider_cart_changed,
    "message": review.get("message") or result.get("message") or "Provider cart synchronized.",
    "ui_action": (
      "UPDATE_PROVIDER_CART"
      if provider_cart_changed
      else "UPDATE_GROCERY_CART" if result.get("native_cart_changed") else None
    ),
  }

def get_pantry_state_tool(user_name: str = "") -> Dict[str, Any]:
  """Read pantry rows, optimistic revision, and full-review timestamp."""
  return db_get_pantry_state()


async def patch_pantry_tool(
  changes: List[Dict[str, Any]], expected_revision: int,
  user_name: str = DEFAULT_ACTIVE_USER,
) -> Dict[str, Any]:
  """Atomically add, set, adjust, or remove pantry rows without changing the native cart."""
  from app.pantry_service import mutate_pantry
  parsed = _ensure_dict(changes)
  if not isinstance(parsed, list) or not parsed:
    return {"status": "error", "message": "changes must be a non-empty list"}
  for change in parsed:
    if not isinstance(change, dict):
      return {"status": "error", "message": "each pantry change must be an object"}
    action = str(change.get("action") or "").strip().lower()
    if action in {"add", "set", "adjust"}:
      amount = change.get("amount")
      if amount is None or isinstance(amount, bool):
        return {
          "status": "error",
          "message": f"Pantry {action} requires the observed or requested quantity in amount. No change was saved.",
        }
      try:
        numeric_amount = float(amount)
      except (TypeError, ValueError):
        return {"status": "error", "message": f"Pantry {action} amount must be numeric. No change was saved."}
      if not math.isfinite(numeric_amount):
        return {"status": "error", "message": f"Pantry {action} amount must be finite. No change was saved."}
  result = await mutate_pantry(expected_revision=expected_revision, mode="patch", items=parsed)
  return {"status": "success", **result}


async def reconcile_native_cart_with_pantry_tool(
  expected_revision: int,
  user_name: str = DEFAULT_ACTIVE_USER,
) -> Dict[str, Any]:
  """Explicitly recalculate native purchase quantities from the current pantry."""
  from app.pantry_service import reconcile_native_cart_with_pantry
  result = await reconcile_native_cart_with_pantry(expected_revision=expected_revision)
  return {"status": "success", **result, "ui_action": "UPDATE_GROCERY_CART"}


async def replace_pantry_tool(
  items: List[Dict[str, Any]], expected_revision: int,
  user_name: str = DEFAULT_ACTIVE_USER,
) -> Dict[str, Any]:
  """Request confirmation for a complete pantry replacement, including empty."""
  from app.agent_confirmation import record_confirmation
  parsed = _ensure_dict(items)
  if not isinstance(parsed, list):
    return {"status": "error", "message": "items must be a list"}
  pending = db_create_pending_agent_action(
    active_user=user_name, action_type="replace_pantry",
    payload={"expected_revision": expected_revision, "items": parsed},
    impact_summary={
      "title": "Replace the complete pantry?",
      "message": (
        "This will mark the pantry empty." if not parsed
        else f"This will replace every pantry row with {len(parsed)} observed item(s)."
      ),
      "item_count": len(parsed),
    },
  )
  action = {
    "type": "CONFIRM_DESTRUCTIVE_ACTION", "action_id": pending["id"],
    "impact": pending["impact_summary"],
  }
  record_confirmation(action)
  return {"status": "confirmation_required", **action}

def log_macros_tool(
    user_name: str, 
    meal_name: str, 
    calories: int, 
    protein: int, 
    carbs: int, 
    fat: int, 
    fiber: int = 0,
    quantity: float = 1,
    unit: str = "serving",
    meal_type: str = "",
    consumed_at: str = "",
    tool_context: ToolContext = None,
) -> str:
  """
  Record one food entry. Supply meal_type or consumed_at only when the user states
  that context; otherwise household-local submission time assigns both.
  """
  active_user = _request_user(user_name, tool_context)
  db_log_macros(
    active_user, meal_name, calories, protein, carbs, fat, fiber,
    quantity, unit, meal_type, consumed_at or None,
  )
  return f"Successfully logged meal '{meal_name}' ({calories} kcal) to {active_user}'s journal."

def get_macro_diary_tool(
  user_name: str = "", tool_context: ToolContext = None,
) -> List[Dict[str, Any]]:
  """
  Query Supabase to fetch the daily plate log history and macros for a user.
  """
  return db_get_macro_diary(_request_user(user_name, tool_context))


def update_nutrition_entry_tool(
  user_name: str, entry_id: int, updates: Dict[str, Any],
  tool_context: ToolContext = None,
) -> Dict[str, Any]:
  """Correct one explicitly identified nutrition entry."""
  return {"status": "success", "entry": db_update_macro_entry(
    _request_user(user_name, tool_context), entry_id, _ensure_dict(updates),
  )}


def delete_nutrition_entry_tool(
  user_name: str, entry_id: int, tool_context: ToolContext = None,
) -> Dict[str, Any]:
  """Delete one explicitly identified nutrition entry."""
  return {"status": "success" if db_delete_macro_entry(
    _request_user(user_name, tool_context), entry_id,
  ) else "not_found"}


def clear_nutrition_day_tool(
  user_name: str, diary_date: str = "", tool_context: ToolContext = None,
) -> Dict[str, Any]:
  """Request confirmation before clearing all nutrition entries for one day."""
  from app.agent_confirmation import record_confirmation
  active_user = _request_user(user_name, tool_context)
  pending = db_create_pending_agent_action(
    active_user=active_user, action_type="clear_nutrition_day",
    payload={"user_name": active_user, "date": diary_date},
    impact_summary={
      "title": "Clear this nutrition day?",
      "message": f"This removes every nutrition entry for {active_user} on {diary_date or 'today'}.",
    },
  )
  action = {"type": "CONFIRM_DESTRUCTIVE_ACTION", "action_id": pending["id"], "impact": pending["impact_summary"]}
  record_confirmation(action)
  return {"status": "confirmation_required", **action}


def update_nutrition_targets_tool(
  user_name: str, daily_calorie_target: int = 0,
  protein_target_g: int = 0, carbs_target_g: int = 0, fat_target_g: int = 0,
  tool_context: ToolContext = None,
) -> Dict[str, Any]:
  """Update deterministic personal nutrition goals outside the household profile."""
  updates = {
    key: value for key, value in {
      "daily_calorie_target": daily_calorie_target,
      "protein_target_g": protein_target_g,
      "carbs_target_g": carbs_target_g,
      "fat_target_g": fat_target_g,
    }.items() if value
  }
  return {"status": "success", "nutrition_targets": db_update_nutrition_targets(
    _request_user(user_name, tool_context), updates,
  )}


def update_household_configuration_tool(
  household_size: int = 0, timezone_name: str = "",
) -> Dict[str, Any]:
  """Update factual household configuration; semantic preferences are unavailable."""
  current = db_get_household_profile()
  profile = db_update_household_profile(
    household_size=household_size or current["household_size"],
    timezone_name=timezone_name or current.get("timezone_name"),
  )
  return {"status": "success", "profile": profile}
