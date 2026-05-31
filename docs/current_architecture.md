# Kitch: Current Architecture and Implementation Guide

This document replaces the older implementation plan. It describes the app as it exists now: a Google ADK 2.0 multi-agent backend, a Next.js dashboard, Supabase persistence, and temporary in-memory ADK services that will later be replaced by Vertex AI managed services.

The goal of this document is separation of concerns. Frontend behavior stays in the frontend section. Agent topology stays in the agent section. Database details stay in the persistence section.

---

## 1. System Shape

Kitch is a household meal planning, nutrition logging, pantry tracking, and grocery checkout assistant.

At runtime it is split into three major surfaces:

1. **Next.js frontend**
   - Runs the dashboard and chat UI.
   - Displays planner, macro diary, pantry, grocery cart, and checkout approval flows.
   - Calls the FastAPI backend over HTTP.

2. **FastAPI backend gateway**
   - Owns all browser-facing API routes.
   - Creates and syncs ADK sessions.
   - Converts chat text and uploaded images into ADK `Content` messages.
   - Reads and writes Supabase state through a small Python client wrapper.

3. **Google ADK 2.0 agent layer**
   - Uses a parent `kitch_coordinator` agent with three specialized sub-agents.
   - Uses ADK `Runner`, `App`, `LlmAgent`, event compaction, `InMemorySessionService`, and `InMemoryMemoryService`.
   - Calls Python tools for meal plans, pantry updates, macro logs, brand preferences, and checkout export.

```mermaid
flowchart LR
    Frontend[Next.js Dashboard] -->|HTTP fetch| API[FastAPI Gateway]
    API -->|runner.run_async| Runner[ADK Runner]
    Runner --> App[ADK App]
    App --> Coordinator[kitch_coordinator]
    Coordinator --> Chef[chef_planner]
    Coordinator --> Vision[vision_scanner]
    Coordinator --> Checkout[checkout_exporter]
    Chef --> Tools[Python Tool Layer]
    Vision --> Tools
    Checkout --> Tools
    Tools --> Supabase[(Supabase)]
    Checkout --> Memory[ADK InMemoryMemoryService]
```

---

## 2. Frontend Duties

The frontend lives under `frontend/src/app`.

Its job is presentation and user interaction. It should not own agent reasoning, long-term brand memory, or database rules.

### Current Responsibilities

- Render the main Kitch app shell in `page.js`.
- Let the user switch active household member.
- Let the user switch diet profile and household size.
- Render chat history and send user messages to `/api/chat`.
- Upload fridge and plate photos to `/api/upload-photo`.
- Render Supabase-backed pantry and macro diary state from `/api/state/{user_name}`.
- Provide manual pantry add/remove controls.
- Render the shared planner, shared pantry, manual cart items, and checkout payload review modal.
- Call `/api/grocery/export` after the user approves checkout.

### Current State

The frontend no longer owns a static recipe catalog or default weekly recipe IDs.

- Backend returns planner rows as display-ready meal names.
- The planner renders the actual recipe name strings saved by the ADK chef planner.
- The planner displays an explicit upcoming Monday-Sunday date window. It does not label future plan days as "Today" just because the weekday matches the current weekday.
- Meal swaps are requested through chat, not through a local static recipe picker.
- `mockData.js` currently contains diet macro targets only.

### Current Limitation

Structured grocery list rendering is still not fully backend-driven. Kitch can compile grocery lists conversationally through `checkout_exporter`, but the dashboard cart currently contains only manually added items until a structured grocery-list API is implemented.

---

## 3. API Gateway Duties

The FastAPI backend lives in `backend/app/main.py`.

Its job is orchestration between browser requests, ADK runner turns, and persistence. It should not contain UI policy or deep agent reasoning.

### Current Routes

| Route | Duty |
| :--- | :--- |
| `POST /api/chat` | Runs a text chat turn through the ADK runner. |
| `POST /api/upload-photo` | Sends image bytes plus task instructions to the ADK runner. |
| `GET /api/state/{user_name}` | Returns profile, pantry, macro diary, and weekly plan state. |
| `POST /api/pantry/add` | Adds pantry stock manually. |
| `DELETE /api/pantry/remove/{user_name}/{item_name}` | Removes pantry stock manually. |
| `POST /api/diary/clear/{user_name}` | Clears a user's macro diary. |
| `POST /api/grocery/calculate` | Placeholder for future structured grocery-list generation. |
| `POST /api/grocery/export` | Prepares provider payloads with brand-memory mapping. Real MCP cart insertion is deferred. |
| `GET /api/health` | Health check. |

