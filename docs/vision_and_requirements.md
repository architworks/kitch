# Kitch: Product Vision and Requirements

This document describes what Kitch is trying to become, what the product does today, and why several product and architecture choices were made. A new developer or coding agent should read this first to understand the direction of the app before changing implementation details.

---

## Product Vision

Kitch is an AI household kitchen companion for planning meals, preparing recipes, managing pantry-aware groceries, syncing a reviewed cart to delivery providers, and tracking individual nutrition.

The app is designed for a shared household where people eat from the same meal plan and pantry, but still keep individual nutrition logs. The current prototype household is prefilled as Archit, Anubhav, and Naman. Multi-household registration is intentionally deferred until the core household workflow is stable.

Kitch should reduce the day-to-day cognitive load of:

- Deciding what to cook.
- Remembering what is already in the kitchen.
- Turning meal plans into recipes and groceries.
- Avoiding accidental duplicate purchases.
- Preparing a delivery cart without letting an agent place real orders by itself.
- Tracking personal macro intake without turning it into a manual spreadsheet task.

---

## Product Principles

### 1. Shared household planning, individual nutrition

The household shares one weekly meal plan, one pantry, one recipe+grocery artifact history, and one native grocery cart.

Macro logging remains individual. If Archit logs a plate photo, it affects Archit's diary only. It should not change Anubhav or Naman's nutrition state.

**Why:** food planning and grocery purchasing are household operations, while nutrition tracking is personal. Treating pantry and meal plan as per-user state made the product incoherent because three people in one home would see different versions of the same dinner.

### 2. Meal planning stays lightweight

The weekly planner stores meal names for breakfast, lunch, and dinner. It does not pre-generate recipes, ingredients, or grocery rows for every meal.

**Why:** recipes and ingredients are best generated when the user needs them. Pre-generating full recipes for a week makes meal planning slower, increases token cost, creates stale ingredients, and overwhelms the planner with work that may never be used.

### 3. Recipe and grocery planning stay connected

When the user asks for groceries for a meal or dish, Kitch generates a recipe+ingredient artifact first, then derives native cart rows from that same artifact.

**Why:** grocery lists that are inferred separately from recipes can drift from the actual cooking plan. Keeping recipe and grocery outputs connected prevents buying ingredients that the recipe does not use, or missing ingredients that the recipe needs.

### 4. Native grocery cart is the source of truth

Kitch owns a provider-agnostic native cart. Zepto/Blinkit/etc. are provider translations of that native cart, not the source of truth.

**Why:** delivery providers differ in catalog structure, package sizes, availability, auth, address selection, and payment flows. A native cart lets Kitch reason about household grocery needs before any provider-specific mapping happens.

### 5. Real orders require explicit UI approval

Chat text can plan groceries and prepare a provider cart. Chat text must not place a real order. Order placement is only allowed through the final frontend approval control after the user has reviewed the provider cart.

**Why:** Zepto is a real consumer-facing service. Catalog substitutions, payment state, address state, and accidental orders are high-risk. Human-in-the-loop final approval is a product safety requirement, not a UI preference.

### 6. Preferences stay flexible in memory

Food preferences and brand preferences are stored as household-level plain-text memory, not strict preference tables.

Examples:

- "We prefer not to use tofu."
- "Avoid mushrooms."
- "Prefer high-protein dinners."
- "Always buy Amul butter."

**Why:** preferences are naturally conversational and often messy. A rigid schema would force the agent into brittle syntax and premature product assumptions. Structured storage is reserved for things that must be deterministic, such as meal plans and grocery rows.

---

## Current Product Surface

### Household page

The main household page gives a high-level view of:

- Current time-aware meal focus.
- Upcoming weekly plan.
- Shared household state.
- Nutrition summary for the active user.
- Floating chat input for agent interaction.

### Recipes page

The Recipes page shows the latest recipe+grocery artifact:

