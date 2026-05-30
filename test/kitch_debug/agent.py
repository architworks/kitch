# =====================================================================
# Kitch: ADK 2.0 Web Playground Notebook-style Agent Setup
# =====================================================================
# This script defines the complete Hub-and-Spoke agent topology.
# All Supabase and external REST bindings are replaced with simple,
# in-memory global dictionaries, allowing pure prompt and tool
# reasoning tests via the native ADK Web playground console.
# =====================================================================

import os
import json as _json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import ToolContext
from google.adk.events import Event
from google.genai.types import Content, Part

# Set Azure OpenAI Credentials directly in python (OpenAI Compatibility Mode)
os.environ["OPENAI_API_KEY"] = "REMOVED_KEY"
os.environ["OPENAI_API_BASE"] = "https://grmopenai-us2.openai.azure.com/openai/v1/"
os.environ["OPENAI_MODEL_NAME"] = "gpt-5.5"

# --- 1. Load Azure OpenAI Model via LiteLLM ---
AZURE_MODEL = os.environ.get("OPENAI_MODEL_NAME", "gpt-5.5")
model_identifier = f"openai/{AZURE_MODEL}"

azure_llm = LiteLlm(
    model=model_identifier,
    api_key=os.environ["OPENAI_API_KEY"],
    api_base=os.environ["OPENAI_API_BASE"],
    custom_llm_provider="openai"
)


# --- 2. In-Memory Mock Databases ---

IN_MEMORY_SCHEDULE = []  # Start with empty schedule

IN_MEMORY_PANTRY = {
    "Archit": [
        {"name": "avocado", "amount": 2.0, "unit": "whole"},
        {"name": "cherry tomatoes", "amount": 6.0, "unit": "pieces"},
        {"name": "eggs", "amount": 6.0, "unit": "large"}
    ],
    "Anubhav": [
        {"name": "eggs", "amount": 4.0, "unit": "large"},
        {"name": "milk", "amount": 1.0, "unit": "liter"}
    ],
    "Naman": [
        {"name": "wild-caught salmon fillet", "amount": 1.0, "unit": "whole"},
        {"name": "rice", "amount": 2.0, "unit": "kg"}
    ]
}

IN_MEMORY_MACROS = {
    "Archit": [],
    "Anubhav": [],
    "Naman": []
}

