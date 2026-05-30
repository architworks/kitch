# Kitch: Core ADK 2.0 Custom Tools

import os
import math
from typing import List, Dict, Any
from app.supabase_client import (
    get_pantry_stock as db_get_pantry_stock,
    add_to_pantry as db_add_to_pantry,
    log_macros as db_log_macros,
    get_macro_diary as db_get_macro_diary
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

# --- Section 3: Brand Preference File Memory Core ---
def get_brand_preferences() -> Dict[str, str]:
  """
  Retrieve your custom brand preferences mapping from the local brand_preferences.md file.
  Use this to find specific brand names preferred by the household.
  """
  file_path = "/Users/dynamiterdx/Documents/Personal Projects/diet_planner/brand_preferences.md"
  preferences = {}
  if os.path.exists(file_path):
    with open(file_path, "r") as f:
      for line in f:
        if line.startswith("- **"):
          parts = line.strip().split("**: ")
          if len(parts) == 2:
            key = parts[0].replace("- **", "").strip().lower()
            val = parts[1].strip()
            preferences[key] = val
  return preferences

def set_brand_preference(ingredient: str, branded_sku: str) -> Dict[str, Any]:
  """
  Record or update a custom brand preference for a generic ingredient in the local brand_preferences.md file.
  Always call this tool whenever a user asks to remember a certain ingredient brand, or preference for orders.
  Args:
      ingredient: The generic name of the ingredient (e.g. 'milk')
      branded_sku: The exact preferred branded choice (e.g. 'Country Delight Pasteurized Milk 1L')
  """
  file_path = "/Users/dynamiterdx/Documents/Personal Projects/diet_planner/brand_preferences.md"
  preferences = get_brand_preferences()
  preferences[ingredient.lower().strip()] = branded_sku
  
  with open(file_path, "w") as f:
    f.write("# Kitch Brand Preferences\n\n")
    for key, val in sorted(preferences.items()):
      f.write(f"- **{key}**: {val}\n")
      
  return {"status": "success", "message": f"Successfully updated '{ingredient}' brand preference to '{branded_sku}'."}

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

def export_to_delivery(items: List[Dict[str, Any]], provider: str = "blinkit") -> str:
  """
  Decoupled Checkout Exporter: Translates generic required ingredients in your grocery list
  into your favored branded products from the brand_preferences.md file, then loads them
  into the chosen delivery merchant cart (Blinkit or Zepto).
  """
  provider_clean = provider.lower().strip()
  if provider_clean not in ["blinkit", "zepto"]:
    raise ValueError(f"Merchant provider: {provider} is currently unsupported.")
  
  brand_map = get_brand_preferences()
  to_buy = [i for i in items if not i.get("checked") and not i.get("alreadyStocked")]
  
  payload = []
  for item in to_buy:
    name_clean = item["name"].lower().strip()
    # Check if a custom brand preference exists in episodic memory
    branded_name = brand_map.get(name_clean, item["name"])
    
    payload.append({
      "name": branded_name,
      "qty": item["amount"],
      "unit": item["unit"]
    })
    
  return f"Successfully synchronized {len(payload)} items to {provider_clean.capitalize()} MCP cart (with brand preferences active)."
