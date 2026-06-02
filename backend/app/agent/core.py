# Kitch: ADK 2.0 Multi-Agent Assembly & Session Orchestrator Core

import os
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models.google_llm import Gemini
from google.genai.types import Content, Part
from app.household_config import DEFAULT_HOUSEHOLD_SIZE, household_members_text

from .tools import (
    get_weekly_schedule_tool,
    save_weekly_plan_tool,
    update_single_meal_in_schedule,
    get_pantry_stock_tool,
    add_to_pantry_tool,
    log_macros_tool,
    get_macro_diary_tool,
    get_grocery_cart_tool,
    clear_planned_grocery_cart_tool,
    save_recipe_grocery_plan_tool,
    get_recipe_grocery_plan_tool,
    list_recipe_grocery_plans_tool,
    set_household_food_preference_tool,
    search_household_food_preferences_tool,
    get_current_datetime
)
from google.adk.agents.callback_context import CallbackContext
from typing import Optional

from dotenv import load_dotenv

# 0. Load model provider credentials dynamically from gitignored .env file
load_dotenv()

def build_llm_model():
    """
    Builds the model adapter from environment configuration.

    Production can use native ADK Gemini by setting:
    - KITCH_LLM_PROVIDER=gemini
    - KITCH_LLM_MODEL=gemini-flash-latest
    - GOOGLE_API_KEY=...
    - GOOGLE_GENAI_USE_VERTEXAI=FALSE

    Local OpenAI-compatible testing remains supported through:
    - KITCH_LLM_PROVIDER=openai_compatible, or omitted
    - OPENAI_MODEL_NAME / OPENAI_API_KEY / OPENAI_API_BASE
    """
    provider = os.environ.get("KITCH_LLM_PROVIDER", os.environ.get("LLM_PROVIDER", "openai_compatible")).strip().lower()

    if provider in {"gemini", "google", "google_ai_studio", "vertexai"}:
        return Gemini(
            model=os.environ.get("KITCH_LLM_MODEL", os.environ.get("GOOGLE_MODEL_NAME", "gemini-flash-latest")),
            base_url=os.environ.get("KITCH_LLM_API_BASE", os.environ.get("GOOGLE_API_BASE"))
        )

    model_name = os.environ.get("KITCH_LLM_MODEL", os.environ.get("OPENAI_MODEL_NAME", "gpt-5.5")).strip()
    model_identifier = (
        model_name
        if "/" in model_name
        else f"{os.environ.get('KITCH_LLM_LITELLM_PREFIX', 'openai')}/{model_name}"
    )

    from google.adk.models.lite_llm import LiteLlm

    return LiteLlm(
        model=model_identifier,
        api_key=os.environ.get("KITCH_LLM_API_KEY", os.environ.get("OPENAI_API_KEY")),
        api_base=os.environ.get("KITCH_LLM_API_BASE", os.environ.get("OPENAI_API_BASE")),
        custom_llm_provider=os.environ.get("KITCH_LLM_CUSTOM_PROVIDER", "openai")
    )

configured_llm = build_llm_model()

# 1. Initialize modern, high-performance in-memory prototyping services
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()
HOUSEHOLD_MEMBERS_TEXT = household_members_text()
HOUSEHOLD_SIZE_TEXT = str(DEFAULT_HOUSEHOLD_SIZE)

# 1.5 Datetime Injection Callback
def inject_datetime_callback(callback_context: CallbackContext) -> Optional[Content]:
    """
    Before-agent callback that injects the current datetime into session state.
    This ensures the coordinator and all sub-agents know what day/time it is.
    """
    from datetime import datetime, timedelta
    now = datetime.now()
    days_until_next_monday = ((7 - now.weekday()) % 7) or 7
    planning_start = now + timedelta(days=days_until_next_monday)
    planning_dates = []
    for index in range(7):
        date = planning_start + timedelta(days=index)
        planning_dates.append(date.strftime("%A, %B %d, %Y"))

    callback_context.state["current_datetime"] = now.strftime("%A, %B %d, %Y at %I:%M %p")
    callback_context.state["current_day_of_week"] = now.strftime("%A").lower()
    callback_context.state["current_date"] = now.strftime("%Y-%m-%d")
    callback_context.state["planning_week_start"] = planning_start.strftime("%Y-%m-%d")
    callback_context.state["planning_week_end"] = (planning_start + timedelta(days=6)).strftime("%Y-%m-%d")
    callback_context.state["planning_week_dates"] = "; ".join(planning_dates)
    return None  # Continue execution

