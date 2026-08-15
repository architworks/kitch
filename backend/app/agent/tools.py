# Kitch: Core ADK 2.0 Custom Tools

import json as _json
from typing import List, Dict, Any
from google.adk.tools import ToolContext
from app.household_config import DEFAULT_ACTIVE_USER
from app.planning_calendar import calendar_context, parse_iso_date
from app.supabase_client import (
    apply_meal_plan_edits as db_apply_meal_plan_edits,
    get_household_timezone,
    get_meal_schedule as db_get_meal_schedule,
    replace_meal_plan_range as db_replace_meal_plan_range,
    get_pantry_stock as db_get_pantry_stock,
    add_to_pantry as db_add_to_pantry,
    log_macros as db_log_macros,
    get_macro_diary as db_get_macro_diary,
    get_grocery_cart as db_get_grocery_cart,
    replace_planned_grocery_cart as db_replace_planned_grocery_cart,
    clear_planned_grocery_cart as db_clear_planned_grocery_cart,
    save_recipe_grocery_plan as db_save_recipe_grocery_plan,
    get_recipe_grocery_plan as db_get_recipe_grocery_plan,
    list_recipe_grocery_plans as db_list_recipe_grocery_plans,
)
from app.checkout_drafts import draft_row_to_review
from app.providers.registry import provider_registry
from app.supabase_client import get_provider_checkout_draft

# --- Safety Parsing Helper ---
def _ensure_dict(val):
  """Parse val if it's a JSON string, otherwise return as-is."""
  if isinstance(val, str):
    try:
      return _json.loads(val)
    except _json.JSONDecodeError:
      return val
  return val

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

