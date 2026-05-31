# Kitch: Current AI Architecture

Kitch's AI layer is a Google ADK 2.0 multi-agent system behind a FastAPI gateway. Agents perform reasoning and intent routing. Python tools perform side effects. Supabase stores structured application state. ADK memory stores flexible household brand preferences.

---

## Runtime Shape

```mermaid
flowchart LR
    User[Household Member] --> Frontend[Next.js App]
    Frontend --> API[FastAPI Gateway]
    API --> Runner[ADK Runner]
    Runner --> App[ADK App]
    App --> Coordinator[kitch_coordinator]
    Coordinator --> Chef[chef_planner]
    Coordinator --> Vision[vision_scanner]
    Coordinator --> Checkout[checkout_exporter]
    Chef --> Tools[Python Tools]
    Vision --> Tools
    Checkout --> Tools
    Tools --> Supabase[(Supabase)]
    Checkout --> Memory[ADK InMemoryMemoryService]
    Runner --> Sessions[ADK InMemorySessionService]
    Checkout --> Zepto[Zepto MCP Adapter]
```

The browser never calls agents directly. It calls FastAPI. FastAPI creates ADK-compatible messages, runs the ADK `Runner`, and returns the final agent response plus any state-sync hint.

---

## ADK Primitives

Location: `backend/app/agent/core.py`

Current primitives:

- `LlmAgent`
- `Runner`
- `App`
- `InMemorySessionService`
- `InMemoryMemoryService`
- `EventsCompactionConfig`
- `LlmEventSummarizer`
- ADK Gemini or LiteLLM model adapters, selected by environment variables.

The local in-memory services are intentional for development. They will be replaced by Vertex AI managed session and memory services after deployment testing.

---

## Agent Team

### `kitch_coordinator`

Parent triage agent.

Responsibilities:

- Understand the user's intent.
- Route meal planning and schedule questions to `chef_planner`.
- Route food logging, macro diary, pantry, and image tasks to `vision_scanner`.
- Route grocery, shopping list, brand preference, and Zepto/Blinkit requests to `checkout_exporter`.
- Answer simple general chat directly.

### `chef_planner`

Meal planning and recipe reasoning agent.

Responsibilities:

- Generate dynamic meal plans.
- Treat "next week" as the upcoming Monday-Sunday planning window.
- Include exact dates in meal-plan responses.
- Save structured weekly meal plans to Supabase.
- Store actual recipe names, not recipe IDs.
- Update one meal slot without rewriting the rest of the plan.
- Answer schedule questions such as "what's for dinner tonight?"

There is no static recipe database.

### `vision_scanner`

Food intake and pantry/fridge scanning agent.

Responsibilities:

- Estimate macros from text meal descriptions.
- Estimate macros from plate photos.
- Log meals to the active member's macro diary.
- Detect pantry/fridge items from text or photos.
- Add detected stock to the shared household pantry.

If a fridge photo is submitted with a grocery request, the API first runs the photo/pantry update turn, then runs a follow-up grocery-planning turn against the updated pantry.

### `checkout_exporter`

Grocery planning, brand preference, and provider-prep agent.

Responsibilities:

- Read the shared weekly plan.
- Read shared pantry stock.
- Infer ingredients from dynamic recipe names or one-off dish requests.
- Scale grocery requirements for household size.
- Save structured native grocery cart rows with `save_grocery_cart_tool`.
- Include pantry-covered rows with `alreadyStocked=true`.
- Preserve manual cart rows by replacing only `source=agent` rows.
- Store household brand preferences in ADK memory.
- Sync native cart rows to Zepto when the user asks for Zepto.
- Never place an order from chat.

---

## Tool Boundary

Meal tools:

- `get_weekly_schedule_tool`
- `save_weekly_plan_tool`
- `update_single_meal_in_schedule`
- `get_current_datetime`

Pantry and macro tools:

- `get_pantry_stock_tool`
- `add_to_pantry_tool`
- `log_macros_tool`
- `get_macro_diary_tool`

Grocery and provider tools:

- `get_grocery_cart_tool`
- `save_grocery_cart_tool`
- `clear_planned_grocery_cart_tool`
- `set_brand_preference`
- `get_brand_preference`
- `sync_native_cart_to_zepto_tool`
- `get_zepto_cart_tool`
- `place_zepto_order_tool`
- `export_to_delivery`

Safety note:

- `place_zepto_order_tool` is intentionally non-executing from chat. Real order placement happens only through the backend approval endpoint after a frontend button click.

---

## Session State Injection

FastAPI syncs these values into ADK session state before each chat turn:

- `user:profile_name`
- `user:dietary_profile`
- `app:household_size`
- `app:household_members`

The before-agent callback injects:

- `current_datetime`
- `current_day_of_week`
- `current_date`
- `planning_week_start`
- `planning_week_end`
- `planning_week_dates`

This lets agents reason about today's real date separately from the upcoming planning week.

---

## Memory Model

Supabase stores structured app state:

- Meal plans.
- Pantry stock.
- Grocery cart rows.
- Macro logs.
- Household profile settings.

ADK memory stores flexible household preferences:

- Brand preferences such as `butter: Amul butter`.
- Provider search mapping hints.

Brand memory affects provider search terms, not the generic native cart row. Example: the native cart row remains `butter`, while Zepto search may use `Amul butter`.

---

## Context Compaction

The ADK `App` uses `EventsCompactionConfig` with `LlmEventSummarizer`.

Current settings:

- `compaction_interval=4`
- `overlap_size=1`

This keeps long-running sessions from growing without bound while preserving recent conversational context.
