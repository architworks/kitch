# Kitch: Current System Design

This document describes the current end-to-end system design: frontend, backend gateway, ADK runtime, persistence, provider adapters, and approval boundaries.

For product intent, read `vision_and_requirements.md`.
For AI runtime and agent roles, read `current_ai_agent_architecture.md`.
For concrete stack/configuration, read `current_technology_stack.md`.

---

## System Summary

Kitch is a household meal planning, recipe, grocery, pantry, nutrition, and delivery-prep app.

The current design separates responsibilities deliberately:

- The frontend renders state and collects explicit user actions.
- FastAPI owns browser-facing APIs, state hydration, multimodal request orchestration, and provider approval boundaries.
- ADK agents reason about user intent and call Python tools.
- Python tools perform deterministic side effects.
- Supabase stores authoritative structured product state.
- ADK memory stores explicitly ephemeral household food and brand preferences.
- Provider adapters translate Kitch's native cart into provider carts.

```mermaid
flowchart LR
    Browser[Browser / Next.js UI] -->|HTTP| API[FastAPI Gateway]
    API -->|runner.run_async| Runner[ADK Runner]
    Runner --> Coordinator[kitch_coordinator]
    Coordinator --> Chef[chef_planner]
    Coordinator --> Vision[vision_scanner]
    Coordinator --> RecipeGrocery[recipe_grocery_planner]

    Chef --> Tools[Python Tool Layer]
    Vision --> Tools
    RecipeGrocery --> Tools

    Tools --> Supabase[(Supabase PostgreSQL)]
    RecipeGrocery --> Memory[ADK Memory]
    Runner --> Sessions[ADK Sessions]

    API --> ZeptoAdapter[ZeptoProviderAdapter]
    ZeptoAdapter --> ZeptoMCP[Zepto MCP]
```

---

## Core Design Decisions

### Google ADK is the app runtime

Kitch uses Google ADK 2.0 for the runtime agent graph.

**Why:** the product needs explicit agent routing, tools, multimodal message support, session state, memory, callbacks, and context compaction. ADK provides these as application runtime primitives and has a path to Vertex AI managed services. Antigravity SDK remains useful for development workflows, but Kitch should not depend on a development harness as the production runtime.

### FastAPI sits between the browser and agents

The browser never calls agents directly. It calls FastAPI.

**Why:** FastAPI can normalize payloads, sync session state, orchestrate photo-plus-text flows, guard provider/order actions, and return a stable API shape to the frontend. This keeps the frontend free of ADK runtime details.

### Supabase stores structured product records

Supabase stores meal plans, recipe+grocery artifacts, pantry stock, native cart rows, profiles, and macro logs.

**Why:** these are deterministic records that the UI must render and users must be able to review. They should not live only in chat memory.

### ADK memory stores flexible preference text

Household food and brand preferences are stored in ADK memory as flexible text.

**Why:** preferences are naturally conversational and can be fuzzy. A strict schema would prematurely constrain how users express preferences and how agents apply them.

### Provider sync is not agent-owned

Zepto sync and order approval sit behind backend HTTP endpoints and `ZeptoProviderAdapter`.

**Why:** provider operations modify real external state. Chat should not be able to place orders. The backend can create review snapshots and require explicit frontend approval before order placement.

---

## Frontend Duties

Location: `frontend/src/app`

The frontend owns presentation and explicit user actions.

Current duties:

- Render the household dashboard.
- Render the Recipes page for recipe+grocery artifacts.
- Render the Groceries page as a provider-neutral, six-stage vertical checkout
  workflow with compact numbered markers and a collapsible native cart.
- Show Zepto as the current live ordering app and Blinkit as a disabled future
  provider without exposing unusable actions.
- Render individual nutrition state.
- Render shared calendar-date plan state with navigable Monday-Sunday views.
- Render pantry/grocery state from backend APIs.
- Send text chat turns to `POST /api/chat`.
- Upload image-plus-text requests to `POST /api/upload-photo`.
- Trigger Zepto cart sync through `POST /api/grocery/zepto/sync-cart`.
- Restore and patch the durable checkout through
  `GET/PATCH /api/grocery/zepto/checkout-draft`.
