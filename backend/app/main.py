# Kitch: FastAPI Production Gateway Server (Google ADK 2.0)

import hashlib
import json
import time
from uuid import uuid4
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from app.schemas import ChatRequest, ChatResponse
from app.agent.core import runner, session_service
from app.agent.tools import get_weekly_schedule_dict, export_to_delivery, apply_brand_memory_to_cart_items
from app.providers.zepto import ZeptoProviderAdapter
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
    update_household_profile,
    validate_persistence_readiness,
)
from app.persistence import (
    PersistenceConfigurationError,
    PersistenceError,
    begin_persistence_scope,
    end_persistence_scope,
    raise_recorded_persistence_failure,
)

load_dotenv()

ZEPTO_ORDER_REVIEWS: Dict[str, Dict[str, Any]] = {}
ZEPTO_ORDER_REVIEW_TTL_SECONDS = 60 * 60

def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_json_safe(v) for v in value]
        return str(value)

def _review_hash(review: Dict[str, Any]) -> str:
    stable_payload = {
        "native_items": review.get("native_items", []),
        "mapped_items": review.get("mapped_items", []),
        "matched_items": review.get("matched_items", []),
        "unavailable_items": review.get("unavailable_items", []),
        "zepto_cart": review.get("zepto_cart"),
        "cart_summary": review.get("cart_summary"),
        "selected_address_id": review.get("selected_address_id"),
        "selected_payment_method_id": review.get("selected_payment_method_id"),
    }
    encoded = json.dumps(_json_safe(stable_payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def _prune_zepto_reviews() -> None:
    cutoff = time.time() - ZEPTO_ORDER_REVIEW_TTL_SECONDS
    expired = [
        review_id for review_id, review in ZEPTO_ORDER_REVIEWS.items()
        if float(review.get("created_at", 0)) < cutoff
    ]
    for review_id in expired:
        ZEPTO_ORDER_REVIEWS.pop(review_id, None)

def _build_zepto_order_review(
    native_items: List[Dict[str, Any]],
    mapped_items: List[Dict[str, Any]],
    result: Dict[str, Any],
    selected_address_id: str,
) -> Dict[str, Any]:
    review_id = f"zepto_review_{uuid4()}"
    matched_items = result.get("items") or []
    unavailable_items = result.get("unavailable_items") or []
    checkout_context = result.get("checkout_context") or {}
    order_blockers: List[str] = []

    if result.get("status") != "success" or len(matched_items) == 0:
        order_blockers.append("Zepto cart sync must succeed with at least one Zepto cart item.")
    if checkout_context.get("address_error"):
        order_blockers.append("Zepto address options could not be read.")
    if checkout_context.get("payment_error"):
        order_blockers.append("Zepto payment options could not be read.")
    if result.get("store_context", {}).get("status") != "ready":
        order_blockers.append("Zepto store context is not ready for the selected address.")

    can_place_order = len(order_blockers) == 0
    confirmation_token = f"kitch_confirm_{uuid4()}" if can_place_order else None

    review = {
        "review_id": review_id,
        "provider": "zepto",
        "status": result.get("status", "error"),
        "native_items": native_items,
        "mapped_items": mapped_items,
        "matched_items": matched_items,
        "unavailable_items": unavailable_items,
        "zepto_cart": result.get("zepto_cart"),
        "cart_summary": result.get("cart_summary") or {
            "currency": "INR",
            "subtotal_minor": None,
            "discount_minor": None,
            "fees": [],
            "total_minor": None,
            "total_source": "unavailable",
            "total_notice": "Zepto did not return a final cart total.",
        },
        "checkout_context": checkout_context,
        "store_context": result.get("store_context") or {},
        "available_tools": result.get("available_tools") or [],
        "selected_address_id": selected_address_id,
        "selected_payment_method_id": None,
        "order_review_acknowledged": False,
        "can_place_order": can_place_order,
        "order_blockers": order_blockers,
        "confirmation_token": confirmation_token,
        "created_at": time.time(),
        "updated_at": time.time(),
        "message": result.get("message", ""),
    }

    review["snapshot_hash"] = _review_hash(review)
    ZEPTO_ORDER_REVIEWS[review_id] = review
    return review

def _get_zepto_review(review_id: str) -> Dict[str, Any]:
    _prune_zepto_reviews()
    review = ZEPTO_ORDER_REVIEWS.get(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Zepto review was not found or has expired.")
    return review

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
    Refuse startup unless durable storage is correctly configured and ready.
    """
    validate_persistence_readiness()
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
            household_size=payload.household_size
        )

        weekly_plan_before = get_weekly_schedule_dict()
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
                
        weekly_plan_after = get_weekly_schedule_dict()
        pantry_after = get_pantry_stock()
        grocery_cart_after = get_grocery_cart()
        latest_recipe_plan_after = get_latest_recipe_grocery_plan_metadata()

        # Only confirmed persisted state changes can produce mutation actions.
        action = None
        
        if weekly_plan_after and weekly_plan_after != weekly_plan_before:
            action = {"type": "UPDATE_PLANNER"}
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
        weekly_plan = get_weekly_schedule_dict()
        grocery_cart = get_grocery_cart()
        latest_recipe_grocery_plan = get_latest_recipe_grocery_plan_metadata()
        
        return {
            "profile": profile,
            "pantry_stock": pantry,
            "macro_diary": diary,
            "weekly_plan": weekly_plan,
            "grocery_cart": grocery_cart,
            "latest_recipe_grocery_plan": latest_recipe_grocery_plan
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
        if result.get("status") == "error" and result.get("code") in {
            "address_required",
            "missing_select_address_tool",
            "store_context_unavailable",
        }:
            return JSONResponse(
                status_code=502,
                content={
                    "detail": {
                        "code": result.get("code"),
                        "message": result.get("message"),
                        "provider": "zepto",
                        "retryable": result.get("code") != "missing_select_address_tool",
                    }
                },
            )

        review = _build_zepto_order_review(
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
    except Exception as e:
        return {
            "status": "error",
            "provider": "zepto",
            "result": {
                "status": "error",
                "provider": "zepto",
                "code": "mcp_sync_failed",
                "message": str(e)
            },
            "confirmation_token": None
        }

@app.get("/api/grocery/zepto/review/{review_id}")
async def get_zepto_review_endpoint(review_id: str):
    """Returns a saved Zepto cart/order review snapshot."""
    return {"status": "success", "provider": "zepto", "review": _get_zepto_review(review_id)}

@app.patch("/api/grocery/zepto/review/{review_id}")
async def update_zepto_review_endpoint(review_id: str, payload: Dict[str, Any]):
    """
    Updates user-selected review metadata before final order approval.
    This never calls Zepto or places an order.
    """
    review = _get_zepto_review(review_id)
    allowed_fields = (
        "selected_payment_method_id",
        "order_review_acknowledged",
    )
    for field in allowed_fields:
        if field in payload:
            review[field] = payload[field]
    review["updated_at"] = time.time()
    review["snapshot_hash"] = _review_hash(review)
    return {"status": "success", "provider": "zepto", "review": review}

@app.post("/api/grocery/zepto/place-order")
async def place_zepto_order_endpoint(payload: Dict[str, Any]):
    """
    Places the reviewed Zepto cart order. Requires explicit frontend approval
    through a confirmation token returned by /sync-cart.
    """
    try:
        review_id = payload.get("review_id", "")
        confirmation_token = payload.get("confirmation_token", "")
        approved_snapshot_hash = payload.get("approved_snapshot_hash", "")
        review = _get_zepto_review(review_id)

        if not review.get("can_place_order"):
            raise HTTPException(status_code=403, detail="This Zepto review is not eligible for order placement.")
        if not confirmation_token or confirmation_token != review.get("confirmation_token"):
            raise HTTPException(status_code=403, detail="Final frontend approval token is missing or expired.")
        if approved_snapshot_hash != review.get("snapshot_hash"):
            raise HTTPException(status_code=409, detail="Zepto review changed after approval. Review the cart again before placing the order.")
        if not payload.get("order_review_acknowledged") and not review.get("order_review_acknowledged"):
            raise HTTPException(status_code=403, detail="Final order review acknowledgement is required.")

        result = await ZeptoProviderAdapter().place_order(review=review)
        if result.get("status") == "success":
            ZEPTO_ORDER_REVIEWS.pop(review_id, None)
        return {"status": result.get("status", "error"), "provider": "zepto", "result": result, "review": review}
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "provider": "zepto",
            "result": {
                "status": "error",
                "provider": "zepto",
                "code": "mcp_order_failed",
                "message": str(e)
            }
        }

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