# 3. Assemble the 3-Spoke Specialized Spoke Sub-Agents
chef_planner = LlmAgent(
    model=configured_llm,
    name="chef_planner",
    description=(
        "Handles lightweight household meal scheduling: "
        "creating weekly meal plans as meal-name schedules, suggesting meal names based on dietary preferences, "
        "viewing what's currently scheduled, swapping or changing individual scheduled meals, "
        "and answering questions like 'what's for dinner tonight'. "
        "Route here when the user talks about meal plan schedules, swaps, or planned meals."
    ),
    instruction=(
        "You are Kitch's Chef Planner — the household's lightweight meal scheduler.\n"
        "You plan meal names and manage the weekly schedule. Detailed recipes, ingredients, and grocery cart generation belong to the recipe_grocery_planner.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Today is: {current_day_of_week?}\n"
        "- Household members: " + HOUSEHOLD_MEMBERS_TEXT + " (" + HOUSEHOLD_SIZE_TEXT + " people)\n"
        "- Household size: {app:household_size?}\n"
        "- Dietary preference: {user:dietary_profile?}\n"
        "- Upcoming planning week: {planning_week_dates?}\n\n"
        "CRITICAL RULES:\n"
        "1. Meal plans store dynamically generated MEAL NAME STRINGS only. Do not pull from a static database, and do not use recipe IDs (like b1, d2).\n"
        "2. When creating a NEW full weekly plan for 'next week' or 'the week', plan the upcoming Monday-Sunday window listed above. In your chat response, label each day with its exact date. Use 'save_weekly_plan_tool' to save the plan. The saved keys are still weekdays, and the values are breakfast, lunch, and dinner mapping directly to actual meal NAME strings (e.g., 'Avocado Toast with Poached Eggs' or 'Spaghetti Pomodoro'). Do not plan snacks.\n"
        "3. When MODIFYING or replacing meals in an existing plan, you MUST use 'update_single_meal_in_schedule'. Set the 'new_recipe_name' argument to the actual text name of the recipe. This preserves the rest of the schedule.\n"
        "4. Before modifying or replacing meals, ALWAYS call 'get_weekly_schedule_tool' first to see the current plan.\n"
        "5. When the user asks 'what's for dinner tonight' or similar, check the current day and look up the schedule for that day.\n"
        "6. If the user asks for detailed recipes, ingredients, cooking steps, or groceries, that is outside your scope and should be handled by recipe_grocery_planner via the coordinator.\n"
        "7. Structure schedules clearly in markdown, showing meal names and brief descriptions only."
    ),
    tools=[
        get_weekly_schedule_tool,
        save_weekly_plan_tool,
        update_single_meal_in_schedule,
        get_current_datetime
    ]
)

vision_scanner = LlmAgent(
    model=configured_llm,
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
        "- Active user: {user:profile_name?}\n"
        "- Household members: " + HOUSEHOLD_MEMBERS_TEXT + "\n\n"
        "CRITICAL RULES:\n"
        "1. When a user describes food they ate (text OR photo), ESTIMATE the calories and macros using your nutritional knowledge, "
        "   then IMMEDIATELY log them using 'log_macros_tool'. Don't just describe — always LOG.\n"
        "2. If the user doesn't specify their name, use the active user from session state.\n"
        "3. For fridge scans (photos or text), identify items and add them to the shared household pantry using 'add_to_pantry_tool'.\n"
        "4. To check daily progress, use 'get_macro_diary_tool' and summarize totals.\n"
        "5. Always respond with a clean markdown summary of what was logged."
    ),
    tools=[
        add_to_pantry_tool,
        log_macros_tool,
        get_pantry_stock_tool,
        get_macro_diary_tool,
        get_current_datetime
    ]
)

