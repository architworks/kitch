# Kitch: ADK 2.0 Agent Assembly & Session Orchestrator Core

import os
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService

from .tools import (
    get_recipes, 
    scale_ingredients, 
    get_pantry_stock_tool,
    add_to_pantry_tool,
    log_macros_tool,
    get_macro_diary_tool,
    get_brand_preferences,
    set_brand_preference,
    export_to_delivery
)

# 1. Initialize persistent SQLite database session tracking for isolated housemate states
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../kitch_sessions.db"))
db_url = f"sqlite+aiosqlite:///{DB_PATH}"
session_service = DatabaseSessionService(db_url=db_url)

# 2. Build the primary Kitch Coordinator Agent
# Uses modern state injection patterns to shape instructions based on the active user profile
kitch_agent = LlmAgent(
    model="gemini-3.5-flash",
    name="kitch_coordinator",
    description="Household chef, culinary planner, and smart pantry manager agent.",
    instruction=(
        "You are Kitch, the empathetic, intelligent household chef, dietary planner, and smart pantry manager.\n"
        "You assist a household of 3 people with healthy, balanced weekly plans, pantry stocks, and logs.\n\n"
        "Current Logged-in User Profile: {user:profile_name?}\n"
        "Current User Dietary Profile: {user:dietary_profile?}\n\n"
        "Your operational guidelines are:\n"
        "1. Triage user requests and discuss recipes, planning, macro progress, or pantry inventory.\n"
        "2. To suggest or retrieve recipes, call 'get_recipes'. To adjust ingredients for household size, call 'scale_ingredients'.\n"
        "3. To fetch stock levels or log macros in Supabase, run 'get_pantry_stock_tool' or 'get_macro_diary_tool' respectively.\n"
        "4. If a user uploads fridge photo scans, segmentation scans, or food plates, identify details and PROACTIVELY log them "
        "using 'add_to_pantry_tool' or 'log_macros_tool' to write to their Supabase db instantly. Detail the actions in markdown.\n"
        "5. If a user mentions a brand preference (e.g. 'always order Bakers Dozen bread'), immediately run 'set_brand_preference' "
        "to save it in brand_preferences.md. To inspect preferences, run 'get_brand_preferences'.\n"
        "6. To synchronize grocery items to Blinkit/Zepto, run 'export_to_delivery'. It will automatically consult "
        "brand_preferences.md and map generic items to branded options before syncing."
    ),
    tools=[
        get_recipes,
        scale_ingredients,
        get_pantry_stock_tool,
        add_to_pantry_tool,
        log_macros_tool,
        get_macro_diary_tool,
        get_brand_preferences,
        set_brand_preference,
        export_to_delivery
    ]
)

# 3. Instantiate the Central Runner to manage multi-turn sessions persistently
runner = Runner(
    agent=kitch_agent,
    app_name="kitch",
    session_service=session_service
)
