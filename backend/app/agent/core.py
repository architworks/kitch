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
from app.planning_calendar import calendar_context
from app.supabase_client import get_household_timezone

from .tools import (
    get_meal_schedule_tool,
    replace_meal_plan_range_tool,
    update_dated_meals_tool,
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
    get_current_datetime,
    list_grocery_providers_tool,
    get_grocery_checkout_status_tool,
    sync_instamart_cart_tool,
)
from google.adk.agents.callback_context import CallbackContext
from typing import Optional

from dotenv import load_dotenv

# 0. Load model provider credentials dynamically from gitignored .env file
load_dotenv()

from app.telemetry import configure_adk_tracing

configure_adk_tracing()

def build_llm_model():
    """
    Builds Kitch's Gemini model adapter from environment configuration.

    Authentication is handled by the Google Gen AI SDK:
    - Google AI Studio: GOOGLE_API_KEY (or GEMINI_API_KEY) and
      GOOGLE_GENAI_USE_VERTEXAI=FALSE.
    - Vertex AI: Application Default Credentials plus GOOGLE_CLOUD_PROJECT,
      GOOGLE_CLOUD_LOCATION, and GOOGLE_GENAI_USE_VERTEXAI=TRUE.
    """
    model_name = os.environ.get("KITCH_LLM_MODEL", "gemini-3.6-flash").strip()
    if not model_name.startswith("gemini-"):
        raise ValueError(
            "KITCH_LLM_MODEL must be a Gemini model ID (for example, "
            "'gemini-3.6-flash')."
        )

    return Gemini(model=model_name)

configured_llm = build_llm_model()

