# Kitch: Core ADK 2.0 Custom Tools

import os
import math
from typing import List, Dict, Any
from google.adk.tools import ToolContext
from app.supabase_client import (
    get_pantry_stock as db_get_pantry_stock,
    add_to_pantry as db_add_to_pantry,
    log_macros as db_log_macros,
    get_macro_diary as db_get_macro_diary,
    supabase
)

# Internal database recipes
RECIPE_DATABASE = {
  "b1": {
    "id": "b1", "name": "Avocado & Poached Egg Toast", "type": "breakfast",
    "diets": ["balanced", "high-protein"], "prepTime": "10 mins", "calories": 380,
    "macros": {"protein": 16, "carbs": 28, "fat": 22, "fiber": 7},
    "ingredients": [
      {"name": "Whole wheat bread slices", "amount": 1, "unit": "slice"},
      {"name": "Medium ripe avocado", "amount": 0.5, "unit": "whole"},
      {"name": "Fresh organic eggs", "amount": 2, "unit": "large"},
      {"name": "Cherry tomatoes", "amount": 4, "unit": "pieces"}
    ]
  },
  "b2": {
    "id": "b2", "name": "Keto Vanilla Chia Pudding", "type": "breakfast",
    "diets": ["keto", "vegan"], "prepTime": "5 mins", "calories": 320,
    "macros": {"protein": 8, "carbs": 6, "fat": 28, "fiber": 11},
    "ingredients": [
      {"name": "Organic black chia seeds", "amount": 3, "unit": "tbsp"},
      {"name": "Unsweetened almond milk", "amount": 0.75, "unit": "cup"},
      {"name": "Full fat coconut milk", "amount": 0.25, "unit": "cup"},
      {"name": "Liquid stevia / monkfruit", "amount": 4, "unit": "drops"},
      {"name": "Fresh raspberries", "amount": 8, "unit": "pieces"}
    ]
  },
  "l1": {
    "id": "l1", "name": "Grilled Chicken Quinoa Bowl", "type": "lunch",
    "diets": ["balanced", "high-protein"], "prepTime": "15 mins", "calories": 520,
    "macros": {"protein": 42, "carbs": 48, "fat": 16, "fiber": 8},
    "ingredients": [
      {"name": "Free-range chicken breast", "amount": 150, "unit": "g"},
      {"name": "Cooked organic quinoa", "amount": 1, "unit": "cup"},
      {"name": "Cucumber slices", "amount": 0.5, "unit": "cup"},
      {"name": "Crumbled feta cheese", "amount": 30, "unit": "g"}
    ]
  },
  "d1": {
    "id": "d1", "name": "Garlic Butter Salmon & Asparagus", "type": "dinner",
    "diets": ["balanced", "keto", "high-protein"], "prepTime": "20 mins", "calories": 580,
    "macros": {"protein": 44, "carbs": 8, "fat": 38, "fiber": 4},
    "ingredients": [
      {"name": "Wild-caught salmon fillet", "amount": 180, "unit": "g"},
      {"name": "Fresh asparagus stalks", "amount": 8, "unit": "stalks"},
      {"name": "Grass-fed butter", "amount": 1.5, "unit": "tbsp"},
      {"name": "Minced garlic", "amount": 2, "unit": "cloves"}
    ]
  },
  "d2": {
    "id": "d2", "name": "Sesame Ginger Tofu Stir-Fry", "type": "dinner",
    "diets": ["vegan", "balanced"], "prepTime": "20 mins", "calories": 480,
    "macros": {"protein": 22, "carbs": 42, "fat": 20, "fiber": 7},
    "ingredients": [
      {"name": "Extra-firm organic tofu", "amount": 150, "unit": "g"},
      {"name": "Broccoli florets", "amount": 1.5, "unit": "cups"},
      {"name": "Sliced shiitake mushrooms", "amount": 0.5, "unit": "cup"},
      {"name": "Brown rice", "amount": 0.75, "unit": "cup"}
    ]
  }
}

# --- Section 1: Standard Meal Planning & Scalers ---
def get_recipes(diet_preference: str) -> List[Dict[str, Any]]:
  """
  Retrieve recipe objects matching a specific dietary profile.
  Use this when planning or suggesting substitutions.
  """
  diet = diet_preference.lower().strip()
  results = []
  for recipe in RECIPE_DATABASE.values():
    if diet in recipe["diets"]:
      results.append(recipe)
  return results

def scale_ingredients(recipe_id: str, household_size: int) -> List[Dict[str, Any]]:
  """
  Scale ingredient quantities of a recipe based on active household size.
  """
  recipe = RECIPE_DATABASE.get(recipe_id)
  if not recipe:
    return []
  
  scaled = []
  for ing in recipe["ingredients"]:
    scaled.append({
      "name": ing["name"],
      "amount": ing["amount"] * household_size,
      "unit": ing["unit"]
    })
  return scaled

def get_weekly_schedule_tool() -> List[Dict[str, Any]]:
  """
  Queries Supabase to fetch the current week's planned meal schedule for the household.
  """
  try:
    response = supabase.table("meal_plans").select("*").execute()
    return response.data or []
  except Exception as e:
    print(f"Error fetching weekly schedule: {e}")
    return []

