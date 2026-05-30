# =====================================================================
# Kitch: ADK 2.0 Web Playground Notebook-style Agent Setup
# =====================================================================
# This script defines the complete Hub-and-Spoke agent topology.
# All Supabase and external REST bindings are replaced with simple,
# in-memory global dictionaries, allowing pure prompt and tool 
# reasoning tests via the native ADK Web playground console.
#
# Authentication for Azure OpenAI:
# Ensure you have your environment variables set before running:
# export AZURE_API_KEY="your-api-key"
# export AZURE_API_BASE="https://your-resource.openai.azure.com/"
# export AZURE_API_VERSION="2024-05-01-preview"
# export AZURE_MODEL_NAME="gpt-5.5"  # Or your deployment name
# =====================================================================

import os
from typing import List, Dict, Any
from google.adk.agents.llm_agent import LlmAgent
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import ToolContext
from google.adk.events import Event
from google.genai.types import Content, Part

# Set Azure OpenAI Credentials directly in python (OpenAI Compatibility Mode)
import os
os.environ["OPENAI_API_KEY"] = "REMOVED_KEY"
os.environ["OPENAI_API_BASE"] = "https://grmopenai-us2.openai.azure.com/openai/v1/"
os.environ["OPENAI_MODEL_NAME"] = "gpt-5.5"  # Your deployment name

# --- 1. Load Azure OpenAI Model via LiteLLM ---
AZURE_MODEL = os.environ.get("OPENAI_MODEL_NAME", "gpt-5.5")
# LiteLLM format for OpenAI Compatibility is "openai/deployment_name"
model_identifier = f"openai/{AZURE_MODEL}"

# Initialize LiteLlm model wrapper.
# Passes reasoning_effort="medium" down to the OpenAI completion API natively.
azure_llm = LiteLlm(
    model=model_identifier,
    api_key="REMOVED_KEY",
    api_base="https://grmopenai-us2.openai.azure.com/openai/v1/",
    custom_llm_provider="openai",
    reasoning_effort="medium"
)

# --- 2. In-Memory Mock Databases ---
# Shared dictionaries representing our database state during local chat runs

IN_MEMORY_SCHEDULE = [
    {"day_of_week": "monday", "meal_type": "breakfast", "recipe_id": "b1"},
    {"day_of_week": "monday", "meal_type": "lunch", "recipe_id": "l1"},
    {"day_of_week": "monday", "meal_type": "dinner", "recipe_id": "d1"}
]

IN_MEMORY_PANTRY = {
    "Archit": [
        {"name": "avocado", "amount": 2.0, "unit": "whole"},
        {"name": "cherry tomatoes", "amount": 6.0, "unit": "pieces"}
    ],
    "Anubhav": [
        {"name": "fresh organic eggs", "amount": 4.0, "unit": "large"}
    ],
    "Naman": [
        {"name": "wild-caught salmon fillet", "amount": 1.0, "unit": "whole"}
    ]
}

IN_MEMORY_MACROS = {
    "Archit": [],
    "Anubhav": [],
    "Naman": []
}

RECIPE_DATABASE = {
  "b1": {
    "id": "b1", "name": "Avocado & Poached Egg Toast", "type": "breakfast",
    "diets": ["balanced", "high-protein"], "prepTime": "10 mins", "calories": 380,
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
    "ingredients": [
      {"name": "Organic black chia seeds", "amount": 3, "unit": "tbsp"},
      {"name": "Unsweetened almond milk", "amount": 0.75, "unit": "cup"},
      {"name": "Full fat coconut milk", "amount": 0.25, "unit": "cup"}
    ]
  },
  "l1": {
    "id": "l1", "name": "Grilled Chicken Quinoa Bowl", "type": "lunch",
    "diets": ["balanced", "high-protein"], "prepTime": "15 mins", "calories": 520,
    "ingredients": [
      {"name": "Free-range chicken breast", "amount": 150, "unit": "g"},
      {"name": "Cooked organic quinoa", "amount": 1, "unit": "cup"}
    ]
  },
  "d1": {
    "id": "d1", "name": "Garlic Butter Salmon & Asparagus", "type": "dinner",
    "diets": ["balanced", "keto", "high-protein"], "prepTime": "20 mins", "calories": 580,
    "ingredients": [
      {"name": "Wild-caught salmon fillet", "amount": 180, "unit": "g"},
      {"name": "Fresh asparagus stalks", "amount": 8, "unit": "stalks"}
    ]
  }
}

# --- 3. Simple In-Memory Mock Tools ---

def get_recipes(diet_preference: str) -> List[Dict[str, Any]]:
  """
  Retrieve recipe objects matching a specific dietary profile.
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
  Fetch the current week's planned meal schedule for the household.
  """
  return IN_MEMORY_SCHEDULE