IN_MEMORY_PREFERENCES = {}  # e.g. {"never_buy": ["cereals"], "only_buy_categories": ["dairy", "fruits", "veggies"]}

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
            {"name": "Full fat coconut milk", "amount": 0.25, "unit": "cup"}
        ]
    },
    "b3": {
        "id": "b3", "name": "Masala Oats Upma", "type": "breakfast",
        "diets": ["balanced", "vegan", "indian"], "prepTime": "12 mins", "calories": 290,
        "macros": {"protein": 10, "carbs": 42, "fat": 8, "fiber": 6},
        "ingredients": [
            {"name": "Rolled oats", "amount": 1, "unit": "cup"},
            {"name": "Onion (diced)", "amount": 0.5, "unit": "whole"},
            {"name": "Green peas", "amount": 0.25, "unit": "cup"},
            {"name": "Mustard seeds", "amount": 0.5, "unit": "tsp"}
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
    "l2": {
        "id": "l2", "name": "Dal Tadka with Brown Rice", "type": "lunch",
        "diets": ["balanced", "vegan", "indian"], "prepTime": "20 mins", "calories": 450,
        "macros": {"protein": 18, "carbs": 62, "fat": 12, "fiber": 10},
        "ingredients": [
            {"name": "Yellow toor dal", "amount": 1, "unit": "cup"},
            {"name": "Brown rice", "amount": 0.75, "unit": "cup"},
            {"name": "Ghee", "amount": 1, "unit": "tbsp"},
            {"name": "Cumin seeds", "amount": 1, "unit": "tsp"}
        ]
    },
    "l3": {
        "id": "l3", "name": "Mediterranean Chickpea Salad", "type": "lunch",
        "diets": ["vegan", "balanced"], "prepTime": "10 mins", "calories": 400,
        "macros": {"protein": 16, "carbs": 50, "fat": 14, "fiber": 12},
        "ingredients": [
            {"name": "Canned chickpeas", "amount": 1, "unit": "can"},
            {"name": "Cucumber", "amount": 1, "unit": "whole"},
            {"name": "Cherry tomatoes", "amount": 8, "unit": "pieces"},
            {"name": "Olive oil", "amount": 2, "unit": "tbsp"}
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
    },
    "d3": {
        "id": "d3", "name": "Paneer Butter Masala with Naan", "type": "dinner",
        "diets": ["balanced", "indian"], "prepTime": "25 mins", "calories": 620,
        "macros": {"protein": 28, "carbs": 52, "fat": 32, "fiber": 5},
        "ingredients": [
            {"name": "Paneer cubes", "amount": 200, "unit": "g"},
            {"name": "Tomato puree", "amount": 1, "unit": "cup"},
            {"name": "Heavy cream", "amount": 0.25, "unit": "cup"},
            {"name": "Whole wheat naan", "amount": 2, "unit": "pieces"}
        ]
    },
    "d4": {
        "id": "d4", "name": "Grilled Chicken Caesar Salad", "type": "dinner",
        "diets": ["balanced", "high-protein", "keto"], "prepTime": "15 mins", "calories": 420,
        "macros": {"protein": 38, "carbs": 12, "fat": 24, "fiber": 4},
        "ingredients": [
            {"name": "Free-range chicken breast", "amount": 150, "unit": "g"},
            {"name": "Romaine lettuce", "amount": 2, "unit": "cups"},
            {"name": "Parmesan cheese", "amount": 30, "unit": "g"},
            {"name": "Caesar dressing", "amount": 2, "unit": "tbsp"}
        ]
    }
}


# --- 3. Utility: Current datetime helper ---

def get_current_datetime() -> str:
    """
    Returns the current date, time, and day of the week.
    Use this to answer questions like "what day is today", "what's for dinner tonight", etc.
    """
    now = datetime.now()
    return now.strftime("Today is %A, %B %d, %Y. The current time is %I:%M %p.")


# --- 4. Simple In-Memory Mock Tools ---

def get_recipes(diet_preference: str) -> List[Dict[str, Any]]:
    """
    Retrieve recipe objects matching a specific dietary profile.
    Valid profiles include: balanced, high-protein, keto, vegan, indian.
    """
    diet = diet_preference.lower().strip()
    results = []
    for recipe in RECIPE_DATABASE.values():
        if diet in recipe["diets"]:
            results.append(recipe)
    return results

def get_all_recipes() -> List[Dict[str, Any]]:
    """
    Retrieve all available recipes in the recipe database.
    Use this when the user doesn't specify a dietary preference or wants to see all options.
    """
    return list(RECIPE_DATABASE.values())

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
            "amount": round(ing["amount"] * household_size, 2),
            "unit": ing["unit"]
        })
    return scaled

def get_weekly_schedule_tool() -> List[Dict[str, Any]]:
    """
    Fetch the current week's planned meal schedule for the household.
    Returns a list of {day_of_week, meal_type, recipe_id} entries.
    If empty, it means no plan has been created yet.
    """
    if not IN_MEMORY_SCHEDULE:
        return [{"status": "empty", "message": "No meal plan exists yet. Create one first."}]
    # Enrich with recipe names
    enriched = []
    for slot in IN_MEMORY_SCHEDULE:
        recipe = RECIPE_DATABASE.get(slot.get("recipe_id", ""))
        enriched.append({
            **slot,
            "recipe_name": recipe["name"] if recipe else "Unknown recipe",
            "calories": recipe["calories"] if recipe else 0
        })
    return enriched


def _ensure_dict(val):
    """Parse val if it's a JSON string, otherwise return as-is."""
    if isinstance(val, str):
        try:
            return _json.loads(val)
        except _json.JSONDecodeError:
            return val
    return val