- Trigger availability repair through `POST /api/grocery/zepto/revalidate-cart`.
- Trigger final order placement through `POST /api/grocery/zepto/place-order`.

The frontend does not:

- Own meal planning logic.
- Generate recipes or groceries.
- Call ADK directly.
- Call Zepto MCP directly.
- Place orders from chat text.
- Store the source of truth for meal plans or carts.

Why:

- The UI should remain a thin product surface over backend-owned state and safety boundaries.
- Explicit button actions are easier to reason about than implicit agent side effects for provider cart and order operations.

---

## Backend Gateway Duties

Location: `backend/app/main.py`

FastAPI owns orchestration, API stability, and safety.

Current routes:

| Route | Duty |
| :--- | :--- |
| `POST /api/chat` | Runs a text chat turn through the ADK runner. |
| `POST /api/upload-photo` | Sends image bytes and optional text to ADK; handles photo-plus-grocery two-step orchestration. |
| `GET /api/state/{user_name}` | Returns dashboard state, including the authoritative current calendar-week meal plan and next chronological meal. |
| `GET /api/meal-plan?week_start=YYYY-MM-DD` | Returns one Monday-Sunday planning window with all seven exact dates, including empty days. |
| `POST /api/pantry/add` | Adds pantry stock manually. |
| `PATCH /api/household/profile` | Persists shared diet and household-size settings. |
| `DELETE /api/pantry/remove/{user_name}/{item_name}` | Removes pantry stock manually. |
| `POST /api/diary/clear/{user_name}` | Clears one user's macro diary. |
| `GET /api/grocery/cart` | Returns the shared native household grocery cart. |
| `POST /api/grocery/cart/items` | Adds a manual native grocery cart row. |
| `PATCH /api/grocery/cart/items/{id}` | Updates one native grocery cart row. |
| `DELETE /api/grocery/cart/items/{id}` | Deletes one native grocery cart row. |
| `DELETE /api/grocery/cart/planned` | Deletes agent-planned cart rows while preserving manual rows. |
| `GET /api/recipe-grocery/plans` | Lists recent recipe+grocery artifacts. |
| `GET /api/recipe-grocery/plans/latest` | Returns the latest recipe+grocery artifact. |
| `GET /api/recipe-grocery/plans/{id}` | Returns one recipe+grocery artifact. |
| `POST /api/grocery/export` | Legacy provider payload preview. |
| `GET /api/grocery/zepto/status` | Returns Zepto configuration state; it does not claim store readiness. |
| `GET /api/grocery/zepto/addresses` | Reads saved Zepto delivery addresses before cart sync. |
| `POST /api/grocery/zepto/sync-cart` | Establishes address/store context, accepts explicitly orderable matches, replaces the cart, reconciles the returned cart, and saves a durable checkout draft. |
| `GET /api/grocery/zepto/checkout-draft` | Restores the current Supabase-backed checkout draft across browser and backend restarts. |
| `PATCH /api/grocery/zepto/checkout-draft` | Updates payment selection and acknowledgement on the durable draft. |
| `POST /api/grocery/zepto/revalidate-cart` | Rechecks current product availability, repairs stale products, reconciles the rebuilt cart, and resets approval after any material change. |
| `POST /api/grocery/zepto/place-order` | Revalidates first, returns `409` when the approved cart changed, and orders only an unchanged explicitly approved snapshot. |
| `GET /api/health` | Readiness check for elevated database access, required schema, and the configured household profile. |

Why the backend owns durable checkout drafts:

- A user must approve the exact provider cart they saw.
- Order placement should not rerun LLM reasoning or product matching after approval.
- Confirmation token plus snapshot hash prevents stale or modified reviews from being submitted silently.
- Persisted operation leases serialize sync, repair, and order operations per household/provider.

---

## Agent Runtime Duties

Location: `backend/app/agent/core.py`

The ADK runtime contains:

- `kitch_coordinator`
- `chef_planner`
- `vision_scanner`
- `recipe_grocery_planner`

Agents reason over:

- User text.
- Optional image content.
- Current date/time.
- Active user.
- Household size.
- Household members.
- Dietary profile.
- Weekly schedule.
- Pantry state.
- Household preferences.

Agents do not reason over:

