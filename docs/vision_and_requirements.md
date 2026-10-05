# Kitch: Product Vision and Requirements

This document describes what Kitch is trying to become, what the product does today, and why several product and architecture choices were made. A new developer or coding agent should read this first to understand the direction of the app before changing implementation details.

---

## Product Vision

Kitch is an AI household kitchen companion for planning meals, preparing recipes, managing pantry-aware groceries, syncing a reviewed cart to delivery providers, and tracking individual nutrition.

The app is designed for a shared household where people eat from the same meal
plan and pantry but keep individual nutrition logs. Empty local installations
create the household from the names entered during first-run onboarding.

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

When the user explicitly asks to add, update, or remove a standalone grocery
item, Kitch may create or change a manual native-cart row without inventing a
recipe. An explicit Instamart request may then synchronize the resulting
complete eligible native cart through the existing guarded sync bridge.

**Why:** grocery lists that are inferred separately from recipes can drift from the actual cooking plan. Keeping recipe and grocery outputs connected prevents buying ingredients that the recipe does not use, or missing ingredients that the recipe needs.

### 4. Native grocery cart is the source of truth

Kitch owns a provider-agnostic native cart. Zepto, Swiggy Instamart, and future
providers are time-sensitive translations of that cart, not independent intent.
The native cart is a durable conduit, not a mandatory manual UI gate: recipe
planning, standalone chat edits, and direct UI edits may all contribute to it.

**Why:** delivery providers differ in catalog structure, package sizes, availability, auth, address selection, and payment flows. A native cart lets Kitch reason about household grocery needs before any provider-specific mapping happens.

### 5. Real orders require explicit UI approval

Chat text can plan groceries and prepare a provider cart. Chat text must not place a real order. Order placement is only allowed through the final frontend approval control after the user has reviewed the provider cart.

**Why:** grocery providers are real consumer-facing services. Catalog
substitutions, payment state, address state, timeouts, and duplicate orders are
high-risk. Human-in-the-loop final approval is a product safety requirement.

### 6. Household context stays flexible and persistent

Food, allergy, dietary style, planning style, brand, pack, exclusion, correction,
and forget statements are stored as household-level natural-language memory,
not strict preference tables. Deployed Kitch uses Vertex AI Memory Bank so this
selected context survives backend restarts while chat sessions remain temporary.

Examples:

- "We prefer not to use tofu."
- "Avoid mushrooms."
- "Prefer high-protein dinners."
- "Always buy Amul butter."

**Why:** household context is naturally conversational and often messy. A
rigid schema would force the agent into brittle syntax and premature product
assumptions. Structured storage is reserved for things that must be
deterministic, such as meal plans and grocery rows. Persistence changes where
the text lives; it does not turn it into database rules.

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

The Groceries page is the operational checkout-prep screen. It keeps the full
ordering path visible in this order:

- Review the compact native-cart summary and expand it for row-level changes.
- Select Zepto or Swiggy Instamart from backend-provided descriptors. Blinkit
  is shown as a disabled `Coming soon` option.
- Connect or reconnect the provider when required, then select its address.
- Transfer the selected native rows as a separate checkout stage.
- Review actual provider cart items, unavailable items, and provider-returned
  totals, with product images and read-only line subtotals sorted by value in
  the main column and the financial summary kept in the right sidebar.
- Choose payment state if exposed, acknowledge the exact review, and place an
  order only through the final approval action.

Later stages stay visible but locked until their prerequisites are complete.
Any native-cart, selection, provider, or address change invalidates the active
provider review and requires a fresh sync.

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
| REQ-001 | On an empty local database, create one member profile per entered name, use the first as household owner, derive household size from the count, and detect timezone from the browser. | Makes local Kitch usable without seeded identities or cloud setup. |
| REQ-002 | Use one shared household profile id for meal plans, pantry, recipe+grocery artifacts, and native cart until household entities exist. | The product needs shared household state before it needs full account management. |
| REQ-003 | Keep macro logs individual to the active user. | Nutrition tracking is personal even when the meal plan is shared. |
| REQ-004 | Defer multi-household registration and authentication-backed membership. | The core planning/cart loop is still being validated. Building registration first would slow the product without proving the main value. |

### Household memory requirements