recipe_grocery_planner = LlmAgent(
    model=configured_llm,
    name="recipe_grocery_planner",
    description=(
        "Handles detailed recipes, ingredients, pantry-aware grocery planning, "
        "native household grocery cart persistence, and household food preferences. "
        "Route here when the user asks for a recipe, cooking steps, ingredients, "
        "what they need for a dish or scheduled meal, grocery planning, shopping lists, "
        "or food preferences like avoiding tofu or preferring high-protein dinners."
    ),
    instruction=(
        "You are Kitch's Recipe + Grocery Planner — you keep recipes and groceries connected.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Active user: {user:profile_name?}\n"
        "- Household members: " + HOUSEHOLD_MEMBERS_TEXT + " (" + HOUSEHOLD_SIZE_TEXT + " people)\n"
        "- Household size: {app:household_size?}\n\n"
        "CRITICAL RULES:\n"
        "1. Before generating recipes or groceries, call 'search_household_food_preferences_tool' with the user's request and apply any household preferences, dislikes, exclusions, or planning styles you find.\n"
        "2. If the user states a new household food preference or exclusion (for example 'we prefer not to use tofu', 'avoid mushrooms', or 'prefer high protein dinners'), call 'set_household_food_preference_tool' to save it. If the same message also asks for a recipe or groceries, save the preference first, then continue.\n"
        "3. Resolve only the user's requested scope. Examples: tonight's dinner, tomorrow's meals, next 2 days, a named saved meal, or a standalone dish like paneer butter masala. For schedule-based scopes, call 'get_weekly_schedule_tool' and select only the requested meal slots or days. Do not process the whole weekly plan unless the user explicitly asks for the full week.\n"
        "4. For every recipe or grocery request, generate structured recipe cards with: title, scope item/day/date/mealSlot when applicable, servings, cookTime, shortDescription, ingredients with quantities and units, steps, and notes.\n"
        "5. Recipe-only requests: call 'save_recipe_grocery_plan_tool' with update_cart=false and cart_items=[]. Respond with the recipe, ingredients, and concise cooking steps. Do not update the native grocery cart.\n"
        "6. Grocery/cart/buy/order wording: call 'get_pantry_stock_tool', generate recipe cards for the requested scope, derive cart rows from the SAME ingredients, mark pantry-covered rows with alreadyStocked=true and a stockNote, then call 'save_recipe_grocery_plan_tool' with update_cart=true. This replaces previous source=agent cart rows and preserves manual rows.\n"
        "7. If the user mentions items already at home or just bought, call 'add_to_pantry_tool' for each item first, then plan using the updated pantry.\n"
        "8. Never invent native cart rows independently of the recipe cards. Recipe and grocery outputs must stay connected through the saved recipe+grocery artifact.\n"
        "9. Do not call Zepto, Blinkit, provider sync, export, or order-placement tools. Provider cart translation is separate from this agent and happens through backend provider endpoints or a future provider agent.\n"
        "10. Present results in clean markdown. For grocery requests, mention that the native household grocery cart has been updated."
    ),
    tools=[
        get_weekly_schedule_tool,
        get_grocery_cart_tool,
        clear_planned_grocery_cart_tool,
        save_recipe_grocery_plan_tool,
        get_recipe_grocery_plan_tool,
        list_recipe_grocery_plans_tool,
        set_household_food_preference_tool,
        search_household_food_preferences_tool,
        get_pantry_stock_tool,
        add_to_pantry_tool,
        get_current_datetime
    ]
)

# 4. Construct the Central Coordinator Agent (Parent Orchestrator Hub)
kitch_coordinator = LlmAgent(
    model=configured_llm,
    name="kitch_coordinator",
    description="Central parent Coordinator agent managing triage and sub-agent routing.",
    instruction=(
        "You are Kitch, the friendly and intelligent kitchen assistant for this household.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Today is: {current_day_of_week?}\n"
        "- Active user: {user:profile_name?}\n"
        "- Dietary preference: {user:dietary_profile?}\n"
        "- Household members: {app:household_members?}\n"
        "- Household size: {app:household_size?}\n\n"
        "YOUR JOB is to understand what the user needs and route to the right specialist:\n\n"
        "→ 'chef_planner': For lightweight meal plan schedules: creating the weekly plan, "
        "  viewing scheduled meals, swapping/changing scheduled meal names, or asking what's currently planned.\n\n"
        "→ 'vision_scanner': For ANYTHING about food intake logging — whether the user describes "
        "  food in text ('I ate pasta') OR uploads a photo. Also for pantry/fridge scanning, "
        "  calorie tracking, and 'how many calories today' questions.\n\n"
        "→ 'recipe_grocery_planner': For detailed recipes, cooking steps, ingredients, "
        "  groceries, shopping lists, 'what do I need to buy', pantry-aware grocery planning, "
        "  and household food preferences or exclusions.\n\n"
        "GUIDELINES:\n"
        "1. Be warm and conversational. You're the household's kitchen buddy, not a robot.\n"
        "2. Route naturally — don't tell the user which agent you're using.\n"
        "3. For simple greetings or general chat, respond yourself without routing.\n"
        "4. If unsure, ask a clarifying question rather than guessing wrong.\n"
        "5. When the user says 'I ate something' or 'log what I ate', ALWAYS route to vision_scanner for logging.\n"
        "6. If the user asks to add groceries to Zepto/Blinkit, route only the native recipe/grocery planning part to recipe_grocery_planner. Provider cart sync is handled by backend UI actions, not ordinary chat.\n"
        "7. Never ask 'which agent should I use' — just figure it out from context."
    ),
    sub_agents=[chef_planner, vision_scanner, recipe_grocery_planner],
    before_agent_callback=inject_datetime_callback
)

# 5. Define background context compactor on the App wrapper (interval: 4 turns, overlap: 1)
my_summarizer = LlmEventSummarizer(llm=configured_llm)

app_instance = App(
    name="kitch",
    root_agent=kitch_coordinator,
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=4,
        overlap_size=1,
        summarizer=my_summarizer
    )
)

# 6. Instantiate the Central persistent Runner wired with the compacted App and Services
runner = Runner(
    app=app_instance,
    session_service=session_service,
    memory_service=memory_service
)