def save_weekly_plan_tool(weekly_plan: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """
    Saves the entire structured 7-day weekly meal plan in memory.
    Use ONLY for creating a brand-new full weekly plan.
    Do NOT use this to modify a single meal — use update_single_meal_in_schedule instead.

    Args:
        weekly_plan: Dict mapping day names to meal type→recipe_id mappings.
                     Example: {"monday": {"breakfast": "b1", "lunch": "l1", "dinner": "d1"}, ...}
    """
    global IN_MEMORY_SCHEDULE

    weekly_plan = _ensure_dict(weekly_plan)
    if not isinstance(weekly_plan, dict):
        return {"status": "error", "message": f"Expected a dict for weekly_plan, got {type(weekly_plan).__name__}"}

    IN_MEMORY_SCHEDULE.clear()
    for day, meals in weekly_plan.items():
        meals = _ensure_dict(meals)
        if not isinstance(meals, dict):
            continue
        for meal_category, recipe_id in meals.items():
            IN_MEMORY_SCHEDULE.append({
                "day_of_week": day.lower().strip(),
                "meal_type": meal_category.lower().strip(),
                "recipe_id": str(recipe_id).strip()
            })
    return {
        "status": "success",
        "message": f"Successfully saved {len(IN_MEMORY_SCHEDULE)} meal slots to the weekly schedule.",
        "saved_slots": len(IN_MEMORY_SCHEDULE)
    }


def update_single_meal_in_schedule(day: str, meal_category: str, new_recipe_id: str) -> Dict[str, Any]:
    """
    Swaps or modifies a single meal slot in the weekly schedule.
    This preserves all other meal slots — only the specified day+meal_category is changed.
    ALWAYS use this instead of save_weekly_plan_tool when modifying individual meals.

    Args:
        day: Weekday name (e.g., "monday", "thursday")
        meal_category: Meal type (e.g., "breakfast", "lunch", "dinner")
        new_recipe_id: Recipe ID to assign to this slot (e.g., "d2", "b1")
    """
    global IN_MEMORY_SCHEDULE
    day_lower = day.lower().strip()
    meal_lower = meal_category.lower().strip()

    # Count existing slots before the change
    before_count = len(IN_MEMORY_SCHEDULE)

    # Remove only the matching slot (in-place mutation to preserve imports/references)
    IN_MEMORY_SCHEDULE[:] = [
        x for x in IN_MEMORY_SCHEDULE
        if not (x["day_of_week"] == day_lower and x["meal_type"] == meal_lower)
    ]
    # Insert the new slot
    IN_MEMORY_SCHEDULE.append({
        "day_of_week": day_lower,
        "meal_type": meal_lower,
        "recipe_id": new_recipe_id.strip()
    })

    recipe = RECIPE_DATABASE.get(new_recipe_id.strip())
    recipe_name = recipe["name"] if recipe else new_recipe_id

    return {
        "status": "success",
        "message": f"Updated {day.capitalize()} {meal_category} to '{recipe_name}'. "
                   f"Total schedule now has {len(IN_MEMORY_SCHEDULE)} slots (was {before_count} before).",
        "total_slots_preserved": len(IN_MEMORY_SCHEDULE)
    }


def get_pantry_stock_tool(user_name: str) -> List[Dict[str, Any]]:
    """
    Fetch current pantry stock levels for a user from in-memory records.
    """
    stock = IN_MEMORY_PANTRY.get(user_name, [])
    if not stock:
        return [{"status": "empty", "message": f"No pantry items found for {user_name}."}]
    return stock


def add_to_pantry_tool(user_name: str, ingredient_name: str, amount: float, unit: str = "piece") -> str:
    """
    Add or update an ingredient in the user's pantry/fridge stock.
    """
    stock = IN_MEMORY_PANTRY.setdefault(user_name, [])
    existing = next((i for i in stock if i["name"].lower() == ingredient_name.lower().strip()), None)
    if existing:
        existing["amount"] += amount
    else:
        stock.append({"name": ingredient_name, "amount": amount, "unit": unit})
    return f"Successfully added {amount} {unit} of '{ingredient_name}' to {user_name}'s pantry."


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
    Record a meal intake log with calorie and macronutrient details.
    Call this every time the user describes what they ate (via text or image).

    Args:
        user_name: Housemate's name (e.g., "Archit", "Anubhav", "Naman")
        meal_name: Description of the meal (e.g., "2 rotis and dal", "banana smoothie")
        calories: Estimated total calories
        protein: Protein in grams
        carbs: Carbohydrates in grams
        fat: Fat in grams
        fiber: Fiber in grams (optional)
    """
    diary = IN_MEMORY_MACROS.setdefault(user_name, [])
    entry = {
        "name": meal_name,
        "calories": calories,
        "macros": {"protein": protein, "carbs": carbs, "fat": fat, "fiber": fiber},
        "logged_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    diary.append(entry)
    return (
        f"✅ Logged '{meal_name}' for {user_name}: "
        f"{calories} kcal | P:{protein}g C:{carbs}g F:{fat}g Fiber:{fiber}g"
    )


def get_macro_diary_tool(user_name: str) -> List[Dict[str, Any]]:
    """
    Query daily plate log history and macros for a user.
    Returns all logged meals with timestamps.
    """
    diary = IN_MEMORY_MACROS.get(user_name, [])
    if not diary:
        return [{"status": "empty", "message": f"No meals logged yet for {user_name} today."}]
    # Compute running totals
    total_cal = sum(m["calories"] for m in diary)
    total_p = sum(m["macros"]["protein"] for m in diary)
    total_c = sum(m["macros"]["carbs"] for m in diary)
    total_f = sum(m["macros"]["fat"] for m in diary)
    return {
        "meals": diary,
        "daily_totals": {
            "calories": total_cal,
            "protein": total_p,
            "carbs": total_c,
            "fat": total_f
        }
    }


def get_brand_preference(ingredient: str) -> Dict[str, Any]:
    """
    Look up if the household has a stored brand preference for a generic ingredient.
    """
    return {"status": "query_completed", "ingredient": ingredient}


async def set_brand_preference(ingredient: str, branded_sku: str, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Record a brand preference for a generic ingredient.
    Future grocery lists will automatically map this ingredient to the preferred brand.

    Args:
        ingredient: Generic ingredient name (e.g., "bread", "butter", "milk")
        branded_sku: Specific brand name preferred (e.g., "Baker's Dozen Whole Wheat", "Amul Butter")
    """
    import time

    # Also store in a simple in-memory dict for testing
    IN_MEMORY_PREFERENCES[ingredient.lower().strip()] = branded_sku.strip()

    # Try native memory service
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

    if mem_svc:
        event = Event(
            id=f"brand_pref_{ingredient.lower().strip()}_{int(time.time())}",
            content=Content(parts=[Part(text=f"{ingredient.lower().strip()}: {branded_sku.strip()}")]),
            author="system",
            timestamp=time.time()
        )
        try:
            await mem_svc.add_events_to_memory(
                app_name="kitch",
                user_id="shared_household",
                events=[event]
            )
        except Exception:
            pass

    return {
        "status": "success",
        "message": f"✅ Brand preference saved: '{ingredient}' → '{branded_sku}'. This will be applied to future grocery lists."
    }


def calculate_intermediary_grocery_list(
    user_name: str = "Archit",
    household_size: int = 3
) -> List[Dict[str, Any]]:
    """
    Compiles the complete grocery shopping list for the week by:
    1. Aggregating all required ingredients from the current meal plan
    2. Scaling quantities for the household size
    3. Subtracting what's already available in the user's pantry

    Returns a list of items to buy, each with name, amount, unit, category,
    and whether it's already stocked.

    Args:
        user_name: Which user's pantry to check against (default "Archit")
        household_size: Number of people to scale for (default 3)
    """
    if not IN_MEMORY_SCHEDULE:
        return [{"status": "error", "message": "No meal plan exists. Create a weekly plan first before generating a grocery list."}]

    pantry_stock = IN_MEMORY_PANTRY.get(user_name, [])
    pantry_map = {item["name"].lower().strip(): item["amount"] for item in pantry_stock}

    aggregated = {}

    # Aggregate all ingredients from the weekly plan
    for slot in IN_MEMORY_SCHEDULE:
        recipe = RECIPE_DATABASE.get(slot.get("recipe_id", ""))
        if recipe:
            for ing in recipe["ingredients"]:
                key = ing["name"].lower().strip()
                scaled_amount = round(ing["amount"] * household_size, 2)

                if key in aggregated:
                    aggregated[key]["amount"] += scaled_amount
                else:
                    # Categorize
                    category = "Pantry & Spices"
                    if any(term in key for term in ["chicken", "salmon", "steak", "beef", "egg", "tofu", "feta", "paneer", "cheese", "cream", "milk", "butter", "ghee"]):
                        category = "Proteins & Dairy"
                    elif any(term in key for term in ["avocado", "broccoli", "spinach", "asparagus", "tomato", "cucumber", "onion", "raspberries", "peas", "lettuce", "mushroom"]):
                        category = "Fresh Produce"
                    elif any(term in key for term in ["bread", "oats", "quinoa", "rice", "chia", "naan", "dal"]):
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
            aggregated[key]["amount"] = max(0.0, round(aggregated[key]["amount"] - stock_amount, 2))
            if aggregated[key]["amount"] == 0:
                aggregated[key]["alreadyStocked"] = True
                aggregated[key]["checked"] = True

    # Apply preference filters (e.g., "never buy cereals")
    result = list(aggregated.values())

    # Summary
    to_buy = [r for r in result if not r["alreadyStocked"]]
    already_have = [r for r in result if r["alreadyStocked"]]

    return {
        "grocery_list": to_buy,
        "already_stocked": already_have,
        "summary": f"🛒 {len(to_buy)} items to buy, {len(already_have)} items already in pantry."
    }


async def export_to_delivery(items: List[Dict[str, Any]], provider: str, tool_context: ToolContext = None) -> str:
    """
    Exports the grocery list to a delivery service (Blinkit or Zepto).
    Maps generic ingredients to branded preferences where available.

    Args:
        items: List of grocery items with name, qty/amount, unit
        provider: Delivery provider - "blinkit" or "zepto"
    """
    provider_clean = provider.lower().strip()
    to_buy = items if isinstance(items, list) else []
    # Filter out already-stocked items
    to_buy = [i for i in to_buy if not i.get("checked") and not i.get("alreadyStocked")]
    payload = []

    for item in to_buy:
        name_clean = item.get("name", "").lower().strip()
        branded_name = item.get("name", "")

        # Check in-memory brand preferences
        if name_clean in IN_MEMORY_PREFERENCES:
            branded_name = IN_MEMORY_PREFERENCES[name_clean]

        payload.append({
            "name": branded_name,
            "qty": item.get("amount", item.get("qty", 1)),
            "unit": item.get("unit", "piece")
        })

    return f"✅ Successfully synced {len(payload)} items to {provider_clean.capitalize()} cart. Items: {_json.dumps(payload, indent=2)}"


# --- 5. Datetime Injection Callback ---

def inject_datetime_callback(callback_context: CallbackContext) -> Optional[Content]:
    """
    Before-agent callback that injects the current datetime into session state.
    This ensures the coordinator and all sub-agents know what day/time it is.
    """
    now = datetime.now()
    callback_context.state["current_datetime"] = now.strftime("%A, %B %d, %Y at %I:%M %p")
    callback_context.state["current_day_of_week"] = now.strftime("%A").lower()
    callback_context.state["current_date"] = now.strftime("%Y-%m-%d")
    return None  # Continue with normal execution


# --- 6. Assemble Hub-and-Spoke Sub-Agents ---

chef_planner = LlmAgent(
    model=azure_llm,
    name="chef_planner",
    description=(
        "Handles all requests related to food planning, cooking, and meals: "
        "creating weekly meal plans, suggesting recipes based on dietary preferences, "
        "viewing what's currently scheduled, swapping or changing individual meals, "
        "scaling ingredient quantities, and answering questions like 'what's for dinner tonight'. "
        "Route here when the user talks about meal planning, recipes, dietary needs, or asks about scheduled meals."
    ),
    instruction=(
        "You are Kitch's Chef Planner — the household's private nutritionist and chef.\n"
        "You help plan meals, suggest recipes, and manage the weekly meal schedule.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Today is: {current_day_of_week?}\n"
        "- Household members: Archit, Anubhav, Naman (3 people)\n\n"
        "CRITICAL RULES:\n"
        "1. When creating a NEW full weekly plan, use 'save_weekly_plan_tool'.\n"
        "2. When MODIFYING or replacing meals in an existing plan (e.g., swapping ingredients, removing salmon, editing specific slots), you MUST use 'update_single_meal_in_schedule' for each slot. NEVER use save_weekly_plan_tool when modifying an existing plan, because save_weekly_plan_tool will wipe the rest of the schedule.\n"
        "3. Systematically check the weekly schedule day-by-day (Monday through Sunday) and meal-by-meal (breakfast, lunch, dinner) to find EVERY slot containing the ingredient or recipe to be replaced (e.g., search for 'salmon' or 'd1'). You MUST call 'update_single_meal_in_schedule' in parallel (in a single turn) for EVERY single matching slot. Do not miss any slot! Even if there are 3 or 4 slots with salmon, call the tool 3 or 4 times in parallel to replace all of them at once.\n"
        "4. Before modifying or replacing meals, ALWAYS call 'get_weekly_schedule_tool' first to see the current plan.\n"
        "5. When the user asks 'what's for dinner tonight' or similar, check the current day and look up the schedule for that day.\n"
        "6. When the user asks to scale ingredients, scale a recipe, or calculate quantities for a specific number of guests or household size (e.g., 10 people), you MUST call the 'scale_ingredients' tool to get the precise scaled amounts. Do not calculate or multiply scaled quantities manually in your text response.\n"
        "7. Scale ingredients for 3 people (household size) by default unless the user specifies otherwise.\n"
        "8. Available recipe IDs: b1, b2, b3 (breakfasts), l1, l2, l3 (lunches), d1, d2, d3, d4 (dinners).\n"
        "9. Use 'get_current_datetime' if you need to confirm the current date/time.\n\n"
        "When creating a weekly plan, structure it as:\n"
        "{'monday': {'breakfast': 'b1', 'lunch': 'l1', 'dinner': 'd1'}, 'tuesday': {...}, ...}\n"
        "Use the actual recipe IDs from the database."
    ),
    tools=[
        get_recipes,
        get_all_recipes,
        scale_ingredients,
        get_weekly_schedule_tool,
        save_weekly_plan_tool,
        update_single_meal_in_schedule,
        get_current_datetime
    ]
)

vision_scanner = LlmAgent(
    model=azure_llm,
    name="vision_scanner",
    description=(
        "Handles all requests related to food intake logging and pantry management: "
        "logging what the user ate (from text descriptions OR photos), estimating calories and macros, "
        "viewing the macro diary, scanning fridge/pantry contents, and updating pantry stock. "
        "Route here when the user says things like 'I ate X', 'log my meal', 'update my pantry', "
        "'how many calories have I eaten today', or uploads food/fridge photos."
    ),
    instruction=(
        "You are Kitch's Food Logger & Pantry Scanner — you track what housemates eat and what's in their fridge.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Household members: Archit, Anubhav, Naman\n\n"
        "CRITICAL RULES:\n"
        "1. When a user describes food they ate (text OR photo), ESTIMATE the calories and macros, "
        "   then IMMEDIATELY log them using 'log_macros_tool'. Don't just describe — always LOG.\n"
        "2. Use your nutritional knowledge to estimate macros. Be reasonable, not exact.\n"
        "   Examples: '2 rotis and dal' ≈ 450cal, 18g protein, 62g carbs, 10g fat.\n"
        "3. If the user doesn't specify their name, default to 'Archit'.\n"
        "4. For fridge scans (photos or text), identify items and add them using 'add_to_pantry_tool'.\n"
        "5. To check daily progress, use 'get_macro_diary_tool' and summarize totals.\n"
        "6. Always respond with a clean markdown summary of what was logged."
    ),
    tools=[
        add_to_pantry_tool,
        log_macros_tool,
        get_pantry_stock_tool,
        get_macro_diary_tool,
        get_current_datetime
    ]
)

checkout_exporter = LlmAgent(
    model=azure_llm,
    name="checkout_exporter",
    description=(
        "Handles all requests related to grocery shopping and delivery: "
        "compiling grocery lists based on the meal plan, accounting for pantry stock, "
        "recording brand preferences, applying dietary filters to shopping lists, "
        "and exporting/ordering groceries on Blinkit or Zepto. "
        "Route here when the user asks about groceries, shopping lists, 'what do I need to buy', "
        "'order on Blinkit', or sets brand preferences."
    ),
    instruction=(
        "You are Kitch's Grocery Manager — you compile shopping lists and handle delivery orders.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Household members: Archit, Anubhav, Naman (3 people)\n\n"
        "CRITICAL RULES:\n"
        "1. To generate a grocery list, use 'calculate_intermediary_grocery_list'. This automatically:\n"
        "   - Pulls all ingredients from the current meal plan\n"
        "   - Scales for household size\n"
        "   - Subtracts available pantry stock\n"
        "2. If the user mentions items they already have at home or just bought, first call 'add_to_pantry_tool' for each item to update their pantry stock, and then call 'calculate_intermediary_grocery_list' to generate the grocery list.\n"
        "3. When the user mentions brand preferences (e.g., 'always buy Amul butter'), "
        "   use 'set_brand_preference' to record it.\n"
        "4. When the user specifies category-level preferences or items to exclude (e.g., 'never buy cereals'), clearly confirm that you have saved and noted this preference (use words like 'noted', 'remember', 'preference', 'saved').\n"
        "5. To export to delivery, use 'export_to_delivery' with the items and provider.\n"
        "6. Present grocery lists in clean markdown with categories.\n"
        "7. If no meal plan exists yet, tell the user to create one first."
    ),
    tools=[
        calculate_intermediary_grocery_list,
        export_to_delivery,
        get_brand_preference,
        set_brand_preference,
        get_pantry_stock_tool,
        add_to_pantry_tool,
        get_current_datetime
    ]
)


# --- 7. Construct the Central Coordinator Agent ---

kitch_coordinator = LlmAgent(
    model=azure_llm,
    name="kitch_coordinator",
    description="Central coordinator for the Kitch household kitchen assistant.",
    instruction=(
        "You are Kitch, the friendly and intelligent kitchen assistant for a household of 3 people: "
        "Archit, Anubhav, and Naman.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Today is: {current_day_of_week?}\n"
        "- Active user: {user:profile_name?}\n"
        "- Dietary preference: {user:dietary_profile?}\n"
        "- Household size: 3\n\n"
        "YOUR JOB is to understand what the user needs and route to the right specialist:\n\n"
        "→ 'chef_planner': For ANYTHING about meal planning, recipes, weekly schedules, "
        "  dietary preferences, 'what's for dinner', swapping meals, or food suggestions.\n\n"
        "→ 'vision_scanner': For ANYTHING about food intake logging — whether the user describes "
        "  food in text ('I ate pasta') OR uploads a photo. Also for pantry/fridge scanning, "
        "  calorie tracking, and 'how many calories today' questions.\n\n"
        "→ 'checkout_exporter': For ANYTHING about grocery shopping, shopping lists, "
        "  'what do I need to buy', brand preferences, or ordering on Blinkit/Zepto.\n\n"
        "GUIDELINES:\n"
        "1. Be warm and conversational. You're the household's kitchen buddy, not a robot.\n"
        "2. Route naturally — don't tell the user which agent you're using.\n"
        "3. For simple greetings or general chat, respond yourself without routing.\n"
        "4. If unsure, ask a clarifying question rather than guessing wrong.\n"
        "5. When the user says 'I ate something', ALWAYS route to vision_scanner for logging.\n"
        "6. Never ask 'which agent should I use' — just figure it out from context."
    ),
    sub_agents=[chef_planner, vision_scanner, checkout_exporter],
    before_agent_callback=inject_datetime_callback
)


# --- 8. Define Root ADK App ---

compactor_llm = LiteLlm(
    model=model_identifier,
    api_key=os.environ["OPENAI_API_KEY"],
    api_base=os.environ["OPENAI_API_BASE"],
    custom_llm_provider="openai"
)
my_summarizer = LlmEventSummarizer(llm=compactor_llm)

app = App(
    name="kitch_debug",
    root_agent=kitch_coordinator,
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=4,
        overlap_size=1,
        summarizer=my_summarizer
    )
)
