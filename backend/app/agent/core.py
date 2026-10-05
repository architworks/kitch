# Kitch: ADK 2.0 Multi-Agent Assembly & Session Orchestrator Core

import os
from pathlib import Path
from dotenv import load_dotenv

# Load gitignored backend configuration before constructing model or memory
# services imported below.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_DIR / ".env.local")
load_dotenv(_BACKEND_DIR / ".env")

from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models.google_llm import Gemini
from google.genai.types import Content, Part
from app.planning_calendar import calendar_context
from app.storage import get_household_timezone

from .tools import (
    get_meal_schedule_tool,
    replace_meal_plan_range_tool,
    update_dated_meals_tool,
    remove_future_meals_tool,
    get_pantry_state_tool,
    patch_pantry_tool,
    replace_pantry_tool,
    reconcile_native_cart_with_pantry_tool,
    log_macros_tool,
    get_macro_diary_tool,
    update_nutrition_entry_tool,
    delete_nutrition_entry_tool,
    clear_nutrition_day_tool,
    get_grocery_cart_tool,
    modify_native_grocery_cart_tool,
    clear_planned_grocery_cart_tool,
    save_recipe_grocery_plan_tool,
    get_recipe_grocery_plan_tool,
    list_recipe_grocery_plans_tool,
    update_recipe_grocery_plan_tool,
    delete_recipe_grocery_plan_tool,
    get_current_datetime,
    list_grocery_providers_tool,
    get_provider_cart_tool,
    sync_provider_cart_tool,
    update_household_configuration_tool,
    update_nutrition_targets_tool,
)
from .memory import (
    memory_service,
    search_household_memory_tool,
    update_household_memory_tool,
)
from .structured_models import PhotoAnalysis, PantryReconciliation
from .tool_error_policy import recover_unknown_tool_error
from google.adk.agents.callback_context import CallbackContext
from typing import Optional

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

# 1. Chat sessions intentionally remain process-local. Household memory uses
# the configured memory backend and never substitutes for Supabase state.
session_service = InMemorySessionService()

# 1.5 Datetime Injection Callback
def inject_datetime_callback(callback_context: CallbackContext) -> Optional[Content]:
    """
    Before-agent callback that injects the current datetime into session state.
    This ensures the coordinator and all sub-agents know what day/time it is.
    """
    context = calendar_context(get_household_timezone())
    now = context["now"]
    callback_context.state["household_timezone"] = context["timezone"]
    callback_context.state["request_received_at"] = now.isoformat()
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
        "removing meal slots, dates, ranges, or all saved future meal plans, "
        "and answering questions like 'what's for dinner tonight'. "
        "Route here when the user talks about meal plan schedules, swaps, removals, or planned meals."
    ),
    instruction=(
        "You are Kitch's Chef Planner — the household's lightweight meal scheduler.\n"
        "You plan meal names and manage the weekly schedule. Detailed recipes, ingredients, and grocery cart generation belong to the recipe_grocery_planner.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Today is: {current_day_of_week?}\n"
        "- Household members: {app:household_members?}\n"
        "- Household size: {app:household_size?}\n"
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
        "4. Use household memory when earlier kitchen preferences or constraints could materially improve this task. Preserve durable context, corrections, and requests to forget in the user's natural language. Do not remember one-off requests or deterministic application state. Apply context stated in the current request directly rather than depending on an immediate read after saving it. If memory is unavailable, continue the planning task when possible but do not claim that context was saved or recalled.\n"
        "5. For a NEW plan, call replace_meal_plan_range_tool with exactly one plan object per date and breakfast, lunch, and dinner meal-name strings. It replaces only that explicit range; never rewrite another week. Do not plan snacks.\n"
        "6. For a targeted change, first call get_meal_schedule_tool for the exact affected range, then call update_dated_meals_tool once with all requested edits. Never use a range replacement for a narrow edit.\n"
        "7. Read schedules only with explicit start_date and end_date. Missing dates or slots are unplanned; never borrow a same-named weekday from another week.\n"
        "8. Use remove_future_meals_tool for explicit future slot/date/range removal. For every/all saved meal plans, pass action=all without inventing boundary dates; the tool resolves the actual saved future range. A single slot or date executes directly; bulk, ranges, and all-future removal require confirmation. When the tool returns confirmation_required, say the removal has not happened yet and ask the user to review the confirmation. Never create or modify past dates.\n"
        "9. If the user asks for detailed recipes, ingredients, cooking steps, or groceries, that is outside your scope and should be handled by recipe_grocery_planner via the coordinator.\n"
        "10. Structure schedules clearly in markdown with exact dates and meal names. Describe a schedule as saved or updated only after the relevant persistence tool returns status=success. If it fails, explicitly say nothing was saved."
    ),
    tools=[
        get_meal_schedule_tool,
        replace_meal_plan_range_tool,
        update_dated_meals_tool,
        remove_future_meals_tool,
        update_household_memory_tool,
        search_household_memory_tool,
        get_current_datetime
    ],
    mode="task",
    on_tool_error_callback=recover_unknown_tool_error,
)

