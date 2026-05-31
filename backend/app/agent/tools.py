# Kitch: Core ADK 2.0 Custom Tools

import json as _json
from typing import List, Dict, Any
from google.adk.tools import ToolContext
from app.household_config import DEFAULT_ACTIVE_USER, get_household_profile_id
from app.supabase_client import (
    get_pantry_stock as db_get_pantry_stock,
    add_to_pantry as db_add_to_pantry,
    log_macros as db_log_macros,
    get_macro_diary as db_get_macro_diary,
    get_grocery_cart as db_get_grocery_cart,
    replace_planned_grocery_cart as db_replace_planned_grocery_cart,
    clear_planned_grocery_cart as db_clear_planned_grocery_cart,
    supabase
)
from app.providers.zepto import ZeptoProviderAdapter

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
  from datetime import datetime, timedelta
  now = datetime.now()
  days_until_next_monday = ((7 - now.weekday()) % 7) or 7
  planning_start = now + timedelta(days=days_until_next_monday)
  planning_end = planning_start + timedelta(days=6)
  return (
    now.strftime("Today is %A, %B %d, %Y. The current time is %I:%M %p. ")
    + f"The upcoming planning week runs from {planning_start.strftime('%A, %B %d, %Y')} "
    + f"through {planning_end.strftime('%A, %B %d, %Y')}."
  )

def get_weekly_schedule_dict(user_name: str = "") -> Dict[str, Dict[str, str]]:
  """
  Queries Supabase to fetch the household's current planned meal schedule.
  Transforms DB rows into frontend's expected dictionary mapping weekdays to meal categories and recipe names.
  """
  try:
    profile_id = get_household_profile_id()
    response = supabase.table("meal_plans").select("*").eq("profile_id", profile_id).execute()
    
    plan_dict = {}
    for row in response.data or []:
      day = row.get("day", "").strip().capitalize()
      if not day:
        continue
      plan_dict[day] = {
        "breakfast": row.get("breakfast_recipe_id") or "",
        "lunch": row.get("lunch_recipe_id") or "",
        "dinner": row.get("dinner_recipe_id") or "",
        "snack": row.get("snack_recipe_id") or ""
      }
      
    # Fill in missing days with empty meal slots
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
      if day not in plan_dict:
        plan_dict[day] = {
          "breakfast": "",
          "lunch": "",
          "dinner": "",
          "snack": ""
        }
    return plan_dict
  except Exception as e:
    print(f"Error fetching weekly schedule dict: {e}")
    return {}

def get_weekly_schedule_tool(user_name: str = "") -> Dict[str, Dict[str, str]]:
  """
  Fetch the current week's planned meal schedule for the household.
  Returns a dictionary mapping day of week to meal slots and their recipe names.
  If slots are empty, it means no meal plan has been created yet.
  """
  return get_weekly_schedule_dict(user_name)

def save_weekly_plan_tool(weekly_plan: Dict[str, Dict[str, str]], user_name: str = "") -> Dict[str, Any]:
  """
  Saves the entire structured 7-day weekly meal plan to the database.
  Each day's meals map directly to the recipe name string (e.g. "Avocado Toast", "Spaghetti Carbonara").
  Do NOT use this to modify a single meal — use update_single_meal_in_schedule instead.
  
  Args:
      weekly_plan: Dict mapping day names to meal category -> recipe name mappings.
                   Example: {"Monday": {"breakfast": "Scrambled Eggs", "lunch": "Salad", "dinner": "Tofu Stir-fry"}, ...}
      user_name: Ignored for now. Meal plans are shared by the configured household.
  """
  try:
    profile_id = get_household_profile_id()
    weekly_plan = _ensure_dict(weekly_plan)
    
    if not isinstance(weekly_plan, dict):
      return {"status": "error", "message": f"Expected a dict for weekly_plan, got {type(weekly_plan).__name__}"}
      
    for day, meals in weekly_plan.items():
      day_clean = day.strip().capitalize()
      meals = _ensure_dict(meals)
      if not isinstance(meals, dict):
        continue
        
      breakfast = meals.get("breakfast", "")
      lunch = meals.get("lunch", "")
      dinner = meals.get("dinner", "")
      snack = meals.get("snack", "")
      
      supabase.table("meal_plans").upsert({
          "profile_id": profile_id,
          "day": day_clean,
          "breakfast_recipe_id": str(breakfast).strip(),
          "lunch_recipe_id": str(lunch).strip(),
          "dinner_recipe_id": str(dinner).strip(),
          "snack_recipe_id": str(snack).strip()
      }, on_conflict="profile_id,day").execute()
      
    return {"status": "success", "message": "Successfully synchronized weekly plan to database."}
  except Exception as e:
    return {"status": "error", "message": f"Database insertion failed: {str(e)}"}