### Session Sync

Before each ADK turn, the backend ensures a session exists for the active user.

It writes these values into ADK session state:

- `user:profile_name`
- `user:dietary_profile`
- `app:household_size`
- `app:household_members`

This lets the coordinator and sub-agents reason with the current user profile without pushing all app state into every prompt manually.

### Multimodal Handling

Photo upload uses ADK-compatible content parts:

- A text prompt describing whether this is a fridge scan or plate scan, including any text the user typed alongside the image.
- An image part built from uploaded file bytes.

The agent is instructed to call tools directly:

- Fridge scan: call `add_to_pantry_tool`.
- Plate scan: call `log_macros_tool`.

---

## 4. Agent Topology Duties

The agent layer lives in `backend/app/agent/core.py`.

Its job is intent routing and domain-specific reasoning. It should not know frontend layout details.

### Runtime Framework

Current runtime primitives:

- `google.adk.agents.llm_agent.LlmAgent`
- `google.adk.runners.Runner`
- `google.adk.apps.app.App`
- `google.adk.sessions.InMemorySessionService`
- `google.adk.memory.InMemoryMemoryService`
- `google.adk.apps.llm_event_summarizer.LlmEventSummarizer`
- `google.adk.apps.app.EventsCompactionConfig`

### Model Access

The ADK agents currently use `LiteLlm` in OpenAI-compatible mode.

The model name and gateway credentials are loaded from environment variables:

- `OPENAI_MODEL_NAME`
- `OPENAI_API_KEY`
- `OPENAI_API_BASE`

### Coordinator Agent

`kitch_coordinator` is the parent agent.

Its duties:

- Interpret the user's intent.
- Route meal planning requests to `chef_planner`.
- Route food logging, macro diary, pantry, and image requests to `vision_scanner`.
- Route shopping, grocery list, brand preference, and checkout requests to `checkout_exporter`.
- Answer simple general chat directly.

It has no domain tools of its own.

### Chef Planner Agent

`chef_planner` owns meal planning and recipe reasoning.

Its duties:

- Generate dynamic weekly meal plans.
- Treat "next week" planning as the upcoming Monday-Sunday planning window and include exact dates in chat responses.
- Store recipe name strings in Supabase.
- Update a single meal slot without rewriting the rest of the plan.
- Answer "what is for dinner" style schedule questions.
- Scale recipes conversationally for different household sizes or guests.

It does not use a static recipe database.

### Vision Scanner Agent

`vision_scanner` owns intake logging and pantry scanning.

Its duties:

- Estimate macros from text meal descriptions.
- Estimate macros from plate photos.
- Log meals to the active user's macro diary.
- Detect fridge or pantry items from images or text.
- Add detected stock to the shared household pantry.
- Summarize daily intake from diary records.

Macro logs are individual per user. Meal plans and pantry stock are shared across the configured household.

### Checkout Exporter Agent

`checkout_exporter` owns grocery reasoning and delivery preparation.

Its duties:

- Fetch the shared weekly schedule.
- Fetch shared pantry stock.
- Reason about required ingredients from dynamic meal names.
- Scale required quantities for household size.
- Subtract pantry stock.
- Save brand preferences into ADK memory.
- Apply brand preferences during checkout export.
- Prepare delivery-provider payloads after user approval. Live MCP cart insertion is intentionally deferred until a provider connection is configured.

---

## 5. Tool Layer Duties

The tool layer lives in `backend/app/agent/tools.py`.

Its job is to expose small, explicit capabilities to the ADK agents. Tool functions should stay narrow and easy to verify.

### Meal Plan Tools

- `get_weekly_schedule_tool`
- `save_weekly_plan_tool`
- `update_single_meal_in_schedule`
- `get_current_datetime`

These tools read and write the household-owned `meal_plans` rows. Meal columns store recipe names, not recipe IDs.

### Pantry and Macro Tools

- `get_pantry_stock_tool`
- `add_to_pantry_tool`
- `log_macros_tool`
- `get_macro_diary_tool`

These tools delegate to `supabase_client.py`. Pantry tools operate on shared household stock; macro tools operate on the active user's diary.

### Brand Memory Tools

- `set_brand_preference`
- `get_brand_preference`