vision_scanner = LlmAgent(
    model=configured_llm,
    name="vision_scanner",
    description=(
        "A non-mutating image interpreter. Classifies every uploaded image as exactly "
        "meal, pantry, or ambiguous and returns structured observations."
    ),
    instruction=(
        "Inspect the image and accompanying text without changing any state. Return exactly one "
        "classification: meal, pantry, or ambiguous. Do not include a confidence score. For a meal, "
        "identify the meal and estimate macros. For a pantry image, list observed inventory and mark "
        "each observation as set for a current-inventory photo or add only when the text clearly says "
        "these are newly purchased items. When the semantic purpose cannot be determined, return "
        "ambiguous with one concise clarification question. Never call tools or claim anything was saved."
    ),
    tools=[],
    output_schema=PhotoAnalysis,
    mode="chat",
    include_contents="none",
)

nutrition_tracker = LlmAgent(
    model=configured_llm,
    name="nutrition_tracker",
    description="Logs, reads, corrects, and deletes personal nutrition diary entries.",
    instruction=(
        "You are Kitch's Nutrition Tracker. Nutrition is user-specific. Log described meals with "
        "log_macros_tool, read progress with get_macro_diary_tool, correct one entry with "
        "update_nutrition_entry_tool, and delete one explicitly identified entry with "
        "delete_nutrition_entry_tool. Update explicit calorie or macro goals with "
        "update_nutrition_targets_tool. Use clear_nutrition_day_tool for a whole day; it creates a "
        "backend confirmation and must not be simulated by repeated deletes. When the user explicitly "
        "names breakfast, lunch, snack, or dinner, pass that meal_type. When the user gives an explicit "
        "consumption date or time, pass it as consumed_at. Otherwise pass the trusted request time "
        "{request_received_at?} as consumed_at and omit meal_type so the backend assigns the meal from "
        "household-local time. Confirm changes only "
        "after a successful tool result."
    ),
    tools=[log_macros_tool, get_macro_diary_tool, update_nutrition_entry_tool,
           delete_nutrition_entry_tool, clear_nutrition_day_tool,
           update_nutrition_targets_tool, get_current_datetime],
    mode="task",
    on_tool_error_callback=recover_unknown_tool_error,
)

pantry_reconciliation_agent = LlmAgent(
    model=configured_llm,
    name="pantry_reconciliation_mode",
    description="Structured non-mutating reconciliation mode for pantry coverage and native purchase intent.",
    instruction=(
        "Semantically reconcile pantry quantities against native grocery requirements. Understand "
        "equivalent real-world units only when defensible, allow partial coverage, and return exactly "
        "one allocation per supplied cart ID. Never invent IDs. purchase_amount is always nonnegative."
    ),
    tools=[], output_schema=PantryReconciliation, mode="chat", include_contents="none",
)