- UI layout.
- Zepto payment UI state.
- Frontend route state.
- Final order placement.

Why:

- Agents should handle culinary reasoning and state updates through tools.
- UI and provider safety workflows should remain deterministic backend/frontend logic.

---

## Persistence Design

Location: `backend/app/supabase_client.py`
Schema: `backend/database/supabase_schema.sql`

Supabase tables:

| Table | Shared or individual | Duty |
| :--- | :--- | :--- |
| `profiles` | Prototype user/shared profile | Stores configured users and profile defaults. |
| `meal_plans` | Shared household | Stores breakfast/lunch/dinner meal names keyed by exact calendar date. |
| `recipe_grocery_plans` | Shared household | Stores recipe cards, ingredients, pantry notes, request scope, and cart update metadata. |
| `pantry_stock` | Shared household | Stores current pantry/fridge inventory. |
| `grocery_cart_items` | Shared household | Stores native provider-agnostic cart rows. |
| `macro_diary` | Individual | Stores active-user nutrition logs. |
| `provider_checkout_drafts` | Shared household | Stores durable provider cart projections, repair history, approval state, and serialized operation leases. |

Important modeling decisions:

- `meal_plans` is uniquely keyed by `(profile_id, plan_date)`; weekdays are
  derived display labels, so Thursday in one week cannot overwrite another.
- The household profile stores the IANA timezone used to resolve relative dates.
- New plan ranges and targeted multi-meal edits use transactional RPCs.
- The product plans breakfast, lunch, and dinner only.
- `recipe_grocery_plan_id` links agent-created cart rows back to the recipe+grocery artifact that produced them.
- `source=manual` rows survive later agent grocery planning.
- `already_stocked=true` rows remain visible but are excluded from provider sync.

Why this model:

- Meal plans need to be lightweight.
- Recipes and grocery rows need an auditable artifact.
- Provider carts should never become Kitch's source of truth.

### Durable-storage contract

- All seven tables have RLS enabled. Browser roles have no table or sequence
  privileges; the browser accesses state only through FastAPI.
- FastAPI requires `SUPABASE_SECRET_KEY` (`sb_secret_...`) or the temporary
  legacy `SUPABASE_SERVICE_ROLE_KEY`. Publishable, anon, malformed, and
  ambiguous `SUPABASE_KEY` credentials prevent startup.
- Empty reads are valid state. Authorization, connection, schema, malformed
  response, and unconfirmed-write failures are not empty state: they become a
  safe HTTP 503 response and no success action is returned to the UI.
- Saving a recipe artifact and replacing agent-generated cart rows is one
  PostgreSQL transaction. A cart failure rolls back the artifact write and
  leaves the previous cart unchanged.
- Frontend state changes only after a confirmed 2xx response. A persistence
  failure preserves the last confirmed state and shows that nothing was saved.

---

## Native Cart to Ordering Provider Flow

The frontend flow is provider-neutral. Its current live adapter is
`backend/app/providers/zepto.py`, and the existing Zepto-specific HTTP routes
remain unchanged.

```mermaid
sequenceDiagram
    autonumber
    participant UI as Groceries UI
    participant API as FastAPI
    participant DB as Supabase
    participant Adapter as ZeptoProviderAdapter
    participant MCP as Zepto MCP

    UI->>API: GET /api/grocery/zepto/addresses
    API->>Adapter: list_addresses()
    Adapter->>MCP: List saved addresses
    MCP-->>UI: Saved address options
    UI->>UI: User selects delivery address
    UI->>UI: Wait for native saves; lock edits; show transfer dialog
    UI->>API: POST /api/grocery/zepto/sync-cart + address id
    API->>DB: Read native cart rows
    API->>API: Exclude unselected and pantry-covered rows
    API->>API: Apply household brand memory to search terms
    API->>Adapter: sync_cart(mapped_items, address id)
    Adapter->>MCP: Select saved address / establish store
    Adapter->>MCP: Search products
    Adapter->>MCP: Replace Zepto cart
    Adapter->>MCP: View Zepto cart
    Adapter-->>API: Cart result + unavailable rows + normalized totals
    API->>DB: Save durable draft + totals + token
    API-->>UI: Confirmed checkout draft
    UI->>UI: Close dialog; unlock edits; show review
    UI->>API: PATCH checkout draft selections/acknowledgement
    UI->>API: POST revalidate after five minutes or page focus
    API->>Adapter: Validate products; repair and reconcile if necessary
    UI->>API: POST place-order after final approval
    API->>Adapter: Mandatory final revalidation
    API->>Adapter: place_order(review)
```

