# Kitch: FastAPI Production Gateway Server (Google ADK 2.0)

import asyncio
import time
from datetime import datetime, time as datetime_time, timedelta
from uuid import uuid4
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from app.schemas import ChatRequest, ChatResponse
from app.agent.core import runner, session_service
from app.agent.tools import export_to_delivery, apply_brand_memory_to_cart_items
from app.planning_calendar import dates_between, household_zone, parse_iso_date
from app.providers.zepto import ZeptoProviderAdapter
from app.checkout_drafts import (
    draft_row_to_review,
    invalidate_draft_for_native_drift,
    native_snapshot_matches,
    save_initial_draft,
    save_revalidated_draft,
    update_draft_review_fields,
)
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
    get_grocery_cart,
    add_grocery_cart_item,
    update_grocery_cart_item,
    delete_grocery_cart_item,
    clear_planned_grocery_cart,
    get_recipe_grocery_plan,
    list_recipe_grocery_plans,
    get_latest_recipe_grocery_plan_metadata,
    get_household_profile,
    build_meal_plan_week,
    delete_past_meal_plans,
    get_household_timezone,
    get_meal_plan_snapshot,
    update_household_profile,
    validate_persistence_readiness,
    claim_provider_checkout_operation,
    delete_provider_checkout_draft,
    get_provider_checkout_draft,
    release_provider_checkout_operation,
)
from app.persistence import (
    PersistenceConfigurationError,
    PersistenceError,
    begin_persistence_scope,
    end_persistence_scope,
    raise_recorded_persistence_failure,
)

load_dotenv()


async def delete_past_meal_plans_at_household_midnight() -> None:
    """Run retention cleanup after every household-calendar date boundary."""
    while True:
        try:
            timezone_name = await asyncio.to_thread(get_household_timezone)
            zone = household_zone(timezone_name)
            now = datetime.now(zone)
            next_midnight = datetime.combine(
                now.date() + timedelta(days=1),
                datetime_time.min,
                tzinfo=zone,
            )
            await asyncio.sleep(max(1.0, (next_midnight - now).total_seconds() + 1.0))
            deleted_count = await asyncio.to_thread(delete_past_meal_plans)
            if deleted_count:
                print(f"Meal-plan retention removed {deleted_count} past dated rows.")
        except PersistenceError as error:
            print(
                "Meal-plan retention cleanup failed safely: "
                f"operation={error.operation} table={error.table} retryable={error.retryable}"
            )
            await asyncio.sleep(300)

def looks_like_grocery_request(text: str) -> bool:
    """Detects fridge-photo follow-ups that need grocery planning after pantry update."""
    text_lower = (text or "").lower()
    grocery_terms = (
        "grocery",
        "groceries",
        "shopping list",
        "what do i need",
        "need to buy",
        "order for",
        "buy for",
        "add to zepto",
        "zepto",
        "cart",
        "tonight",
        "tomorrow",
    )
    return any(term in text_lower for term in grocery_terms)