recipe_grocery_planner = LlmAgent(
    model=configured_llm,
    name="recipe_grocery_planner",
    description=(
        "Handles detailed recipes, ingredients, pantry-aware grocery planning, "
        "standalone native grocery-cart edits, native household grocery cart "
        "persistence, and household food preferences. "
        "Route here when the user asks for a recipe, cooking steps, ingredients, "
        "what they need for a dish or scheduled meal, grocery planning, shopping lists, "
        "or food preferences like avoiding tofu or preferring high-protein dinners."
    ),
    instruction=(
        "You are Kitch's Recipe + Grocery Planner — you keep recipes and groceries connected.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Active user: {user:profile_name?}\n"
        "- Household members: {app:household_members?}\n"
        "- Household size: {app:household_size?}\n\n"
        "CRITICAL RULES:\n"
        "1. Use household memory when earlier kitchen context could materially affect recipes, groceries, pantry work, or product matching. Preserve durable household preferences, constraints, corrections, and requests to forget as self-contained natural-language statements. Do not remember transient requests, deterministic app state, provider history, or choices you inferred yourself. Apply context stated in the current message directly without relying on an immediate memory read after writing it.\n"
        "2. Resolve only a recipe or meal-based request's scope to exact ISO dates. Examples: tonight's dinner, tomorrow's meals, next 2 days, a named saved meal, or a standalone dish like paneer butter masala. For schedule-based scopes, call 'get_meal_schedule_tool' with the exact start and end date and select only those slots. Do not process another week.\n"
        "3. For every recipe or recipe-derived grocery request, generate structured recipe cards with: title, scope item/day/date/mealSlot when applicable, servings, cookTime, shortDescription, ingredients with quantities and units, steps, and notes.\n"
        "4. Recipe-only requests: call 'save_recipe_grocery_plan_tool' with update_cart=false and cart_items=[]. Respond with the recipe, ingredients, and concise cooking steps. Do not update the native grocery cart.\n"
        "5. Recipe-derived grocery/cart/buy wording: call get_pantry_state_tool, generate recipe cards for the requested scope, and save required ingredient amounts plus positive purchaseAmount/purchaseUnit and structured pantryAllocation. Never create alreadyStocked or stockNote snapshots.\n"
        "6. Standalone native-cart wording such as 'add two chocolates', 'change milk to 2 litres', or 'remove eggs from my grocery list' does NOT require a recipe. This rule takes priority whenever the user names cart items rather than asking for ingredients for a meal or dish. Call 'get_grocery_cart_tool', then 'modify_native_grocery_cart_tool' with explicit add, set/update, or remove changes. New standalone rows are manual native-cart intent and must not fabricate a recipe artifact.\n"
        "7. Pantry management belongs to you. Read get_pantry_state_tool first, then use patch_pantry_tool for atomic add/set/adjust/single-remove operations. Every add, set, or adjust operation must carry the quantity the user or Vision Scanner supplied; never omit it while relaying structured observations. Current-inventory observations use set; newly purchased stock uses add. Complete replacement, including an empty pantry, requires confirmation before replace_pantry_tool. Pantry changes never update the native cart implicitly. Call reconcile_native_cart_with_pantry_tool only when the user explicitly asks to recalculate or update the grocery cart from pantry state.\n"
        "8. Keep recipe-derived rows connected to their saved artifact. Revise an existing recipe with update_recipe_grocery_plan_tool and delete one explicitly named recipe with delete_recipe_grocery_plan_tool. Standalone rows remain source=manual.\n"
        "9. On an explicit request to move/sync items to an ordering app, call sync_provider_cart_tool. A named provider applies only to this call; otherwise omit provider so the backend uses the last UI selection. Never authenticate, change the saved provider, select payment, or place/cancel an order.\n"
        "10. Provider availability, current ordering-app cart contents, quantities, prices, and totals also belong to you. Use list_grocery_providers_tool or get_provider_cart_tool for these read-only questions. Reading a provider cart must never synchronize, repair, or otherwise mutate it.\n"
        "11. Present results in clean markdown. Mention that the native household grocery cart changed only after the relevant persistence tool returns status=success.\n"
        "12. Never describe memory, a recipe artifact, or a cart as saved based on intent alone. If a persistence tool fails or has no successful result, explicitly say nothing was saved."
    ),
    tools=[
        get_meal_schedule_tool,
        get_grocery_cart_tool,
        modify_native_grocery_cart_tool,
        clear_planned_grocery_cart_tool,
        save_recipe_grocery_plan_tool,
        get_recipe_grocery_plan_tool,
        list_recipe_grocery_plans_tool,
        update_recipe_grocery_plan_tool,
        delete_recipe_grocery_plan_tool,
        update_household_memory_tool,
        search_household_memory_tool,
        get_pantry_state_tool,
        patch_pantry_tool,
        replace_pantry_tool,
        reconcile_native_cart_with_pantry_tool,
        list_grocery_providers_tool,
        get_provider_cart_tool,
        sync_provider_cart_tool,
        get_current_datetime
    ],
    mode="task",
    on_tool_error_callback=recover_unknown_tool_error,
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
        "- Household members: {app:household_members?}\n"
        "- Household size: {app:household_size?}\n\n"
        "YOUR JOB is to understand what the user needs and route to the right specialist:\n\n"
        "→ 'chef_planner': For lightweight meal plan schedules: creating the weekly plan, "
        "  viewing scheduled meals, swapping/changing scheduled meal names, removing planned meal slots/dates/ranges, "
        "  clearing saved future plans, or asking what's currently planned.\n\n"
        "→ 'nutrition_tracker': For food intake logging, macro questions, and correcting or deleting nutrition entries.\n\n"
        "→ 'vision_scanner': Used only by the upload pipeline to classify and interpret images; do not route ordinary text chat to it.\n\n"
        "→ 'recipe_grocery_planner': For detailed recipes, cooking steps, ingredients, "
        "  groceries, shopping lists, 'what do I need to buy', pantry-aware grocery planning, "
        "  standalone add/update/remove requests for the Kitch grocery cart, and household "
        "  food preferences or exclusions, ordering-app availability, provider-cart contents, totals, or explicit provider synchronization.\n\n"
        "GUIDELINES:\n"
        "1. Be warm and conversational. You're the household's kitchen buddy, not a robot.\n"
        "2. Route naturally — don't tell the user which agent you're using.\n"
        "3. For simple greetings or general chat, respond yourself without routing.\n"
        "4. If unsure, ask a clarifying question rather than guessing wrong.\n"
        "5. For nutrition intake, macro tracking, food-log corrections, or nutrition goals, delegate the "
        "complete request to nutrition_tracker. The coordinator must not estimate, log, modify, or claim "
        "success for nutrition records itself.\n"
        "6. All recipes, pantry, native grocery cart, provider availability, provider-cart reads, and explicit provider-cart synchronization requests route to recipe_grocery_planner. Do not intercept provider requests with a coordinator tool.\n"
        "7. Factual household size and timezone may be changed with update_household_configuration_tool. Dietary, food, allergy, planning-style, and brand preferences are natural-language agent memories and must never be written to the household profile. Personal calorie and macro goals belong to nutrition_tracker. Provider authentication and provider selection remain UI-only.\n"
        "8. Ordinary grocery planning changes only native Kitch state; provider synchronization requires explicit move/sync wording.\n"
        "9. Never attempt provider checkout from chat. Explain that final review and Place Order are available only in the Groceries UI.\n"
        "10. Never ask 'which agent should I use' — just figure it out from context.\n"
        "11. Every request to create, change, remove, delete, or clear a meal plan must be delegated to chef_planner. The coordinator never performs or narrates a meal-plan mutation itself.\n"
        "12. Never claim a durable change succeeded unless the specialist or tool received a successful persistence result. Do not turn a tool error into reassuring success language."
    ),
    sub_agents=[chef_planner, recipe_grocery_planner, nutrition_tracker],
    tools=[
        update_household_configuration_tool,
    ],
    on_tool_error_callback=recover_unknown_tool_error,
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

# Image classification and pantry reconciliation are logically one-shot. ADK
# requires root LlmAgents to use chat mode, so isolation comes from a unique
# session per invocation plus include_contents="none", not single_turn mode.
vision_session_service = InMemorySessionService()
vision_runner = Runner(
    app_name="kitch_vision", agent=vision_scanner,
    session_service=vision_session_service, auto_create_session=True,
)
pantry_reconciliation_session_service = InMemorySessionService()
pantry_reconciliation_runner = Runner(
    app_name="kitch_pantry_reconciliation", agent=pantry_reconciliation_agent,
    session_service=pantry_reconciliation_session_service, auto_create_session=True,
)
