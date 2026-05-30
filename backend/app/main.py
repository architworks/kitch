# Kitch: FastAPI Production Gateway Server (Google ADK 2.0)

import time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from app.schemas import ChatRequest, ChatResponse
from app.agent.core import runner, session_service
from app.agent.tools import get_weekly_schedule_dict, export_to_delivery
from app.household_config import DEFAULT_HOUSEHOLD_SIZE, canonical_user_name, household_members_text
from google.genai.types import Content, Part
from google.adk.events import Event, EventActions

# Import direct database CRUD functions
from app.supabase_client import (
    get_pantry_stock,
    get_macro_diary,
    clear_macro_diary,
    add_to_pantry,
    remove_from_pantry,
    get_household_profile,
    update_household_profile
)

load_dotenv()

# Helper: Ensure the ADK session exists and the user: and app: states are fully synchronized
async def get_or_create_session(user_name: str, session_id: str, diet_preference: str, household_size: int):
    """
    Looks up the ADK session thread. Syncs user profile parameters 
    into persistent user: and app: prefixed session states before executing.
    """
    active_user = canonical_user_name(user_name)
    user_id = active_user.replace(" ", "_")
    
    state_updates = {
        "user:profile_name": active_user,
        "user:dietary_profile": diet_preference,
        "app:household_size": household_size,
        "app:household_members": household_members_text()
    }
    
    session = await session_service.get_session(app_name="kitch", user_id=user_id, session_id=session_id)
    
    if not session:
        # Create a new session with initial state
        session = await session_service.create_session(
            app_name="kitch",
            user_id=user_id,
            session_id=session_id,
            state=state_updates
        )
    else:
        # Session exists. Append an event with a state delta to sync profile updates dynamically
        actions = EventActions(state_delta=state_updates)
        sync_event = Event(
            invocation_id=f"sync_state_{int(time.time())}",
            author="system",
            actions=actions,
            timestamp=time.time()
        )
        await session_service.append_event(session, sync_event)
        
    return session

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events logging backend startup/shutdown.
    """
    print("🚀 Starting Kitch ADK 2.0 Backend Gateway Service...")
    yield
    print("💤 Stopped Kitch ADK 2.0 Backend Gateway Service.")

app = FastAPI(
    title="Kitch Backend Gateway",
    description="Python microservice running the Google ADK 2.0 agentic loops.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for Next.js frontend calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Conversational Chat Agent Endpoint
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    """
    Exposes conversational chat. Interfaces with the Kitch Coordinator
    running the Google ADK 2.0 persistent session loops.
    """
    try:
        active_user = canonical_user_name(payload.active_user)
        user_id = active_user.replace(" ", "_")
        session_id = f"kitch_chat_session_{user_id}"
        
        # 1. Update shared household planning settings
        update_household_profile(
            diet_preference=payload.diet_preference,
            household_size=payload.household_size
        )
        
        # 2. Sync profile parameters into the ADK session state persistently
        await get_or_create_session(
            user_name=active_user,
            session_id=session_id,
            diet_preference=payload.diet_preference,
            household_size=payload.household_size
        )
        
        # 3. Construct a standard Content message for the ADK runner
        user_message = Content(
            parts=[Part(text=payload.message)],
            role="user"
        )
        
        # 4. Stream and run the persistent agent turn
        text_reply = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message
        ):
            if event.is_final_response() and event.content and event.content.parts:
                text_reply = event.content.parts[0].text
                
        # Detect if the model triggered grocery lists or planner sync actions
        action = None
        text_lower = text_reply.lower()
        
        if "swapped" in text_lower or "modified your meal plan" in text_lower:
            action = {"type": "UPDATE_PLANNER"}
        elif "dietary alignment complete" in text_lower or "switched dietary profile" in text_lower:
            action = {"type": "SWITCH_DIET"}
        elif "added" in text_lower and "pantry" in text_lower:
            action = {"type": "UPDATE_PANTRY"}
            
        return ChatResponse(text=text_reply, action=action)
        
    except Exception as e:
        print(f"Chat execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 2. Visual Photo Ingestion & OCR Scanner Endpoint
@app.post("/api/upload-photo")
async def upload_photo_endpoint(
    file: UploadFile = File(...),
    active_user: str = Form(...),
    is_fridge_scan: bool = Form(False)
):
    """
    Natively ingests food plate or fridge interior images utilizing 
    ADK 2.0 Part byte builders. Parses and logs outcomes to Supabase.
    """
    try:
        file_bytes = await file.read()
        file_name = file.filename
        
        active_user = canonical_user_name(active_user)
        user_id = active_user.replace(" ", "_")
        session_id = f"kitch_chat_session_{user_id}"
        
        # Resolve shared household settings from Supabase to keep state in sync
        profile = get_household_profile()
        diet_preference = profile.get("diet_preference", "balanced")
        household_size = profile.get("household_size", DEFAULT_HOUSEHOLD_SIZE)
        
        # Sync parameters to active ADK session
        await get_or_create_session(
            user_name=active_user,
            session_id=session_id,
            diet_preference=diet_preference,
            household_size=household_size
        )
        
        # Construct dynamic prompt instructions
        if is_fridge_scan:
            prompt = (
                f"Analyze this fridge shelf photo upload: {file_name}. "
                "1. List all ingredients present.\n"
                "2. PROACTIVELY call the 'add_to_pantry_tool' for each detected ingredient to save it to the shared household pantry in Supabase. "
                "Include the ingredient name, estimated amount, and standard unit (e.g. 'stalks', 'slice', 'whole', 'large', 'tbsp').\n"
                "3. In your response text, summarize the pantry updates in a friendly list."
            )
        else:
            prompt = (
                f"Analyze this food plate photo upload: {file_name} for the user {active_user}. "
                "1. Identify the meal plate dish.\n"
                "2. Estimate total calories and macronutrients (protein, carbs, fat, fiber).\n"
                f"3. PROACTIVELY call the 'log_macros_tool' to write this meal log directly to {active_user}'s intake journal in Supabase.\n"
                "4. In your response text, summarize the nutritional breakdown and confirm it has been logged."
            )
            
        # Natively package file bytes and prompt text as ContentParts
        prompt_part = Part(text=prompt)
        image_part = Part.from_bytes(data=file_bytes, mime_type=file.content_type)
        
        user_message = Content(
            parts=[prompt_part, image_part],
            role="user"
        )
        
        # Run multimodal scan turn
        text_reply = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message
        ):
            if event.is_final_response() and event.content and event.content.parts:
                text_reply = event.content.parts[0].text
                
        return {
            "result": text_reply,
            "isFridgeScan": is_fridge_scan,
            "filename": file_name
        }
        
    except Exception as e:
        print(f"Photo upload execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 3. Live DB Synchronization State Routes
@app.get("/api/state/{user_name}")
async def get_state_endpoint(user_name: str):
    """
    Returns live DB state (Pantry stock levels, Macro diary records, profile settings) 
    directly from Supabase for initial dashboard sync.
    """
    try:
        active_user = canonical_user_name(user_name)
        profile = get_household_profile()
        pantry = get_pantry_stock()
        diary = get_macro_diary(active_user)
        weekly_plan = get_weekly_schedule_dict()
        
        return {
            "profile": profile,
            "pantry_stock": pantry,
            "macro_diary": diary,
            "weekly_plan": weekly_plan
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pantry/add")
async def add_pantry_endpoint(payload: Dict[str, Any]):
    """Adds a pantry item manually to Supabase."""
    try:
        user = canonical_user_name(payload.get("user_name"))
        name = payload.get("name", "")
        amount = float(payload.get("amount", 1))
        unit = payload.get("unit", "piece")
        
        res = add_to_pantry(user, name, amount, unit)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/pantry/remove/{user_name}/{item_name}")
async def remove_pantry_endpoint(user_name: str, item_name: str):
    """Deletes a pantry item from Supabase."""
    try:
        res = remove_from_pantry(user_name, item_name)
        return {"status": "success" if res else "failed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/diary/clear/{user_name}")
async def clear_diary_endpoint(user_name: str):
    """Clears macro logs in Supabase."""
    try:
        res = clear_macro_diary(canonical_user_name(user_name))
        return {"status": "success" if res else "failed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. Dynamic Pantry Calculations Route
@app.post("/api/grocery/calculate")
async def calculate_grocery_endpoint(payload: Dict[str, Any]):
    """
    Decoupled Calculations Route:
    Receives current weekly plan, household size, and pantry stock,
    and returns the intermediary platform-agnostic required shopping list.
    """
    try:
        return {"grocery_list": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 5. Blinkit / Zepto Brand-Mapped Exporter Route
@app.post("/api/grocery/export")
async def export_grocery_endpoint(payload: Dict[str, Any]):
    """
    Decoupled checkout preview: maps required items to chosen delivery merchant
    using ADK native brand preference memory. Real MCP cart connection is deferred.
    """
    try:
        items = payload.get("items", [])
        provider = payload.get("provider", "blinkit")
        
        result = await export_to_delivery(items=items, provider=provider)
        return {"status": "success", "result": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "engine": "google-adk"}
