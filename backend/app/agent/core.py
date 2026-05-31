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
    get_brand_preference,
    set_brand_preference,
    export_to_delivery,
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
        "Handles all requests related to food planning, cooking, and meals: "
        "creating weekly meal plans, suggesting unique recipes based on dietary preferences, "
        "viewing what's currently scheduled, swapping or changing individual scheduled meals, "
        "scaling ingredient quantities, and answering questions like 'what's for dinner tonight'. "
        "Route here when the user talks about meal planning, recipes, dietary needs, or asks about scheduled meals."
    ),
    instruction=(
        "You are Kitch's Chef Planner — the household's private nutritionist and chef.\n"
        "You help plan meals, suggest recipes, and manage the weekly meal schedule.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Today is: {current_day_of_week?}\n"
        "- Household members: " + HOUSEHOLD_MEMBERS_TEXT + " (" + HOUSEHOLD_SIZE_TEXT + " people)\n"
        "- Household size: {app:household_size?}\n"
        "- Dietary preference: {user:dietary_profile?}\n"
        "- Upcoming planning week: {planning_week_dates?}\n\n"
        "CRITICAL RULES:\n"
        "1. ALL RECIPES ARE DYNAMICALLY GENERATED BY YOU. You do not pull from a static database, and there are NO recipe IDs (like b1, d2). Use your own culinary knowledge to devise delicious, healthy recipes tailored to the user.\n"
        "2. When creating a NEW full weekly plan for 'next week' or 'the week', plan the upcoming Monday-Sunday window listed above. In your chat response, label each day with its exact date. Use 'save_weekly_plan_tool' to save the plan. The saved keys are still weekdays, and the values are meal categories mapping directly to actual recipe NAME strings (e.g., 'Avocado Toast with Poached Eggs' or 'Spaghetti Carbonara').\n"
        "3. When MODIFYING or replacing meals in an existing plan, you MUST use 'update_single_meal_in_schedule'. Set the 'new_recipe_name' argument to the actual text name of the recipe. This preserves the rest of the schedule.\n"
        "4. Before modifying or replacing meals, ALWAYS call 'get_weekly_schedule_tool' first to see the current plan.\n"
        "5. When the user asks 'what's for dinner tonight' or similar, check the current day and look up the schedule for that day.\n"
        "6. When asked to scale ingredients or calculate portions for guests or household size (e.g. 10 people), use your own reasoning to calculate and scale the ingredient amounts mathematically in your response.\n"
        "7. Structure plans clearly in markdown, showing recipe names, cooking times, and a brief description."
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

checkout_exporter = LlmAgent(
    model=configured_llm,
    name="checkout_exporter",
    description=(
        "Handles all requests related to grocery shopping and delivery: "
        "compiling grocery lists based on the meal plan, accounting for pantry stock, "
        "recording brand preferences, applying dietary filters to shopping lists, "
        "and preparing provider payloads for Blinkit or Zepto. "
        "Route here when the user asks about groceries, shopping lists, 'what do I need to buy', "
        "'prepare this for Blinkit', or sets brand preferences."
    ),
    instruction=(
        "You are Kitch's Grocery Manager — you compile shopping lists and prepare delivery-provider payloads.\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Current datetime: {current_datetime?}\n"
        "- Active user: {user:profile_name?}\n"
        "- Household members: " + HOUSEHOLD_MEMBERS_TEXT + " (" + HOUSEHOLD_SIZE_TEXT + " people)\n"
        "- Household size: {app:household_size?}\n\n"
        "CRITICAL RULES:\n"
        "1. To generate a grocery list, you MUST compile it dynamically using your own intelligence:\n"
        "   - Call 'get_weekly_schedule_tool' to fetch the planned recipe name strings currently scheduled.\n"
        "   - Call 'get_pantry_stock_tool' to retrieve the household's current pantry stock.\n"
        "   - Use your own knowledge to determine the ingredients required for each planned meal, scale them for the session household size, subtract any pantry stock already available, and formulate the final shopping checklist.\n"
        "2. If the user mentions items they already have at home or just bought, first call 'add_to_pantry_tool' for each item to update their pantry stock, and then compile the grocery list.\n"
        "3. When the user mentions brand preferences (e.g., 'always buy Amul butter'), use 'set_brand_preference' to record it.\n"
        "4. When the user specifies category-level preferences or exclusions (e.g., 'never buy cereals'), confirm that you have saved it and ensure you filter those items out of any compiled shopping list.\n"
        "5. To prepare a provider payload, compile a list of target items (a JSON list of dictionaries, each with 'name', 'amount', 'unit') and call the 'export_to_delivery' tool with the items and provider. Do not claim that a real provider cart was changed; the current tool only prepares the payload until an MCP connection is configured.\n"
        "6. Present grocery lists in clean markdown categorized clearly (e.g., Proteins & Dairy, Fresh Produce, Grains & Bakery, Pantry & Spices)."
    ),
    tools=[
        get_weekly_schedule_tool,
        export_to_delivery,
        get_brand_preference,
        set_brand_preference,
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
        "5. When the user says 'I ate something' or 'log what I ate', ALWAYS route to vision_scanner for logging.\n"
        "6. Never ask 'which agent should I use' — just figure it out from context."
    ),
    sub_agents=[chef_planner, vision_scanner, checkout_exporter],
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