def save_grocery_cart_tool(items: List[Dict[str, Any]], user_name: str = "") -> Dict[str, Any]:
  """
  Replace the shared household grocery cart with a structured provider-agnostic list.
  Call this after compiling groceries so the Pantry/Grocery page updates.

  Args:
      items: List of grocery item dictionaries. Each item should include name,
             amount, unit, and category. Optional flags: checked, alreadyStocked.
      user_name: Ignored for now. Grocery cart is shared by the configured household.
  """
  items = _ensure_dict(items)
  if not isinstance(items, list):
    return {"status": "error", "message": f"Expected a list of grocery items, got {type(items).__name__}"}

  saved = db_replace_planned_grocery_cart(items)
  return {
    "status": "success",
    "message": f"Saved {len(saved)} grocery cart items for the shared household.",
    "items": saved
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

def _resolve_memory_service(tool_context: ToolContext = None):
  mem_svc = None
  if tool_context:
    if hasattr(tool_context, "get_invocation_context"):
      try:
        mem_svc = tool_context.get_invocation_context().memory_service
      except Exception:
        pass
    elif hasattr(tool_context, "_invocation_context"):
      try:
        mem_svc = tool_context._invocation_context.memory_service
      except Exception:
        pass

  if not mem_svc:
    try:
      from app.agent.core import memory_service as fallback_mem_svc
      mem_svc = fallback_mem_svc
    except ImportError:
      pass
  return mem_svc

async def set_household_food_preference_tool(preference_text: str, tool_context: ToolContext = None) -> Dict[str, Any]:
  """
  Store a household-level food preference, dislike, exclusion, or planning style
  in intentionally ephemeral, process-local ADK memory as plain text.
  """
  preference = str(preference_text or "").strip()
  if not preference:
    return {"status": "error", "message": "No preference text was provided."}

  try:
    from google.adk.events import Event
    from google.genai.types import Content, Part
    import time

    mem_svc = _resolve_memory_service(tool_context)
    if mem_svc:
      event = Event(
          id=f"food_pref_{int(time.time())}",
          content=Content(parts=[Part(text=f"food_preference: {preference}")]),
          author="system",
          timestamp=time.time()
      )
      await mem_svc.add_events_to_memory(
          app_name="kitch",
          user_id="shared_household",
          events=[event]
      )

    return {
      "status": "success",
      "message": f"Stored household food preference in ephemeral process-local memory: {preference}"
    }
  except Exception as e:
    return {"status": "error", "message": f"Failed to save household food preference: {str(e)}"}

async def search_household_food_preferences_tool(query: str, tool_context: ToolContext = None) -> Dict[str, Any]:
  """
  Search household food preferences before recipe and grocery generation.
  """
  mem_svc = _resolve_memory_service(tool_context)
  if not mem_svc:
    return {"status": "success", "preferences": []}

  try:
    memory_result = await mem_svc.search_memory(
        app_name="kitch",
        user_id="shared_household",
        query=f"household food preference recipe grocery dislike avoid prefer {query}"
    )
    preferences = []
    for memory in memory_result.memories or []:
      try:
        text = memory.content.parts[0].text
      except Exception:
        text = ""
      if text:
        preferences.append(text)
    return {"status": "success", "preferences": preferences}
  except Exception as e:
    return {"status": "error", "message": f"Failed to search household food preferences: {str(e)}", "preferences": []}

def list_grocery_providers_tool() -> Dict[str, Any]:
  """Read provider availability without exposing credentials or mutation tools."""
  return {"status": "success", "providers": provider_registry.descriptors()}


def get_grocery_checkout_status_tool(provider: str) -> Dict[str, Any]:
  """Read a sanitized durable checkout status for the requested provider."""
  descriptor = provider_registry.descriptor(provider)
  if provider not in {"zepto", "swiggy_instamart"}:
    return {"status": "unavailable", "provider": provider}
  row = get_provider_checkout_draft(provider, str(descriptor["environment"]))
  review = draft_row_to_review(row)
  if not review or not review.get("native_items"):
    return {"status": "empty", "provider": provider}
  return {
    "status": review.get("status"),
    "provider": provider,
    "last_validated_at": review.get("last_validated_at"),
    "matched_item_count": len(review.get("matched_items") or []),
    "unavailable_item_count": len(review.get("unavailable_items") or []),
    "can_place_order": bool(review.get("can_place_order")),
    "order_blockers": review.get("order_blockers") or [],
  }

def add_to_pantry_tool(user_name: str = DEFAULT_ACTIVE_USER, ingredient_name: str = "", amount: float = 1, unit: str = "piece") -> str:
  """
  Add or update an ingredient in the shared household pantry/fridge stock database on Supabase.
  """
  db_add_to_pantry(user_name, ingredient_name, amount, unit)
  return f"Successfully added {amount} {unit} of '{ingredient_name}' to the shared household pantry stock."

def log_macros_tool(
    user_name: str, 
    meal_name: str, 
    calories: int, 
    protein: int, 
    carbs: int, 
    fat: int, 
    fiber: int = 0
) -> str:
  """
  Record a meal intake log with calorie and macronutrient details into the user's Supabase journal.
  """
  db_log_macros(user_name, meal_name, calories, protein, carbs, fat, fiber)
  return f"Successfully logged meal '{meal_name}' ({calories} kcal) to {user_name}'s journal."

def get_macro_diary_tool(user_name: str) -> List[Dict[str, Any]]:
  """
  Query Supabase to fetch the daily plate log history and macros for a user.
  """
  return db_get_macro_diary(user_name)

# --- Section 3: Brand Preference Memory Management (ADK Native Memory) ---
def get_brand_preference(ingredient: str) -> Dict[str, Any]:
  """
  Factual verification tool helper representing brand lookup confirmations.
  """
  return {"status": "query_completed", "ingredient": ingredient}

async def _apply_brand_memory_to_items(items: List[Dict[str, Any]], tool_context: ToolContext = None) -> List[Dict[str, Any]]:
  """
  Adds a provider search name to each native cart row using household brand memory.
  The native item name remains generic.
  """
  mem_svc = None
  if tool_context:
    if hasattr(tool_context, "get_invocation_context"):
      try:
        mem_svc = tool_context.get_invocation_context().memory_service
      except Exception:
        pass
    elif hasattr(tool_context, "_invocation_context"):
      try:
        mem_svc = tool_context._invocation_context.memory_service
      except Exception:
        pass

  if not mem_svc:
    try:
      from app.agent.core import memory_service as fallback_mem_svc
      mem_svc = fallback_mem_svc
    except ImportError:
      pass

  mapped_items = []
  for item in items:
    item_name = str(item.get("name") or item.get("item") or "").strip()
    mapped = dict(item)
    mapped["search_name"] = item_name

    if mem_svc and item_name:
      try:
        memory_result = await mem_svc.search_memory(
            app_name="kitch",
            user_id="shared_household",
            query=f"preferred brand for {item_name.lower()}"
        )
        if memory_result.memories:
          text_match = memory_result.memories[0].content.parts[0].text
          if text_match and len(text_match) < 100:
            mapped["search_name"] = text_match.split(":", 1)[1].strip() if ":" in text_match else text_match.strip()
      except Exception:
        pass

    mapped_items.append(mapped)

  return mapped_items

async def apply_brand_memory_to_cart_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  """
  Public helper for non-agent API routes that need provider search terms with
  household brand preferences applied.
  """
  return await _apply_brand_memory_to_items(items, None)

async def set_brand_preference(ingredient: str, branded_sku: str, tool_context: ToolContext = None) -> Dict[str, Any]:
  """
  Instructs the agent to record a brand preference for an ingredient. 
  This writes the preference natively to the shared household memory store.
  
  Args:
      ingredient: Generic ingredient name (e.g. 'bread')
      branded_sku: Specific brand preferred (e.g. 'Bakers Dozen Whole Wheat')
  """
  print(f"*** set_brand_preference called with ingredient='{ingredient}', branded_sku='{branded_sku}' ***")
  try:
    from google.adk.events import Event
    from google.genai.types import Content, Part
    import time
    
    # Resolve memory service
    mem_svc = None
    if tool_context:
      if hasattr(tool_context, "get_invocation_context"):
        try:
          mem_svc = tool_context.get_invocation_context().memory_service
        except Exception:
          pass
      elif hasattr(tool_context, "_invocation_context"):
        try:
          mem_svc = tool_context._invocation_context.memory_service
        except Exception:
          pass
          
    if not mem_svc:
      try:
        from app.agent.core import memory_service as fallback_mem_svc
        mem_svc = fallback_mem_svc
      except ImportError:
        pass
        
    if mem_svc:
      event = Event(
          id=f"brand_pref_{ingredient.lower().strip()}_{int(time.time())}",
          content=Content(parts=[Part(text=f"{ingredient.lower().strip()}: {branded_sku.strip()}")]),
          author="system",
          timestamp=time.time()
      )
      await mem_svc.add_events_to_memory(
          app_name="kitch",
          user_id="shared_household",
          events=[event]
      )
      
    return {
        "status": "success", 
        "message": (
          "Updated ephemeral process-local brand preference memory: "
          f"'{ingredient}' will map to '{branded_sku}'."
        )
    }
  except Exception as e:
    import traceback
    print(f"*** set_brand_preference failed with: {e} ***")
    traceback.print_exc()
    return {"status": "error", "message": f"Failed to set brand preference in memory: {str(e)}"}