| ID | Requirement | Why |
| :--- | :--- | :--- |
| REQ-005 | Store durable household kitchen context as natural-language Memory Bank facts scoped by app `kitch` and the stable household-owner profile UUID. | Preferences must stay expressive, shared within the household, and isolated from unrelated households. |
| REQ-006 | Let relevant specialists decide when context is durable and submit one self-contained statement; do not ingest every turn or complete chat session automatically. | Memory generation should remain a deliberate agent action rather than an invisible side effect of every conversation. |
| REQ-007 | Let Memory Bank consolidate corrections, contradictions, and forget requests through event-based generation without prefix schemas or custom topic taxonomies. | Cohesion belongs to semantic memory management, not brittle application parsing. |
| REQ-008 | Keep chat sessions temporary while household memory survives backend restarts. | Short Kitch conversations do not justify persistent session infrastructure, but preferences must remain useful later. |
| REQ-009 | If configured memory is unavailable, report that memory was not saved or recalled, keep structured-persistence features usable, and never fall back silently from Vertex. | Personalization failure must not become false success or disable the kitchen workflows. |

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
| REQ-024 | Native rows keep required amount separate from remaining positive purchase amount and structured pantry allocation. | Partial coverage and later pantry edits must not depend on stale booleans. |
| REQ-025 | Fridge-photo grocery requests update pantry first, then plan groceries against the updated pantry. | Prevents reordering things the user just showed Kitch they already have. |
| REQ-026 | A recipe artifact and its agent-generated cart replacement commit together or not at all. | Prevents a recipe history entry from claiming a cart change that did not persist. |
| REQ-027 | When durable storage is unavailable, preserve confirmed UI state and explain that nothing was saved. | Users must not be misled by optimistic changes or agent prose. |
| REQ-027A | Explicit standalone grocery chat requests can add, update, or remove `source=manual` native-cart rows without a recipe artifact. | Lets the native cart connect recipe planning with ordinary household shopping intent. |
| REQ-027B | Explicit provider chat requests and the Groceries UI use the same guarded confirmed-cart workflow. | Keeps chat flexible without duplicating provider logic or weakening checkout controls. |
| REQ-027C | Provider synchronization belongs to Recipe/Grocery Planner through one provider-neutral tool; the coordinator only routes. | Prevents coordinator tool proliferation while preserving direct conversational workflow. |

### Pantry and vision requirements

| ID | Requirement | Why |
| :--- | :--- | :--- |
| REQ-030 | Vision Scanner classifies every image as exactly meal, pantry, or ambiguous before mutation. | Upload source does not reveal semantic intent. |
| REQ-031 | Meal observations route to Nutrition Tracker; pantry observations route to Recipe/Grocery Planner. | Interpretation remains non-mutating while domain owners control state. |
| REQ-032 | Camera and Gallery accept accompanying text and use the identical classifier. | Acquisition method must not change behavior. |
| REQ-033 | Ambiguous images persist nothing and retain the browser file for an explicit meal/pantry override. | Uncertainty must not create accidental diary or pantry writes. |
| REQ-034 | Pantry supports revisioned add/set/adjust/remove and confirmed full replacement, including empty. | Users need transparent, safe inventory maintenance after time passes. |

### Provider and order requirements