# 1. Intentionally ephemeral ADK services.
# These are process-local until the Vertex AI migration and must never be used
# as substitutes for structured Supabase state.
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
    context = calendar_context(get_household_timezone())
    now = context["now"]
    callback_context.state["household_timezone"] = context["timezone"]
    callback_context.state["current_datetime"] = now.strftime("%A, %B %d, %Y (%Y-%m-%d) at %I:%M %p")
    callback_context.state["current_day_of_week"] = now.strftime("%A").lower()
    callback_context.state["current_date"] = context["today"].isoformat()
    callback_context.state["tomorrow_date"] = context["tomorrow"].isoformat()
    callback_context.state["current_week_start"] = context["current_week_start"].isoformat()
    callback_context.state["current_week_end"] = context["current_week_end"].isoformat()
    callback_context.state["current_week_dates"] = context["current_week_dates"]
    callback_context.state["planning_week_start"] = context["next_week_start"].isoformat()
    callback_context.state["planning_week_end"] = context["next_week_end"].isoformat()
    callback_context.state["planning_week_dates"] = context["next_week_dates"]
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
        "- Household timezone: {household_timezone?}\n"
        "- Today: {current_date?}\n"
        "- Tomorrow: {tomorrow_date?}\n"
        "- Current week (ending {current_week_end?}): {current_week_dates?}\n"
        "- Next calendar week: {planning_week_dates?}\n"
        "- Planner week currently visible to the user: {app:planner_week_start?}\n"
        "- Exact dates in the visible planner week: {app:planner_week_dates?}\n"
        "- Planner date currently selected by the user: {app:planner_selected_date?}\n\n"
        "CRITICAL RULES:\n"
        "1. Meal plans store dynamically generated MEAL NAME STRINGS only. Do not pull from a static database, and do not use recipe IDs (like b1, d2).\n"
        "2. Resolve every scope to exact ISO dates before reading or writing: tomorrow is tomorrow_date; this week is current_date through current_week_end; next week/the next week/coming week is planning_week_start through planning_week_end; next N days starts current_date unless the user says starting tomorrow.\n"
        "3. A bare weekday refers to that weekday in the visible planner week when supplied. Otherwise use the nearest non-past occurrence. State the resolved exact date in the response.\n"
        "4. For a NEW plan, call replace_meal_plan_range_tool with exactly one plan object per date and breakfast, lunch, and dinner meal-name strings. It replaces only that explicit range; never rewrite another week. Do not plan snacks.\n"
        "5. For a targeted change, first call get_meal_schedule_tool for the exact affected range, then call update_dated_meals_tool once with all requested edits. Never use a range replacement for a narrow edit.\n"
        "6. Read schedules only with explicit start_date and end_date. Missing dates or slots are unplanned; never borrow a same-named weekday from another week.\n"
        "7. Never create, modify, or claim access to a past plan date. Past meal-plan rows are automatically deleted after the household date advances.\n"
        "8. If the user asks for detailed recipes, ingredients, cooking steps, or groceries, that is outside your scope and should be handled by recipe_grocery_planner via the coordinator.\n"
        "9. Structure schedules clearly in markdown with exact dates and meal names. Describe a schedule as saved or updated only after the relevant persistence tool returns status=success. If it fails, explicitly say nothing was saved."
    ),
    tools=[
        get_meal_schedule_tool,
        replace_meal_plan_range_tool,
        update_dated_meals_tool,
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
        "5. Always respond with a clean markdown summary of what was logged.\n"
        "6. Describe pantry or diary data as saved only after its persistence tool returns a successful result. If persistence fails or has no successful result, explicitly say nothing was saved."
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
        "2. If the user states a new household food preference or exclusion (for example 'we prefer not to use tofu', 'avoid mushrooms', or 'prefer high protein dinners'), call 'set_household_food_preference_tool' to store it in explicitly ephemeral process-local ADK memory. If the same message also asks for a recipe or groceries, store the preference first, then continue. Never describe this memory as durable.\n"
        "3. Resolve only the user's requested scope to exact ISO dates. Examples: tonight's dinner, tomorrow's meals, next 2 days, a named saved meal, or a standalone dish like paneer butter masala. For schedule-based scopes, call 'get_meal_schedule_tool' with the exact start and end date and select only those slots. Do not process another week.\n"
        "4. For every recipe or grocery request, generate structured recipe cards with: title, scope item/day/date/mealSlot when applicable, servings, cookTime, shortDescription, ingredients with quantities and units, steps, and notes.\n"
        "5. Recipe-only requests: call 'save_recipe_grocery_plan_tool' with update_cart=false and cart_items=[]. Respond with the recipe, ingredients, and concise cooking steps. Do not update the native grocery cart.\n"
        "6. Grocery/cart/buy/order wording: call 'get_pantry_stock_tool', generate recipe cards for the requested scope, derive cart rows from the SAME ingredients, mark pantry-covered rows with alreadyStocked=true and a stockNote, then call 'save_recipe_grocery_plan_tool' with update_cart=true. This replaces previous source=agent cart rows and preserves manual rows.\n"
        "7. If the user mentions items already at home or just bought, call 'add_to_pantry_tool' for each item first, then plan using the updated pantry.\n"
        "8. Never invent native cart rows independently of the recipe cards. Recipe and grocery outputs must stay connected through the saved recipe+grocery artifact.\n"
        "9. Do not call ordering-provider cart mutation or order-placement tools. Provider cart translation is separate from this agent and happens through the guarded checkout backend.\n"
        "10. Present results in clean markdown. For grocery requests, mention that the native household grocery cart has been updated only after save_recipe_grocery_plan_tool returns status=success.\n"
        "11. Never describe a recipe artifact or cart as saved based on intent alone. If a persistence tool fails or has no successful result, explicitly say nothing was saved."
    ),
    tools=[
        get_meal_schedule_tool,
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
        "6. If the user explicitly asks to move, sync, or refresh the existing native grocery cart in Swiggy Instamart, call sync_instamart_cart_tool. This prepares and confirms the provider cart but never orders. If the user is merely planning groceries, route to recipe_grocery_planner and update only the native cart. Never trigger provider synchronization from ordinary grocery wording.\n"
        "7. Never attempt provider checkout from chat. Explain that final review and Place Order are available only in the Groceries UI.\n"
        "8. Never ask 'which agent should I use' — just figure it out from context.\n"
        "9. Never claim a durable change succeeded unless the specialist received a successful persistence-tool result. Do not turn a tool error into reassuring success language."
    ),
    sub_agents=[chef_planner, vision_scanner, recipe_grocery_planner],
    tools=[
        list_grocery_providers_tool,
        get_grocery_checkout_status_tool,
        sync_instamart_cart_tool,
    ],
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