Brand preferences currently use ADK native memory.

The current memory namespace is:

- `app_name="kitch"`
- `user_id="shared_household"`

This matches the current prototype approach. It is intentionally not stored in a markdown file anymore.

### Checkout Export Tool

- `export_to_delivery`

This tool:

- Filters items that are already checked or stocked.
- Searches ADK memory for brand preferences.
- Replaces generic names with preferred branded names when a memory match exists.
- Returns a provider payload preview for the selected provider. It does not place a live order or push to a real cart yet.

Provider names currently supported:

- `blinkit`
- `zepto`

---

## 6. Persistence Duties

Persistence currently lives in Supabase and the ADK in-memory services.

### Supabase Tables

The SQL schema lives in `backend/database/supabase_schema.sql`.

| Table | Duty |
| :--- | :--- |
| `profiles` | Stores prototype member records and the shared household planning profile. |
| `meal_plans` | Stores household planned recipe name strings by day and meal slot. |
| `pantry_stock` | Stores shared household ingredient name, amount, and unit. |
| `macro_diary` | Stores individual meal logs and macro estimates. |

### Supabase Client Wrapper

`backend/app/supabase_client.py` owns direct Supabase access.

Prototype household membership is centralized in `backend/app/household_config.py`. It pre-fills the current household members and fixed local UUIDs:

- `Archit`
- `Anubhav`
- `Naman`

This is a local prototype shortcut. Production auth and multi-household registration should replace this fixed mapping later. Until then, meal plans and pantry stock reuse one configured household owner profile ID, while macro diary reads and writes remain user-specific.

### ADK Session Service

Current:

- `InMemorySessionService`

Later:

- `VertexAISessionService`

The session service stores conversation/session state for active ADK turns.

### ADK Memory Service

Current:

- `InMemoryMemoryService`

Later:

- `VertexAIMemoryBank`

The memory service stores household brand preferences and other durable agent memories during local testing.

---

## 7. Checkout and Human Approval Duties

Checkout payload review begins in the frontend and execution happens through the backend.

### Frontend Duty

The frontend:

- Shows a review modal.
- Displays the cart payload.
- Requires explicit user approval.
- Calls `/api/grocery/export` only after approval.

### Backend Duty

The backend:

- Receives approved checkout items.
- Calls `export_to_delivery`.
- Returns the provider payload preview.

### Agent and Tool Duty

The checkout exporter:

- Produces or receives the intended grocery items.
- Applies brand memory.
- Targets a provider such as Blinkit or Zepto.

Actual provider automation is intentionally not wired yet. A real MCP adapter can replace the current preview implementation without changing the frontend approval concept.

---

## 8. Known Current Gaps

These are not failures of the architecture, but they are important current-state boundaries.

1. **Structured grocery list state is still pending.**
   - Grocery lists can be generated conversationally by the agent.
   - The dashboard does not yet consume a structured grocery-list artifact from the backend.

2. **`/api/grocery/calculate` is a placeholder.**
   - It currently returns an empty grocery list.
   - The production direction is backend or agent-driven grocery list generation.

3. **Provider cart insertion is not wired.**
   - `/api/grocery/export` prepares provider payloads and applies brand memory.
   - It does not call a real Blinkit or Zepto MCP server yet.

4. **Prototype identity is fixed-name based.**
   - Current users map to configured UUIDs in `household_config.py`.
   - Real auth should replace this after the core local flows are stable.

5. **Brand memory is in-memory for now.**
   - This is expected during local testing.
   - Deployment should switch it to Vertex AI Memory Bank.

---

## 9. Deployment Direction

The intended evolution is:

1. Keep the current local architecture stable.
2. Move session persistence from `InMemorySessionService` to `VertexAISessionService`.
3. Move brand and household memory from `InMemoryMemoryService` to `VertexAIMemoryBank`.
4. Replace fixed UUID user mapping with real auth-backed identity.
5. Add a structured grocery-list artifact/API that the frontend can render.
6. Replace the checkout preview shim with real provider MCP adapters.

---

## 10. Design Principle

Kitch should remain split by duty:

- Frontend renders and collects user approval.
- FastAPI coordinates requests and session state.
- ADK agents reason and choose tools.
- Tools perform explicit side effects.
- Supabase stores structured application data.
- ADK memory stores agent-native household preferences.

This separation keeps the app easier to debug now and easier to migrate to managed Vertex AI services later.