# Helper: Ensure the ADK session exists and the user: and app: states are fully synchronized
async def get_or_create_session(
    user_name: str,
    session_id: str,
    diet_preference: str,
    household_size: int,
    planner_week_start: str = "",
    planner_selected_date: str = "",
):
    """
    Looks up the ADK session thread. Syncs user profile parameters 
    into persistent user: and app: prefixed session states before executing.
    """
    active_user = canonical_user_name(user_name)
    user_id = active_user.replace(" ", "_")

    planner_week_dates = ""
    if planner_week_start:
        try:
            visible_start = parse_iso_date(planner_week_start)
            if visible_start.weekday() == 0:
                visible_end = visible_start + timedelta(days=6)
                planner_week_dates = "; ".join(
                    item.strftime("%A %Y-%m-%d")
                    for item in dates_between(visible_start, visible_end)
                )
                if planner_selected_date:
                    selected_date = parse_iso_date(planner_selected_date)
                    if not visible_start <= selected_date <= visible_end:
                        planner_selected_date = ""
            else:
                planner_week_start = ""
                planner_selected_date = ""
        except ValueError:
            planner_week_start = ""
            planner_selected_date = ""
    
    state_updates = {
        "user:profile_name": active_user,
        "user:dietary_profile": diet_preference,
        "app:household_size": household_size,
        "app:household_members": household_members_text(),
        "app:planner_week_start": planner_week_start,
        "app:planner_week_dates": planner_week_dates,
        "app:planner_selected_date": planner_selected_date,
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
    Refuse startup unless durable storage is correctly configured and ready.
    """
    validate_persistence_readiness()
    deleted_count = await asyncio.to_thread(delete_past_meal_plans)
    if deleted_count:
        print(f"Meal-plan retention removed {deleted_count} past dated rows at startup.")
    retention_task = asyncio.create_task(delete_past_meal_plans_at_household_midnight())
    print("🚀 Starting Kitch ADK 2.0 Backend Gateway Service...")
    try:
        yield
    finally:
        retention_task.cancel()
        try:
            await retention_task
        except asyncio.CancelledError:
            pass
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

@app.middleware("http")
async def persistence_postcondition(request: Request, call_next):
    """
    Convert every durable-storage failure to a safe 503 response.

    The request-scope marker also catches failures swallowed by the agent
    framework so chat/photo APIs cannot return generated success text.
    """
    token = begin_persistence_scope()
    try:
        response = await call_next(request)
        raise_recorded_persistence_failure()
        return response
    except PersistenceError as error:
        return JSONResponse(
            status_code=503,
            content={"detail": error.public_detail()},
        )
    finally:
        end_persistence_scope(token)

@app.exception_handler(PersistenceError)
async def persistence_exception_handler(
    request: Request,
    error: PersistenceError,
):
    return JSONResponse(
        status_code=503,
        content={"detail": error.public_detail()},
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
            household_size=payload.household_size,
            planner_week_start=payload.planner_context.visible_week_start,
            planner_selected_date=payload.planner_context.selected_date,
        )

        meal_plan_before = get_meal_plan_snapshot()
        pantry_before = get_pantry_stock()
        grocery_cart_before = get_grocery_cart()
        latest_recipe_plan_before = get_latest_recipe_grocery_plan_metadata()
        
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
                
        meal_plan_after = get_meal_plan_snapshot()
        pantry_after = get_pantry_stock()
        grocery_cart_after = get_grocery_cart()
        latest_recipe_plan_after = get_latest_recipe_grocery_plan_metadata()

        # Only confirmed persisted state changes can produce mutation actions.
        action = None
        
        changed_plan_dates = sorted(
            plan_date
            for plan_date in set(meal_plan_before) | set(meal_plan_after)
            if meal_plan_before.get(plan_date) != meal_plan_after.get(plan_date)
        )
        if changed_plan_dates:
            action = {
                "type": "UPDATE_PLANNER",
                "affected_dates": changed_plan_dates,
                "focus_date": changed_plan_dates[0],
            }
        elif pantry_after != pantry_before:
            action = {"type": "UPDATE_PANTRY"}
        elif grocery_cart_after != grocery_cart_before:
            action = {"type": "UPDATE_GROCERY_CART"}
        elif latest_recipe_plan_after != latest_recipe_plan_before:
            action = {"type": "UPDATE_RECIPE_GROCERY"}
            
        return ChatResponse(text=text_reply, action=action)
        
    except Exception as e:
        print(f"Chat execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 2. Visual Photo Ingestion & OCR Scanner Endpoint
@app.post("/api/upload-photo")
async def upload_photo_endpoint(
    file: UploadFile = File(...),
    active_user: str = Form(...),
    is_fridge_scan: bool = Form(False),
    message: str = Form("")
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
        
        user_context = message.strip()
        context_instruction = (
            f"\n\nUser accompanying text: {user_context}\n"
            "Use this text as first-class context alongside the image. "
            "If the text provides dish names, quantities, corrections, goals, or pantry instructions, honor it."
            if user_context
            else ""
        )

        # Construct dynamic prompt instructions
        if is_fridge_scan:
            prompt = (
                f"Analyze this fridge shelf photo upload: {file_name}. "
                "1. List all ingredients present.\n"
                "2. PROACTIVELY call the 'add_to_pantry_tool' for each detected ingredient to save it to the shared household pantry in Supabase. "
                "Include the ingredient name, estimated amount, and standard unit (e.g. 'stalks', 'slice', 'whole', 'large', 'tbsp').\n"
                "3. In your response text, summarize the pantry updates in a friendly list."
                f"{context_instruction}"
            )
        else:
            prompt = (
                f"Analyze this food plate photo upload: {file_name} for the user {active_user}. "
                "1. Identify the meal plate dish.\n"
                "2. Estimate total calories and macronutrients (protein, carbs, fat, fiber).\n"
                f"3. PROACTIVELY call the 'log_macros_tool' to write this meal log directly to {active_user}'s intake journal in Supabase.\n"
                "4. In your response text, summarize the nutritional breakdown and confirm it has been logged."
                f"{context_instruction}"
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

        if is_fridge_scan and looks_like_grocery_request(user_context):
            grocery_followup = Content(
                parts=[Part(text=(
                    "The user's fridge/pantry photo has just been processed and pantry stock has been updated. "
                    f"Now answer this grocery request using the updated pantry state: {user_context}\n\n"
                    "Route to recipe_grocery_planner. Generate the requested recipe+ingredient artifact, "
                    "account for pantry-covered items, and save structured native grocery cart rows when this is a grocery request. "
                    "Do not sync to Zepto or Blinkit from chat."
                ))],
                role="user"
            )

            grocery_reply = ""
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=grocery_followup
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    grocery_reply = event.content.parts[0].text

            if grocery_reply:
                text_reply = f"{text_reply}\n\n---\n\n{grocery_reply}"
                
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
        meal_plan = build_meal_plan_week()
        grocery_cart = get_grocery_cart()
        latest_recipe_grocery_plan = get_latest_recipe_grocery_plan_metadata()
        
        return {
            "profile": profile,
            "pantry_stock": pantry,
            "macro_diary": diary,
            "meal_plan": meal_plan,
            "grocery_cart": grocery_cart,
            "latest_recipe_grocery_plan": latest_recipe_grocery_plan
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/meal-plan")
async def get_meal_plan_endpoint(week_start: str):
    """Return one authoritative Monday-Sunday household planning window."""
    try:
        return build_meal_plan_week(week_start)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

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

@app.patch("/api/household/profile")
async def update_household_profile_endpoint(payload: Dict[str, Any]):
    """Persist shared household planning settings before confirming them in UI."""
    try:
        current = get_household_profile()
        profile = update_household_profile(
            diet_preference=payload.get(
                "diet_preference",
                current["diet_preference"],
            ),
            household_size=int(
                payload.get("household_size", current["household_size"])
            ),
            daily_calorie_target=int(
                payload.get(
                    "daily_calorie_target",
                    current["daily_calorie_target"],
                )
            ),
        )
        return {"status": "success", "profile": profile}
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

# 4. Native Grocery Cart Routes
@app.get("/api/grocery/cart")
async def get_grocery_cart_endpoint():
    """Returns the shared household native grocery cart."""
    try:
        return {"grocery_cart": get_grocery_cart()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/grocery/cart/items")
async def add_grocery_cart_item_endpoint(payload: Dict[str, Any]):
    """Adds a manual item to the native grocery cart."""
    try:
        item = add_grocery_cart_item({
            "name": payload.get("name", ""),
            "amount": payload.get("amount", 1),
            "unit": payload.get("unit", "piece"),
            "category": payload.get("category", "General"),
            "source": payload.get("source", "manual"),
            "checked": payload.get("checked", False),
            "alreadyStocked": payload.get("alreadyStocked", False),
            "stockNote": payload.get("stockNote", ""),
        })
        return {"status": "success", "item": item, "grocery_cart": get_grocery_cart()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/grocery/cart/items/{item_id}")
async def update_grocery_cart_item_endpoint(item_id: str, payload: Dict[str, Any]):
    """Updates checked/status/details for one native grocery cart row."""
    try:
        item = update_grocery_cart_item(item_id, payload)
        return {"status": "success", "item": item, "grocery_cart": get_grocery_cart()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/grocery/cart/items/{item_id}")
async def delete_grocery_cart_item_endpoint(item_id: str):
    """Deletes one native grocery cart row."""
    try:
        res = delete_grocery_cart_item(item_id)
        return {"status": "success" if res else "failed", "grocery_cart": get_grocery_cart()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/grocery/cart/planned")
async def clear_planned_grocery_cart_endpoint():
    """Clears only agent-planned native grocery cart rows."""
    try:
        res = clear_planned_grocery_cart()
        return {"status": "success" if res else "failed", "grocery_cart": get_grocery_cart()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 5. Recipe + Grocery Artifact Routes
@app.get("/api/recipe-grocery/plans")
async def list_recipe_grocery_plans_endpoint(limit: int = 10):
    """Returns recent recipe+ingredient artifacts for future recipe UI surfaces."""
    try:
        return {"plans": list_recipe_grocery_plans(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipe-grocery/plans/latest")
async def latest_recipe_grocery_plan_endpoint():
    """Returns the latest full recipe+ingredient artifact."""
    try:
        plans = list_recipe_grocery_plans(limit=1)
        return {"plan": plans[0] if plans else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipe-grocery/plans/{plan_id}")
async def get_recipe_grocery_plan_endpoint(plan_id: str):
    """Returns one recipe+ingredient artifact by id."""
    try:
        plan = get_recipe_grocery_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Recipe+grocery plan not found.")
        return {"plan": plan}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 6. Dynamic Pantry Calculations Route
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

# 7. Blinkit / Zepto Brand-Mapped Exporter Route
@app.post("/api/grocery/export")
async def export_grocery_endpoint(payload: Dict[str, Any]):
    """
    Legacy checkout preview: maps required items to a provider-shaped payload
    using ADK native brand preference memory. Live Zepto sync uses /api/grocery/zepto/sync-cart.
    """
    try:
        items = payload.get("items", [])
        provider = payload.get("provider", "blinkit")
        
        result = await export_to_delivery(items=items, provider=provider)
        return {"status": "success", "result": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/grocery/zepto/status")
async def zepto_status_endpoint():
    """Returns Zepto MCP configuration status for the grocery review UI."""
    try:
        return ZeptoProviderAdapter().status()
    except Exception as e:
        return {
            "provider": "zepto",
            "enabled": False,
            "state": "failed",
            "message": str(e),
        }

@app.get("/api/grocery/zepto/addresses")
async def zepto_addresses_endpoint():
    """Returns saved addresses so the user can choose store context before sync."""
    try:
        result = await ZeptoProviderAdapter().list_addresses()
        if result.get("status") != "success":
            return JSONResponse(
                status_code=502,
                content={
                    "detail": {
                        "code": result.get("code", "zepto_address_lookup_failed"),
                        "message": result.get("message", "Kitch could not read Zepto delivery addresses."),
                        "provider": "zepto",
                        "retryable": True,
                    }
                },
            )
        return result
    except Exception:
        return JSONResponse(
            status_code=502,
            content={
                "detail": {
                    "code": "zepto_address_lookup_failed",
                    "message": "Kitch could not read Zepto delivery addresses.",
                    "provider": "zepto",
                    "retryable": True,
                }
            },
        )

@app.post("/api/grocery/zepto/sync-cart")
async def sync_zepto_cart_endpoint(payload: Dict[str, Any] | None = None):
    """
    Replaces the user's Zepto cart with approved native Kitch cart rows.
    This does not place an order.
    """
    operation_id = str(uuid4())
    if not claim_provider_checkout_operation(operation_id):
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "code": "provider_checkout_busy",
                    "message": "Another Zepto checkout operation is already running.",
                    "provider": "zepto",
                    "retryable": True,
                }
            },
        )
    try:
        payload = payload or {}
        selected_ids = {str(i) for i in payload.get("cart_item_ids", [])}
        selected_address_id = str(payload.get("selected_address_id") or "").strip()
        if not selected_address_id:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": {
                        "code": "zepto_address_required",
                        "message": "Select a Zepto delivery address before moving items to the cart.",
                        "provider": "zepto",
                        "retryable": False,
                    }
                },
            )

        cart_items = get_grocery_cart()
        export_items = [
            item for item in cart_items
            if not item.get("alreadyStocked")
            and (not selected_ids or str(item.get("id")) in selected_ids)
        ]

        mapped_items = await apply_brand_memory_to_cart_items(export_items)
        result = await ZeptoProviderAdapter().sync_cart(
            mapped_items,
            selected_address_id=selected_address_id,
        )
        if result.get("status") == "error":
            return JSONResponse(
                status_code=502,
                content={
                    "detail": {
                        "code": result.get("code"),
                        "message": result.get("message"),
                        "provider": "zepto",
                        "retryable": result.get("code") not in {
                            "missing_select_address_tool",
                            "missing_cart_tools",
                        },
                    }
                },
            )

        review = save_initial_draft(
            export_items,
            mapped_items,
            result,
            selected_address_id,
        )
        return {
            "status": result.get("status", "error"),
            "provider": "zepto",
            "result": result,
            "review": review,
            "review_id": review["review_id"],
            "confirmation_token": review.get("confirmation_token")
        }
    finally:
        release_provider_checkout_operation(operation_id)


@app.get("/api/grocery/zepto/checkout-draft")
async def get_zepto_checkout_draft_endpoint():
    """Restore the durable checkout draft without contacting Zepto."""
    draft = draft_row_to_review(get_provider_checkout_draft())
    return {"status": "success", "provider": "zepto", "draft": draft}


@app.patch("/api/grocery/zepto/checkout-draft")
async def update_zepto_checkout_draft_endpoint(payload: Dict[str, Any]):
    """Update payment and explicit review acknowledgement on the durable draft."""
    draft_row = get_provider_checkout_draft()
    if not draft_row:
        raise HTTPException(status_code=404, detail="No Zepto checkout draft exists.")
    allowed_fields = {
        key: payload[key]
        for key in (
            "selected_payment_method_id",
            "order_review_acknowledged",
        )
        if key in payload
    }
    if not allowed_fields:
        raise HTTPException(status_code=422, detail="No supported checkout fields were provided.")
    review = update_draft_review_fields(draft_row, allowed_fields)
    return {"status": "success", "provider": "zepto", "draft": review}


@app.post("/api/grocery/zepto/revalidate-cart")
async def revalidate_zepto_cart_endpoint():
    """Revalidate and automatically repair a durable Zepto checkout draft."""
    operation_id = str(uuid4())
    if not claim_provider_checkout_operation(operation_id):
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "code": "provider_checkout_busy",
                    "message": "Another Zepto checkout operation is already running.",
                    "provider": "zepto",
                    "retryable": True,
                }
            },
        )
    try:
        draft_row = get_provider_checkout_draft()
        if not draft_row or not draft_row.get("native_items"):
            raise HTTPException(status_code=404, detail="No Zepto checkout draft exists.")
        if not native_snapshot_matches(draft_row, get_grocery_cart()):
            review = invalidate_draft_for_native_drift(draft_row)
            return JSONResponse(
                status_code=409,
                content={
                    "detail": {
                        "code": "native_cart_changed",
                        "message": "The native cart changed. Move the selected items to Zepto again.",
                        "provider": "zepto",
                        "retryable": False,
                        "draft": review,
                    }
                },
            )

        result = await ZeptoProviderAdapter().revalidate_cart(
            draft_row_to_review(draft_row) or {}
        )
        if result.get("status") == "error":
            return JSONResponse(
                status_code=502,
                content={
                    "detail": {
                        "code": result.get("code", "zepto_revalidation_failed"),
                        "message": result.get("message", "Zepto cart revalidation failed."),
                        "provider": "zepto",
                        "retryable": True,
                    }
                },
            )
        review, changed = save_revalidated_draft(draft_row, result)
        return {
            "status": result.get("status", "error"),
            "provider": "zepto",
            "changed": changed,
            "changes": result.get("changes") or [],
            "draft": review,
        }
    finally:
        release_provider_checkout_operation(operation_id)

@app.post("/api/grocery/zepto/place-order")
async def place_zepto_order_endpoint(payload: Dict[str, Any]):
    """
    Places the reviewed Zepto cart order. Requires explicit frontend approval
    through a confirmation token returned by /sync-cart.
    """
    operation_id = str(uuid4())
    if not claim_provider_checkout_operation(operation_id):
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "code": "provider_checkout_busy",
                    "message": "Another Zepto checkout operation is already running.",
                    "provider": "zepto",
                    "retryable": True,
                }
            },
        )
    try:
        review_id = payload.get("review_id", "")
        confirmation_token = payload.get("confirmation_token", "")
        approved_snapshot_hash = payload.get("approved_snapshot_hash", "")
        draft_row = get_provider_checkout_draft()
        review = draft_row_to_review(draft_row)
        if not draft_row or not review or review_id != review.get("review_id"):
            raise HTTPException(status_code=404, detail="Zepto checkout draft was not found.")

        if not review.get("can_place_order"):
            raise HTTPException(status_code=403, detail="This Zepto review is not eligible for order placement.")
        if not confirmation_token or confirmation_token != review.get("confirmation_token"):
            raise HTTPException(status_code=403, detail="Final frontend approval token is missing or expired.")
        if approved_snapshot_hash != review.get("snapshot_hash"):
            raise HTTPException(status_code=409, detail="Zepto review changed after approval. Review the cart again before placing the order.")
        if not payload.get("order_review_acknowledged") or not review.get("order_review_acknowledged"):
            raise HTTPException(status_code=403, detail="Final order review acknowledgement is required.")

        if not native_snapshot_matches(draft_row, get_grocery_cart()):
            changed_review = invalidate_draft_for_native_drift(draft_row)
            return JSONResponse(
                status_code=409,
                content={
                    "detail": {
                        "code": "native_cart_changed",
                        "message": "The native cart changed after approval. Sync and review it again.",
                        "provider": "zepto",
                        "retryable": False,
                        "draft": changed_review,
                    }
                },
            )

        validation = await ZeptoProviderAdapter().revalidate_cart(review)
        if validation.get("status") == "error":
            return JSONResponse(
                status_code=502,
                content={
                    "detail": {
                        "code": validation.get("code", "zepto_revalidation_failed"),
                        "message": validation.get("message", "Zepto cart revalidation failed."),
                        "provider": "zepto",
                        "retryable": True,
                    }
                },
            )
        refreshed_review, changed = save_revalidated_draft(draft_row, validation)
        if changed or refreshed_review.get("snapshot_hash") != approved_snapshot_hash:
            return JSONResponse(
                status_code=409,
                content={
                    "detail": {
                        "code": "provider_cart_changed",
                        "message": "The Zepto cart changed during the final availability check. Review it again before ordering.",
                        "provider": "zepto",
                        "retryable": False,
                        "draft": refreshed_review,
                    }
                },
            )
        if not refreshed_review.get("can_place_order"):
            raise HTTPException(status_code=403, detail="The refreshed Zepto cart is not eligible for ordering.")

        result = await ZeptoProviderAdapter().place_order(review=refreshed_review)
        if result.get("status") == "success":
            delete_provider_checkout_draft()
        return {"status": result.get("status", "error"), "provider": "zepto", "result": result, "review": refreshed_review}
    except HTTPException:
        raise
    finally:
        release_provider_checkout_operation(operation_id)

@app.get("/api/health")
async def health_check():
    """Readiness check for elevated access, schema, and household config."""
    try:
        readiness = validate_persistence_readiness()
        return {
            "status": "ready",
            "engine": "google-adk",
            "memory": "ephemeral-process-local",
            "persistence": readiness,
        }
    except PersistenceError as error:
        return JSONResponse(
            status_code=503,
            content={"detail": error.public_detail()},
        )
    except PersistenceConfigurationError:
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "persistence_misconfigured",
                    "message": "Kitch durable storage is not configured correctly.",
                    "operation": "readiness_check",
                    "retryable": False,
                }
            },
        )