| ID | Requirement | Why |
| :--- | :--- | :--- |
| REQ-040 | Keep provider execution behind the backend commerce service while exposing one provider-neutral sync capability to Recipe/Grocery Planner. | Grocery intent can reach a provider agent without exposing payment or checkout. |
| REQ-041 | Run Zepto and Swiggy Instamart through the same provider contract and provider-keyed API. | Supporting a provider must not introduce provider-specific frontend routes or checkout semantics. |
| REQ-042 | Before provider sync, show "not synced" rather than fake prices. After sync, prefer the provider's final total; an exact line-item sum is allowed only when no tax, fee, discount, or other adjustment is present. | A simple sum is useful when it is mathematically complete, but must never masquerade as a checkout total when provider adjustments exist. |
| REQ-043 | Synchronization replaces the complete selected-provider cart after explicit user action. | Replacement avoids ambiguous merges and keeps the native selection authoritative. |
| REQ-044 | Order placement requires a durable checkout draft, confirmation token, and unchanged final revalidation. | Ensures the order is based on exactly what the user reviewed and that it remains orderable. |
| REQ-045 | The app must surface unavailable or unresolved provider items. | Silent failures would lead to missing groceries. |
| REQ-046 | Blinkit provider sync is deferred. | No Blinkit MCP connection is currently configured. |
| REQ-047 | Keep checkout stages visible in chronological order while locking unavailable actions. | Users should understand the full path from native cart review to final approval without being able to bypass a prerequisite. |
| REQ-048 | Invalidate a provider review when its native-cart inputs or delivery context change. | A user must never place an order from a stale cart, address, or total snapshot. |
| REQ-049 | Keep provider cart items full-width in the main workflow and put the financial order summary in the information sidebar. | The summary must stay visible without consuming the horizontal space needed to review product mappings. |
| REQ-050 | Use minimal numbered vertical stage markers and make the native cart collapsible. Pending markers are light green; completed markers are dark green and must revert when their underlying state is invalidated. | The checkout sequence should remain obvious while accurately reflecting whether a transfer or review is still valid. |
| REQ-051 | Persist provider checkout drafts in the selected backend-only structured store and restore them across browser/backend restarts. | Provider cart approval must not depend on misleading process-local or browser-local state. |
| REQ-052 | Reconcile every initial provider update against the confirmed cart and treat ambiguous availability as unverified. | A search result is not proof that the requested product and quantity were added or remain orderable. |
| REQ-053 | Mark drafts stale after five minutes without automatic cart search, mutation, or revalidation on page entry, focus, or provider switching; allow read-only saved-address discovery, require explicit cart refresh before payment, and revalidate immediately before ordering. | Address selection should remain effortless while every operation that can inspect or change the provider cart stays intentional and visible. |
| REQ-054 | Permit a confirmed partial provider cart while prominently listing every unresolved native item as omitted from the order; block only when no selected item is confirmed or another checkout prerequisite fails. | Missing groceries must never be silently dropped, but one unavailable item should not prevent ordering the confirmed remainder. |
| REQ-055 | Discover and validate provider MCP capabilities, and degrade only that provider when required schemas are absent. | External schema drift must not corrupt calls or make core Kitch unavailable. |
| REQ-056 | Encrypt provider tokens and PKCE verifiers, reject OAuth replay/expiry, and never expose provider credentials or sensitive raw payloads. | Household commerce credentials require a backend-only security boundary. |
| REQ-057 | Offer only fresh provider-returned payment methods; prefer Instamart UPI and allow COD only when UPI is absent and COD is returned. | Kitch must never invent or submit a stale payment choice. |
| REQ-057A | Automatically select and display Instamart's sole provider-returned payment method as read-only; show a selector only when Instamart returns multiple supported methods. Keep Zepto payment selection independent. | A one-option dropdown adds no meaningful consent, while provider-specific behavior must not reduce Zepto's supported choices. |
| REQ-058 | Persist pending, partial, and ambiguous order outcomes and prevent blind checkout retry. | A timeout must not create duplicate-order risk. |
| REQ-059 | Provider switching preserves the native cart but isolates address, draft, payment, approval, and order state by provider/environment. | Provider-specific checkout state must never leak across integrations. |
| REQ-060 | Let the Instamart cart agent interpret brands, pack descriptions, and quantity coverage, using explicit persistent household memory before Swiggy history. | Real catalog variants such as one dozen, 12 pieces, and 2 × 6 cannot be handled reliably by rigid preprocessing. |
| REQ-061 | Permit explicit UI and chat Instamart synchronization, but authorize `checkout` only from the final UI place-order endpoint through server-owned middleware. | Cart preparation is reversible; order placement is consequential and must not be model-triggerable. |
| REQ-062 | Persist match reasoning but derive durable cart, prices, quantities, and totals only from captured `update_cart`/`get_cart` results. | Agent prose must never become evidence that a provider mutation or price succeeded. |

---

## Architecture Decisions That Affect Product Behavior

### Google ADK instead of Antigravity SDK

Kitch uses Google ADK 2.0 as the app runtime.

**Why:** ADK provides the production agent primitives this app needs:
`LlmAgent`, `Runner`, tools, callbacks, session services, memory services, and
multimodal message handling. Antigravity SDK was useful as an agent-development
environment, but Kitch needs a stable application runtime that can be
documented, deployed, and handed to future developers without relying on an
experimental development harness as the product substrate.

### Temporary sessions and persistent household memory

Kitch uses:

- `InMemorySessionService` for short conversational continuity.
- `VertexAiMemoryBankService` for deployed household memory.
- `InMemoryMemoryService` as the supported ephemeral local mode.

**Why:** conversations are short and may reset on restart, while durable
household context must remain available across conversations. Kitch sends only
specialist-selected user events to Memory Bank and does not deploy the agent to
Agent Engine Runtime or use Agent Platform Sessions.

Persistent memory authenticates through Application Default Credentials
locally or Vercel Workload Identity Federation when hosted. It does not reuse
the Gemini/AI Studio key. Explicit writes wait for generation and default
consolidation before reporting success.

### SQLite or Supabase for deterministic state

The selected backend stores structured app state: meal plans, recipe+grocery
artifacts, pantry stock, native cart rows, profiles, macro logs, and provider
workflow records. SQLite serves local single-process installs; Supabase serves
hosted deployments.

**Why:** these are deterministic product records that the UI must render reliably. They should not live only in LLM memory.

### Natural-language memory for household context

ADK memory tools store and retrieve flexible household kitchen statements.

**Why:** the agent benefits from semantic context without requiring users or
catalogues to conform to a strict preference schema.

---

## Non-Goals and Deferred Work

- Full user auth and household registration.
- Multiple households.
- Persistent conversation sessions.
- Blinkit live cart sync.
- Swiggy Food and Dineout surfaces.
- Production Instamart ordering before approval and a successful staging soak.
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
- The user can choose Zepto or Instamart, sync selected native rows,
  and see actual provider cart details and returned totals.
- The user cannot place a real order without explicit final approval.