- Recipe card.
- Ingredients.
- Cooking steps.
- Nutrition/tips sections where available.
- A side panel for ingredients and recipe-derived grocery rows.

**Why this is separate from Groceries:** recipe exploration and grocery execution are different jobs. The Recipes page explains what to cook. The Groceries page manages what to buy.

### Groceries page

The Groceries page is the operational checkout-prep screen:

- Review native grocery cart rows.
- Add manual rows.
- Edit quantities and units.
- Select which eligible rows should move to Zepto.
- Sync selected rows to Zepto.
- Review actual Zepto cart items and unavailable items.
- Choose address/payment state if exposed.
- Confirm order only through a final approval action.

**Why this page exists:** native cart review, provider sync, and order approval need one clear operational flow. Hiding this inside the recipe page made it hard to understand what would actually be bought.

### Floating chat input

The floating chat input is the primary mode of interaction. It supports:

- Text prompts.
- Plate/photo attachments.
- Fridge scan attachments.
- Expanded chat history.
- Markdown-rendered agent replies.

**Why:** users should not have to learn a complex form system to ask for a meal plan, recipe, grocery list, pantry scan, or macro log.

---

## Functional Requirements

### Household and profile requirements

| ID | Requirement | Why |
| :--- | :--- | :--- |
| REQ-001 | Prefill prototype members as Archit, Anubhav, and Naman through configuration, not hardcoded UI logic. | Keeps the prototype useful while leaving room for real household registration later. |
| REQ-002 | Use one shared household profile id for meal plans, pantry, recipe+grocery artifacts, and native cart until household entities exist. | The product needs shared household state before it needs full account management. |
| REQ-003 | Keep macro logs individual to the active user. | Nutrition tracking is personal even when the meal plan is shared. |
| REQ-004 | Defer multi-household registration and authentication-backed membership. | The core planning/cart loop is still being validated. Building registration first would slow the product without proving the main value. |

### Meal planning requirements

| ID | Requirement | Why |
| :--- | :--- | :--- |
| REQ-010 | Generate a 7-day breakfast/lunch/dinner plan for the upcoming Monday-Sunday window when the user asks for "next week." | Users expect "next week" to be a future planning window, not today's weekday repeated into a generated plan. |
| REQ-011 | Store meal names directly in the weekly schedule. | Meal names are enough for planning, display, and later recipe lookup. |
| REQ-012 | Do not use a static recipe database or static recipe ids. | Kitch moved to agent-generated meal plans so it can adapt to preferences and household context. |
| REQ-013 | Do not plan snacks. | The product currently focuses on breakfast, lunch, and dinner only. |
| REQ-014 | Include exact dates in agent meal-plan responses and UI state. | Prevents misleading "today" highlighting when the visible plan is for a future week. |

### Recipe and grocery requirements

| ID | Requirement | Why |
| :--- | :--- | :--- |
| REQ-020 | Recipe-only requests save a recipe+ingredient artifact and do not update the native cart. | Asking how to cook something is not the same as asking to buy ingredients. |
| REQ-021 | Grocery requests generate recipe cards and ingredient rows for only the requested scope. | Avoids pushing the full weekly plan through recipe generation when the user asked about tonight or tomorrow only. |
| REQ-022 | Grocery requests update native cart rows derived from the same recipe artifact. | Keeps recipes and groceries consistent. |
| REQ-023 | New agent grocery plans replace prior agent-generated cart rows but preserve manual rows. | Lets the user add household staples manually without losing them every time the agent replans groceries. |
| REQ-024 | Pantry-covered rows remain visible but disabled/muted and excluded from provider sync. | Users should see why something was not ordered instead of wondering whether it was forgotten. |
| REQ-025 | Fridge-photo grocery requests update pantry first, then plan groceries against the updated pantry. | Prevents reordering things the user just showed Kitch they already have. |

### Pantry and vision requirements