def save_weekly_plan_tool(weekly_plan: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
  """
  Saves the entire structured 7-day weekly meal plan in memory.
  Accepts either a dict or a JSON-encoded string (LLMs sometimes serialize args).
  """
  import json as _json
  global IN_MEMORY_SCHEDULE

  def _ensure_dict(val):
    """Parse val if it's a JSON string, otherwise return as-is."""
    if isinstance(val, str):
      try:
        return _json.loads(val)
      except _json.JSONDecodeError:
        return val
    return val

  weekly_plan = _ensure_dict(weekly_plan)
  if not isinstance(weekly_plan, dict):
    return {"status": "error", "message": f"Expected a dict for weekly_plan, got {type(weekly_plan).__name__}"}

  IN_MEMORY_SCHEDULE.clear()
  for day, meals in weekly_plan.items():
    meals = _ensure_dict(meals)  # inner values can also be serialised strings
    if not isinstance(meals, dict):
      continue  # skip malformed slots
    for meal_category, recipe_id in meals.items():
      IN_MEMORY_SCHEDULE.append({
          "day_of_week": day.lower().strip(),
          "meal_type": meal_category.lower().strip(),
          "recipe_id": str(recipe_id).strip()
      })
  return {"status": "success", "message": f"Successfully saved {len(IN_MEMORY_SCHEDULE)} meal slots to in-memory weekly schedule."}


def update_single_meal_in_schedule(day: str, meal_category: str, new_recipe_id: str) -> Dict[str, Any]:
  """
  Swaps or modifies a single meal slot in the weekly schedule.
  Always call this whenever a user requests to swap or change a scheduled meal slot.
  """
  # Remove existing slot if matches
  global IN_MEMORY_SCHEDULE
  IN_MEMORY_SCHEDULE = [x for x in IN_MEMORY_SCHEDULE if not (x["day_of_week"] == day.lower() and x["meal_type"] == meal_category.lower())]
  IN_MEMORY_SCHEDULE.append({
      "day_of_week": day.lower().strip(),
      "meal_type": meal_category.lower().strip(),
      "recipe_id": new_recipe_id.strip()
  })
  return {"status": "success", "message": f"Updated slot: {day} {meal_category} set to {new_recipe_id}."}

def get_pantry_stock_tool(user_name: str) -> List[Dict[str, Any]]:
  """
  Fetch current pantry stock levels for a user from in-memory records.
  """
  return IN_MEMORY_PANTRY.get(user_name, [])

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
  return f"Successfully added {amount} {unit} of '{ingredient_name}' to {user_name}'s in-memory pantry."

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
  """
  diary = IN_MEMORY_MACROS.setdefault(user_name, [])
  diary.append({
      "name": meal_name,
      "calories": calories,
      "macros": {"protein": protein, "carbs": carbs, "fat": fat, "fiber": fiber}
  })
  return f"Successfully logged meal '{meal_name}' ({calories} kcal) to {user_name}'s macro diary."

def get_macro_diary_tool(user_name: str) -> List[Dict[str, Any]]:
  """
  Query daily plate log history and macros for a user.
  """
  return IN_MEMORY_MACROS.get(user_name, [])

def get_brand_preference(ingredient: str) -> Dict[str, Any]:
  """
  Factual verification helper representing brand lookup confirmations.
  """
  return {"status": "query_completed", "ingredient": ingredient}

async def set_brand_preference(ingredient: str, branded_sku: str, tool_context: ToolContext = None) -> Dict[str, Any]:
  """
  Instructs the agent to record a brand preference for an ingredient.
  This writes the preference natively to the shared household memory store.
  """
  import time
  
  # Resolve memory service natively
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
    await mem_svc.add_events_to_memory(
        app_name="kitch",
        user_id="shared_household",
        events=[event]
    )
    
  return {
      "status": "success", 
      "message": f"Successfully updated brand preference in memory: '{ingredient}' will map to '{branded_sku}'."
  }

async def export_to_delivery(items: List[Dict[str, Any]], provider: str, tool_context: ToolContext = None) -> str:
  """
  Checkout Exporter: Translates generic required ingredients in your grocery list
  into your favored branded products from the shared memory service, and maps them to MCP delivery formats.
  """
  provider_clean = provider.lower().strip()
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
  
  for item in to_buy:
    name_clean = item["name"].lower().strip()
    branded_name = item["name"]
    
    # Query shared memory natively for brand preferences
    if mem_svc:
      memory_result = await mem_svc.search_memory(
          app_name="kitch",
          user_id="shared_household",
          query=f"preferred brand for {name_clean}"
      )
      if memory_result.memories:
        text_match = memory_result.memories[0].content.parts[0].text
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
    
  return f"Successfully synchronized {len(payload)} items to {provider_clean.capitalize()} MCP cart. Mapped items: {payload}"


# --- 4. Assemble Hub-and-Spoke Spoke Sub-Agents ---

chef_planner = LlmAgent(
    model=azure_llm,
    name="chef_planner",
    description="Handles all requests related to meal planning, suggesting recipes, scaling ingredient quantities, querying the weekly schedule, saving meal plans, and swapping or updating recipe slots on the calendar.",
    instruction=(
        "You are Kitch's Chef Planner sub-agent, the private chef and nutritionist for the household.\n"
        "Your role is to manage plans, recipes, scale ingredient sizes, and execute schedule updates.\n\n"
        "Guidelines:\n"
        "1. Suggest recipes matching user profiles. Scale ingredient weights based on household count.\n"
        "2. To query the current schedule, run 'get_weekly_schedule_tool'.\n"
        "3. To write or update planned schedules, run 'save_weekly_plan_tool' or 'update_single_meal_in_schedule'.\n"
        "   Always run 'update_single_meal_in_schedule' when a user requests to swap or replace planned slots."
    ),
    tools=[
        get_recipes,
        scale_ingredients,
        get_weekly_schedule_tool,
        save_weekly_plan_tool,
        update_single_meal_in_schedule
    ]
)

vision_scanner = LlmAgent(
    model=azure_llm,
    name="vision_scanner",
    description="Processes image uploads of food plates or fridge/pantry shelves. Performs visual ingredient detection, calorie/macronutrient estimation, logging macro intakes, and updating pantry stock based on pictures.",
    instruction=(
        "You are Kitch's Vision Scanner sub-agent, interpreting photo uploads for the household.\n"
        "Your role is to identify visual plate meals or fridge shelves items and proactively log them.\n\n"
        "Guidelines:\n"
        "1. Snapped Plate scans: Estimate dish calories, protein, carbs, fat, and fiber, and pro-actively write them "
        "   using 'log_macros_tool'. Summarize the macro details in clean markdown.\n"
        "2. Fridge shelves scans: List detected ingredients and pro-actively log them to pantry stock using 'add_to_pantry_tool'.\n"
        "3. Always query active user diaries using 'get_macro_diary_tool' or 'get_pantry_stock_tool' to verify state."
    ),
    tools=[
        add_to_pantry_tool,
        log_macros_tool,
        get_pantry_stock_tool,
        get_macro_diary_tool
    ]
)

checkout_exporter = LlmAgent(
    model=azure_llm,
    name="checkout_exporter",
    description="Handles compiling grocery shopping lists, recording housemate brand preferences, mapping generic ingredients to branded products, and exporting/synchronizing final carts to Blinkit or Zepto.",
    instruction=(
        "You are Kitch's Checkout Exporter sub-agent, managing intermediate lists and logistics.\n"
        "Your role is to resolve custom brand rules from memory and sync final carts to MCP providers.\n\n"
        "Guidelines:\n"
        "1. Review generic required items compiled from pantry-subtracted lists.\n"
        "2. Query the shared memory bank for custom choices using 'get_brand_preference'. If a user states brand choices, "
        "   record them permanently using 'set_brand_preference'.\n"
        "3. Connect final mapped carts to Blinkit or Zepto using 'export_to_delivery'."
    ),
    tools=[
        export_to_delivery,
        get_brand_preference,
        set_brand_preference
    ]
)

# --- 5. Construct the Central Coordinator Agent (Parent Orchestrator Hub) ---

kitch_coordinator = LlmAgent(
    model=azure_llm,
    name="kitch_coordinator",
    description="Central parent Coordinator agent managing triage and sub-agent routing.",
    instruction=(
        "You are Kitch, the empathetic, intelligent household orchestrator. You manage the hub-and-spoke multi-agent team.\n"
        "You coordinate culinary schedules, pantry stock, and checkout logistics for household members: Archit, Anubhav, and Naman.\n\n"
        "Context details:\n"
        "- Active Housemate chatting: {user:profile_name?}\n"
        "- User Dietary Preference: {user:dietary_profile?}\n"
        "- Household Size: {app:household_size?}\n\n"
        "Triage & Routing guidelines:\n"
        "1. Converse empathetically with the active user, answering culinary questions and guiding discussions.\n"
        "2. If the user asks to plan meals, swap scheduled recipes, or scale portions, immediately hand over to 'chef_planner'.\n"
        "3. If the user uploads fridge scans or food plate snaps, immediately hand over to 'vision_scanner'.\n"
        "4. If the user requests to synchronize list carts, maps generic items to brands, or checkout, hand over to 'checkout_exporter'."
    ),
    sub_agents=[chef_planner, vision_scanner, checkout_exporter]
)

# --- 6. Define Background Context Compactor and Root ADK App ---

compactor_llm = LiteLlm(
    model=model_identifier,
    api_key="REMOVED_KEY",
    api_base="https://grmopenai-us2.openai.azure.com/openai/v1/",
    custom_llm_provider="openai"
)
my_summarizer = LlmEventSummarizer(llm=compactor_llm)

# Expose the final root "app" object that ADK's web loader expects
app = App(
    name="kitch_debug",
    root_agent=kitch_coordinator,
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=4,
        overlap_size=1,
        summarizer=my_summarizer
    )
)
