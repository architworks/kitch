# Kitch: ADK 2.0 Multi-Agent Assembly & Session Orchestrator Core

import os
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models.lite_llm import LiteLlm
from google.genai.types import Content, Part

from .tools import (
    get_recipes, 
    get_all_recipes,
    scale_ingredients, 
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
    calculate_intermediary_grocery_list,
    get_current_datetime
)
from google.adk.agents.callback_context import CallbackContext
from typing import Optional

# 0. Set Azure OpenAI Credentials dynamically or directly as fallbacks (OpenAI Compatibility Mode)
os.environ["OPENAI_API_KEY"] = os.environ.get(
    "OPENAI_API_KEY", "REMOVED_KEY"
)
os.environ["OPENAI_API_BASE"] = os.environ.get(
    "OPENAI_API_BASE", "https://grmopenai-us2.openai.azure.com/openai/v1/"
)
os.environ["OPENAI_MODEL_NAME"] = os.environ.get(
    "OPENAI_MODEL_NAME", "gpt-5.5"
)

AZURE_MODEL = os.environ["OPENAI_MODEL_NAME"]
model_identifier = f"openai/{AZURE_MODEL}"

azure_llm = LiteLlm(
    model=model_identifier,
    api_key=os.environ["OPENAI_API_KEY"],
    api_base=os.environ["OPENAI_API_BASE"],
    custom_llm_provider="openai"
)

# 1. Initialize modern, high-performance in-memory prototyping services
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

# 1.5 Datetime Injection Callback
def inject_datetime_callback(callback_context: CallbackContext) -> Optional[Content]:
    """
    Before-agent callback that injects the current datetime into session state.
    This ensures the coordinator and all sub-agents know what day/time it is.
    """
    from datetime import datetime
    now = datetime.now()
    callback_context.state["current_datetime"] = now.strftime("%A, %B %d, %Y at %I:%M %p")
    callback_context.state["current_day_of_week"] = now.strftime("%A").lower()
    callback_context.state["current_date"] = now.strftime("%Y-%m-%d")
    return None  # Continue execution

# 3. Assemble the 3-Spoke Specialized Spoke Sub-Agents
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

# 4. Construct the Central Coordinator Agent (Parent Orchestrator Hub)
kitch_coordinator = LlmAgent(
    model=azure_llm,
    name="kitch_coordinator",
    description="Central parent Coordinator agent managing triage and sub-agent routing.",
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
        "5. When the user says 'I ate something' or 'log what I ate', ALWAYS route to vision_scanner for logging.\n"
        "6. Never ask 'which agent should I use' — just figure it out from context."
    ),
    sub_agents=[chef_planner, vision_scanner, checkout_exporter],
    before_agent_callback=inject_datetime_callback
)

# 5. Define background context compactor on the App wrapper (interval: 4 turns, overlap: 1)
my_summarizer = LlmEventSummarizer(llm=azure_llm)

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