| ID | Requirement | Why |
| :--- | :--- | :--- |
| REQ-030 | Plate photos log macros to the active user's diary. | Photo logging should reduce manual macro tracking friction. |
| REQ-031 | Fridge photos update shared pantry stock. | Pantry is a physical household resource. |
| REQ-032 | Photo uploads may include text. | Users often attach a photo and then explain context; submitting immediately on image attach removed that option. |

### Provider and order requirements

| ID | Requirement | Why |
| :--- | :--- | :--- |
| REQ-040 | Keep provider sync behind backend adapters. | Provider APIs/MCP tools are external systems and should not leak into recipe/grocery planning. |
| REQ-041 | Use Zepto MCP for live Zepto cart sync. | Zepto MCP exposes search/cart/order tools that are suitable for testing native-cart-to-provider-cart translation. |
| REQ-042 | Before provider sync, show "not synced" rather than fake prices. | Fake totals would create false confidence. Prices and fees come from the provider response. |
| REQ-043 | Moving items to Zepto may replace the existing Zepto cart after the user clicks the sync action. | The user explicitly asked to move selected Kitch rows to Zepto, and replacing avoids ambiguous merges. |
| REQ-044 | Order placement requires a saved review snapshot and confirmation token. | Ensures the order is based on exactly what the user reviewed. |
| REQ-045 | The app must surface unavailable or unresolved provider items. | Silent failures would lead to missing groceries. |
| REQ-046 | Blinkit provider sync is deferred. | No Blinkit MCP connection is currently configured. |

---

## Architecture Decisions That Affect Product Behavior

### Google ADK instead of Antigravity SDK

Kitch uses Google ADK 2.0 as the app runtime.

**Why:** ADK provides the production agent primitives this app needs: `LlmAgent`, `Runner`, tools, callbacks, session services, memory services, multimodal message handling, and a path toward Vertex AI managed memory/session services. Antigravity SDK was useful as an agent-development environment, but Kitch needs a stable application runtime that can be documented, deployed, and handed to future developers without relying on an experimental development harness as the product substrate.

### In-memory ADK services for now

Kitch currently uses:

- `InMemorySessionService`
- `InMemoryMemoryService`

**Why:** local development needs fast iteration, easy restarts, and low setup overhead while the product loop is still being tested. The data that must survive now is already stored in Supabase. Conversational memory and sessions can reset on backend restart during this phase.

**Deferred path:** after deployment and testing, replace them with:

- `VertexAISessionService`
- `VertexAIMemoryBank`

This will make sessions and long-term memory persistent without changing the agent topology.

### Supabase for deterministic state

Supabase stores structured app state: meal plans, recipe+grocery artifacts, pantry stock, native cart rows, profiles, and macro logs.

**Why:** these are deterministic product records that the UI must render reliably. They should not live only in LLM memory.

### Plain-text memory for preferences

ADK memory stores flexible household preference text.

**Why:** preferences are not yet stable enough for a strict schema, and the agent benefits from natural-language preference context.

---

## Non-Goals and Deferred Work

- Full user auth and household registration.
- Multiple households.
- Persistent Vertex AI sessions and memory.
- Blinkit live cart sync.
- Autonomous order placement from chat.
- Static recipe database.
- Snack planning.
- Full pantry quantity reconciliation across arbitrary units.
- Hard-coded user names outside configuration.

---

## Success Criteria

Kitch is working when:

- A user can ask for next week's meal plan and the UI shows the generated future-dated plan.
- All household members see the same plan, pantry, recipe+grocery artifacts, and grocery cart.
- Each user keeps their own macro diary.
- Recipe requests produce recipe artifacts without changing the cart.
- Grocery requests produce recipe artifacts and native cart rows together.
- Pantry-covered items are visible but excluded from provider sync.
- The user can sync selected native rows to Zepto and see actual Zepto cart details.
- The user cannot place a real order without explicit final approval.