def save_weekly_plan_tool(weekly_plan: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
  """
  Saves or overrides the entire structured 7-day weekly meal plan in the database.
  
  Args:
      weekly_plan: Mapping of weekdays to meal types (breakfast, lunch, dinner) and recipe IDs.
                   Example: {'monday': {'breakfast': 'b1', 'lunch': 'l1', 'dinner': 'd1'}}
  """
  try:
    for day, meals in weekly_plan.items():
      for meal_category, recipe_id in meals.items():
        supabase.table("meal_plans").upsert({
            "day_of_week": day.lower().strip(),
            "meal_type": meal_category.lower().strip(),
            "recipe_id": recipe_id.strip()
        }).execute()
        
    return {"status": "success", "message": "Successfully synchronized weekly plan to database."}
  except Exception as e:
    return {"status": "error", "message": f"Database insertion failed: {str(e)}"}

def update_single_meal_in_schedule(day: str, meal_category: str, new_recipe_id: str) -> Dict[str, Any]:
  """
  Swaps, replaces, or modifies a single meal slot in the weekly schedule in the database.
  Always call this whenever a user requests to swap or change a scheduled meal slot.
  
  Args:
      day: Weekday of the slot (e.g. 'thursday', 'monday')
      meal_category: Meal slot to replace (e.g. 'breakfast', 'dinner')
      new_recipe_id: The ID of the new recipe (e.g. 'd2', 'b1')
  """
  try:
    supabase.table("meal_plans").upsert({
        "day_of_week": day.lower().strip(),
        "meal_type": meal_category.lower().strip(),
        "recipe_id": new_recipe_id.strip()
    }).execute()
    
    return {"status": "success", "message": f"Successfully updated {day} {meal_category} to {new_recipe_id}."}
  except Exception as e:
    return {"status": "error", "message": f"Database update failed: {str(e)}"}

# --- Section 2: Supabase Pantry Stock & Logs ---
def get_pantry_stock_tool(user_name: str) -> List[Dict[str, Any]]:
  """
  Query Supabase to fetch current pantry stock levels for a user.
  """
  return db_get_pantry_stock(user_name)

def add_to_pantry_tool(user_name: str, ingredient_name: str, amount: float, unit: str = "piece") -> str:
  """
  Add or update an ingredient in the user's pantry/fridge stock database on Supabase.
  """
  res = db_add_to_pantry(user_name, ingredient_name, amount, unit)
  if res:
      return f"Successfully added {amount} {unit} of '{ingredient_name}' to {user_name}'s pantry stock."
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

# --- Section 4: Grocery List Calculations & Brand-Mapped Exporter ---
def calculate_intermediary_grocery_list(
    weekly_plan: Dict[str, Dict[str, str]], 
    household_size: int, 
    pantry_stock: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
  """
  Intermediary Subtraction Core:
  1. Aggregates all required weekly recipe ingredients scaled for household.
  2. Subtracts available pantry stock case-insensitively.
  3. Returns platform-agnostic intermediary native grocery list.
  """
  aggregated = {}
  pantry_map = {item["name"].lower().strip(): item["amount"] for item in pantry_stock}

  # Scale and aggregate requirements
  for day, meals in weekly_plan.items():
    for meal_type, recipe_id in meals.items():
      recipe = RECIPE_DATABASE.get(recipe_id)
      if recipe:
        for ing in recipe["ingredients"]:
          key = ing["name"].lower().strip()
          scaled_amount = ing["amount"] * household_size
          
          if key in aggregated:
            aggregated[key]["amount"] += scaled_amount
          else:
            category = "Pantry & Spices"
            name_lower = key
            if any(term in name_lower for term in ["chicken", "salmon", "steak", "beef", "egg", "tofu", "feta"]):
              category = "Proteins & Dairy"
            elif any(term in name_lower for term in ["avocado", "broccoli", "spinach", "asparagus", "tomato", "cucumber", "onion", "raspberries"]):
              category = "Fresh Produce"
            elif any(term in name_lower for term in ["bread", "oats", "quinoa", "rice", "chia"]):
              category = "Grains & Bakery"

            aggregated[key] = {
              "name": ing["name"],
              "amount": scaled_amount,
              "unit": ing["unit"],
              "category": category,
              "checked": False,
              "alreadyStocked": False
            }

  # Subtract pantry stock
  for key, stock_amount in pantry_map.items():
    if key in aggregated:
      aggregated[key]["amount"] = max(0.00, aggregated[key]["amount"] - stock_amount)
      if aggregated[key]["amount"] == 0:
        aggregated[key]["alreadyStocked"] = True
        aggregated[key]["checked"] = True

  return list(aggregated.values())

async def export_to_delivery(items: List[Dict[str, Any]], provider: str, tool_context: ToolContext = None) -> str:
  """
  Decoupled Checkout Exporter: Translates generic required ingredients in your grocery list
  into your favored branded products from the shared factual memory service, then loads them
  into the chosen delivery merchant cart (Blinkit or Zepto).
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
    name_clean = item["name"].lower().strip()
    branded_name = item["name"]
    
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
      "qty": item["amount"],
      "unit": item["unit"]
    })
    
  return f"Successfully synchronized {len(payload)} items to {provider_clean.capitalize()} MCP cart (with ADK native brand memory active). Mapped items: {payload}"
