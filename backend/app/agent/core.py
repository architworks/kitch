# Kitch: ADK 2.0 Multi-Agent Assembly & Session Orchestrator Core

import os
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models import Gemini
from google.genai.types import GenerateContentConfig, ThinkingConfig

from .tools import (
    get_recipes, 
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
    export_to_delivery
)

# 1. Initialize modern, high-performance in-memory prototyping services
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

# 2. Configure Gemini 3.5 Flash with medium reasoning thinking effort
gemini_35_config = GenerateContentConfig(
    thinking_config=ThinkingConfig(
        thinking_level="medium"  # Enforces medium thinking level natively
    )
)

# 3. Assemble the 3-Spoke Specialized Spoke Sub-Agents
chef_planner = LlmAgent(
    model="gemini-3.5-flash",
    name="chef_planner",
    description="Nutritionist and chef Spoke agent focused on schedule database mutations.",
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
    ],
    generate_content_config=gemini_35_config
)

vision_scanner = LlmAgent(
    model="gemini-3.5-flash",
    name="vision_scanner",
    description="Multimodal visual scanning Spoke agent mapping fridge and plate snaps to Supabase.",
    instruction=(
        "You are Kitch's Vision Scanner sub-agent, interpreting photo uploads for the household.\n"
        "Your role is to identify visual plate meals or fridge shelves items and proactively log them.\n\n"
        "Guidelines:\n"
        "1. Snapped Plate scans: Estimate dish calories, protein, carbs, fat, and fiber, and pro-actively write them "
        "   to the database using 'log_macros_tool'. Summarize the macro details in clean markdown.\n"
        "2. Fridge shelves scans: List detected ingredients and pro-actively log them to pantry stock using 'add_to_pantry_tool'.\n"
        "3. Always query active user diaries using 'get_macro_diary_tool' or 'get_pantry_stock_tool' to verify state."
    ),
    tools=[
        add_to_pantry_tool,
        log_macros_tool,
        get_pantry_stock_tool,
        get_macro_diary_tool
    ],
    generate_content_config=gemini_35_config
)

checkout_exporter = LlmAgent(
    model="gemini-3.5-flash",
    name="checkout_exporter",
    description="Checkout logistics Spoke agent resolving brand memory and syncing MCP carts.",
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
    ],
    generate_content_config=gemini_35_config
)

# 4. Construct the Central Coordinator Agent (Parent Orchestrator Hub)
kitch_coordinator = LlmAgent(
    model="gemini-3.5-flash",
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
    sub_agents=[chef_planner, vision_scanner, checkout_exporter],
    generate_content_config=gemini_35_config
)

# 5. Define background context compactor on the App wrapper (interval: 4 turns, overlap: 1)
compactor_llm = Gemini(model="gemini-3.5-flash")
my_summarizer = LlmEventSummarizer(llm=compactor_llm)

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