Important rules:

- User selection on the native cart means "include this row when moving to Zepto."
- Pantry-covered rows are never included.
- The main page chronology is native cart, ordering app, delivery address,
  transfer, provider cart review, then payment and order.
- Numbered stage markers are light green while pending and dark green only
  when their underlying state is complete. Native-cart, selection, provider,
  or address changes invalidate the provider review and return transfer,
  review, and order markers to pending.
- Zepto is selected by default. Blinkit is disabled and cannot issue API calls.
- A saved delivery address is required before sync.
- Zepto sync cannot start while a native-cart write is still in flight.
- Once sync starts, the frontend disables native-cart selection, quantity,
  unit, add, delete, clear, address, and quick-action controls. A modal progress
  dialog retains focus until the request succeeds or fails.
- Product search cannot start until Zepto confirms store context for that address.
- Search results do not count as cart success. The adapter must confirm exact
  product/store identifiers and quantities in the returned Zepto cart.
- Missing or ambiguous availability is unverified and cannot unlock ordering.
- A review is locked to the address/store context used during product resolution.
- Changing the native cart, selection, provider, or address invalidates the
  current review and requires a new cart sync.
- Zepto sync can replace the current Zepto cart.
- The backend exposes normalized `cart_summary` values in minor currency units.
  A provider-returned final total is authoritative. If the provider omits a
  final total, Kitch may sum exact provider selling prices multiplied by exact
  cart quantities only when the response contains no fee, tax, discount, or
  other adjustment. Otherwise the total remains unavailable.
- The cart summary is included in the review snapshot hash.
- Drafts are stored in `provider_checkout_drafts` with backend-only RLS and
  survive frontend/backend restarts.
- Groceries-page entry and focus revalidate drafts older than five minutes.
- Replacements, price changes, pack changes, quantity changes, and cart drift
  reset payment and acknowledgement. Unresolved native items block the order.
- The cart-item review occupies the main workflow; subtotal, fees, discount,
  total, and total-source explanation are shown in the right summary sidebar.
- Provider-cart rows show the provider image, mapped native item, unit price,
  read-only quantity, pack size, and line subtotal. Rows are ordered by line
  subtotal descending. Kitch does not expose provider-cart quantity controls
  until direct cart editing is implemented.
- The transfer stage is a single compact action row; it does not introduce a
  second internal section for its one button.
- Actual address labels should be shown with address details when exposed by Zepto.
- The UI distinguishes "Zepto configured/connected" from "Zepto store ready."

Why:

- Users care about what went into the cart, not internal matching terminology.
- Provider auth and tool mechanics are implementation details.
- Real order placement needs a human review point.

---

## Memory and Session Design

Current local ADK services:

- `InMemorySessionService`
- `InMemoryMemoryService`

Current persistent app state:

- Supabase.

Current memory contents:

- Household food preferences.
- Household brand preferences.

Why in-memory services now:

- The product is still in local/deployment testing.
- In-memory sessions make restarts predictable during development.
- Supabase already persists the deterministic records that the UI needs.
- Vertex AI service setup can wait until the deployed runtime is validated.

Planned migration:

- `VertexAISessionService` for durable sessions.
- `VertexAIMemoryBank` for durable household preferences.

Why the migration is deferred:

- It avoids coupling early product experimentation to managed memory setup.
- It lets the current app stabilize before introducing cloud-state debugging.
- The code already uses ADK service abstractions, so the migration should not require changing the agent topology.

---

## Known Boundaries

- Local backend restarts clear ephemeral ADK sessions and preferences.
- Apply versioned Supabase migrations before starting FastAPI in every
  environment. The bootstrap schema must remain synchronized with them.
- Zepto MCP OAuth/auth is external to Kitch.
- Blinkit live integration is not implemented.
- Multi-household registration is not implemented.
- Provider order placement is live and must remain guarded.
- The current household is configured in code until real registration exists.