def update_single_meal_in_schedule(day: str, meal_category: str, new_recipe_name: str, user_name: str = "") -> Dict[str, Any]:
  """
  Swaps, replaces, or modifies a single meal slot in the weekly schedule in the database.
  Always call this whenever a user requests to swap or change a scheduled meal slot.
  This preserves all other meal slots — only the specified day+meal_category is changed.
  
  Args:
      day: Weekday of the slot (e.g. 'Thursday', 'Monday')
      meal_category: Meal slot to replace (e.g. 'breakfast', 'dinner')
      new_recipe_name: The name of the new recipe (e.g. 'Garlic Salmon', 'Keto Chia Pudding')
      user_name: Ignored for now. Meal plans are shared by the configured household.
  """
  try:
    profile_id = get_household_profile_id()
    day_clean = day.strip().capitalize()
    meal_category = meal_category.lower().strip()
    
    # Check if there is an existing plan row for this day
    response = supabase.table("meal_plans").select("*").eq("profile_id", profile_id).eq("day", day_clean).execute()
    
    data = {
        "profile_id": profile_id,
        "day": day_clean
    }
    
    if response.data:
        # Row exists, update target column and carry over other columns
        row = response.data[0]
        data["id"] = row.get("id")
        data["breakfast_recipe_id"] = row.get("breakfast_recipe_id")
        data["lunch_recipe_id"] = row.get("lunch_recipe_id")
        data["dinner_recipe_id"] = row.get("dinner_recipe_id")
        data["snack_recipe_id"] = row.get("snack_recipe_id")
        
    col_map = {
        "breakfast": "breakfast_recipe_id",
        "lunch": "lunch_recipe_id",
        "dinner": "dinner_recipe_id",
        "snack": "snack_recipe_id"
    }
    
    target_col = col_map.get(meal_category)
    if not target_col:
        return {"status": "error", "message": f"Invalid meal category: {meal_category}"}
        
    data[target_col] = str(new_recipe_name).strip()
    
    supabase.table("meal_plans").upsert(data, on_conflict="profile_id,day").execute()
    return {"status": "success", "message": f"Successfully updated {day_clean} {meal_category} to '{new_recipe_name}'."}
  except Exception as e:
    return {"status": "error", "message": f"Database update failed: {str(e)}"}

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

async def sync_native_cart_to_zepto_tool(tool_context: ToolContext = None) -> Dict[str, Any]:
  """
  Replace the user's Zepto cart with unchecked, non-stocked items from Kitch's
  native household grocery cart. This does not place an order.
  """
  cart_items = [
    item for item in db_get_grocery_cart()
    if not item.get("checked") and not item.get("alreadyStocked")
  ]
  mapped_items = await _apply_brand_memory_to_items(cart_items, tool_context)
  return await ZeptoProviderAdapter().sync_cart(mapped_items)

async def get_zepto_cart_tool() -> Dict[str, Any]:
  """
  Fetch the current Zepto cart through the configured Zepto MCP connection.
  """
  return await ZeptoProviderAdapter().get_cart()

async def place_zepto_order_tool(confirmation_token: str = "") -> Dict[str, Any]:
  """
  Agents cannot place real Zepto orders from chat. The backend HTTP endpoint
  owns final approval token validation after the frontend approval button.
  """
  return {
    "status": "error",
    "message": "Final frontend approval is required before placing a real Zepto order. Use the Zepto review button in the app."
  }

def add_to_pantry_tool(user_name: str = DEFAULT_ACTIVE_USER, ingredient_name: str = "", amount: float = 1, unit: str = "piece") -> str:
  """
  Add or update an ingredient in the shared household pantry/fridge stock database on Supabase.
  """
  res = db_add_to_pantry(user_name, ingredient_name, amount, unit)
  if res:
      return f"Successfully added {amount} {unit} of '{ingredient_name}' to the shared household pantry stock."
  return "Failed to add item to database."

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
  res = db_log_macros(user_name, meal_name, calories, protein, carbs, fat, fiber)
  if res:
      return f"Successfully logged meal '{meal_name}' ({calories} kcal) to {user_name}'s journal."
  return "Failed to log meal macros to database."

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
        "message": f"Successfully updated your household brand preference: '{ingredient}' will map to '{branded_sku}'."
    }
  except Exception as e:
    import traceback
    print(f"*** set_brand_preference failed with: {e} ***")
    traceback.print_exc()
    return {"status": "error", "message": f"Failed to set brand preference in memory: {str(e)}"}

# --- Section 4: Grocery List Delivery Exporter ---
async def export_to_delivery(items: List[Dict[str, Any]], provider: str, tool_context: ToolContext = None) -> str:
  """
  Decoupled Checkout Exporter: Translates generic required ingredients in your grocery list
  into your favored branded products from the shared factual memory service, then returns
  a provider-shaped payload preview. Live merchant cart insertion is intentionally deferred.
  """
  print(f"*** export_to_delivery called with items={items}, provider='{provider}' ***")
  provider_clean = provider.lower().strip()
  if provider_clean not in ["blinkit", "zepto"]:
    raise ValueError(f"Merchant provider: {provider} is currently unsupported.")
  
  to_buy = [i for i in items if not i.get("checked") and not i.get("alreadyStocked")]
  payload = []
  
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
  
  for item in to_buy:
    item_name = item.get("name") or item.get("item")
    amount = item.get("amount", item.get("quantity", item.get("qty", 1)))
    unit = item.get("unit", "piece")

    if not item_name:
      continue

    name_clean = str(item_name).lower().strip()
    branded_name = str(item_name).strip()
    
    # Query shared household memory natively for brand preferences
    if mem_svc:
      memory_result = await mem_svc.search_memory(
          app_name="kitch",
          user_id="shared_household",
          query=f"preferred brand for {name_clean}"
      )
      if memory_result.memories:
        # Resolve the top matched text part as our brand replacement
        text_match = memory_result.memories[0].content.parts[0].text
        # Safety check: ensure it matches a brand phrasing
        if text_match and len(text_match) < 100:
          if ":" in text_match:
            branded_name = text_match.split(":", 1)[1].strip()
          else:
            branded_name = text_match
          
    payload.append({
      "name": branded_name,
      "qty": amount,
      "unit": unit
    })
    
  return (
    f"Prepared {len(payload)} legacy {provider_clean.capitalize()} preview items with ADK native brand memory active. "
    f"This preview tool does not modify provider carts. For live Zepto cart sync, use sync_native_cart_to_zepto_tool. "
    f"Mapped items: {payload}"
  )
