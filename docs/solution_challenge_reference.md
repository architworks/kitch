# Kitch Solution Building Challenge Reference

This is a prep document for submitting Kitch to the solution building challenge.

Challenge framing from the prompt:

1. **Pick a complex problem**: something that needs a system, not just a script.
2. **Build the solution**: code it, ship it, push to a public repo.
3. **Record a video**: walk through the thinking in 5-10 minutes max.

The video should cover:

- **Problem framing**: what problem did we choose, and why is it hard?
- **System design**: architecture, components, and data flows.
- **Tradeoffs**: key decisions, alternatives considered, and what would change our mind.
- **Failure modes**: what breaks, and how the system behaves when things go wrong.

---

## Submission Positioning

Kitch is not a single prompt or script. It is a household kitchen operating system with shared state, personal state, multimodal AI, structured persistence, provider cart translation, and explicit safety boundaries around real orders.

The complex problem is not "generate a meal plan." The complex problem is:

> How do you help a real household decide what to cook, remember what is already in the kitchen, convert meals into groceries, prepare a delivery cart, and track individual nutrition without losing trust when AI is wrong?

Current persistence guardrail: the browser has no direct Supabase access. The
backend uses an elevated credential behind RLS, treats only confirmed database
results as saved, and returns a clear failure instead of inventing local state.
ADK preference memory remains intentionally ephemeral until the Vertex AI
migration.

That requires a system because the app has to coordinate:

- Multiple household members.
- Shared meal plans.
- Shared pantry/fridge stock.
- Individual macro diaries.
- Recipe generation.
- Grocery derivation.
- Native cart state.
- Provider cart sync.
- Real-world ordering safety.
- Multimodal inputs from plate and fridge photos.

---

## 5-10 Minute Video Outline

The challenge asks for several sections that could easily exceed 10 minutes. For the actual submission video, compress the story and keep the tradeoffs/failure modes high-signal.

### 0:00-0:45 - Hook

Show the app briefly and state the problem:

> Kitch is an AI household kitchen companion. The challenge I picked is household food planning: deciding meals, tracking pantry stock, turning recipes into groceries, preparing a delivery cart, and keeping nutrition logs personal. This is hard because the kitchen is shared, nutrition is individual, and ordering groceries has real-world consequences.

### 0:45-2:15 - Problem Framing

Cover:

- Most AI meal planners stop at text generation.
- Real households need state: what is planned, what is stocked, what is in the cart, who ate what.
- Shared household workflows and personal nutrition workflows must not be mixed.
- Grocery delivery integration is risky because bad automation can place wrong or accidental orders.

Strong sentence:

> The core product problem is trust: users need to know what the AI understood, what it changed, what it saved, and what still needs human review.

### 2:15-5:45 - System Design

Walk through the architecture:

- Next.js frontend for dashboard, recipes, groceries, nutrition, and explicit user actions.
- FastAPI backend as gateway and safety boundary.
- Google ADK 2.0 multi-agent runtime.
- Supabase for structured persistent state.
- ADK memory for flexible preferences.
- Provider registry, checkout service, and Zepto/Instamart adapters for guarded commerce.

Agent roles:

- `kitch_coordinator`: routes natural language.
- `chef_planner`: creates and edits weekly meal plans.
- `vision_scanner`: handles plate macros and fridge/pantry scans.
- `recipe_grocery_planner`: creates recipe artifacts and native grocery rows.

Core data flows:

1. **Meal plan flow**
   User asks for next week -> coordinator routes to chef planner -> chef saves Monday-Sunday meal names in Supabase -> UI refreshes shared plan.

2. **Recipe/grocery flow**
   User asks for groceries -> recipe grocery planner reads schedule and pantry -> generates recipe artifact -> derives native cart rows -> UI shows reviewable cart.

3. **Fridge photo flow**
   User uploads fridge photo with grocery request -> vision scanner updates pantry first -> grocery planner runs against updated pantry -> pantry-covered rows are muted/excluded from provider sync.

4. **Provider flow**
   User selects native cart rows -> backend syncs and reconciles selected
   non-stocked rows through the selected adapter -> backend saves an isolated durable checkout draft -> stale
   products are revalidated/repaired -> user must explicitly approve an
   unchanged final cart before order placement.

Agent harness talking points:

- The harness is Google ADK 2.0 behind a FastAPI gateway.
- ADK provides the agent graph, runner, session service, memory service, tools, callbacks, and context compaction.
- FastAPI prepares each turn with active user, household, date/time, pantry, and planning context.
- The coordinator delegates to specialist agents instead of giving every tool to one agent.
- Durable product state is written through tools into Supabase, not trusted only from chat text.
- Risky provider actions are outside the agent tool list and stay behind backend approval routes.

Suggested 90-second harness structure:

1. **Execution environment:** Next.js UI -> FastAPI gateway -> ADK runner -> Supabase/tools/provider adapters.
2. **Context:** active user, household, diet profile, current date, and planning week injected before turns.
3. **Memory:** Supabase for durable records, ADK memory for fuzzy household preferences.
4. **Delegation:** coordinator routes to meal planning, vision, or recipe/grocery specialists.
5. **Tools/MCP:** internal Python tools mutate app state; Zepto and Instamart MCP are wrapped by a shared backend contract.
6. **Guardrails:** chat cannot place real orders; final ordering needs review snapshot and explicit UI approval.

### 5:45-8:00 - Tradeoffs

Pick 4-5 from the tradeoff sections below. For a technical prototyping submission, include at least two system-design tradeoffs, not only product tradeoffs.

Recommended mix:

- FastAPI gateway vs direct frontend-to-agent calls.
- Supabase structured state vs LLM/session memory.
- Multi-agent ADK topology vs one large agent.
- Native cart/provider adapter boundary vs provider cart as source of truth.
- In-memory ADK services now vs durable managed sessions later.

### 8:00-9:30 - Failure Modes

Pick the failure modes that prove clear thinking:

- AI routes the wrong intent.
- Vision/macro estimation is uncertain.
- Pantry quantity reconciliation is imperfect.
- Provider SKU matching can be wrong.
- External ordering must never be fully autonomous.

### 9:30-10:00 - Close

Close with:

> The important design choice is that Kitch is agentic where reasoning helps, but deterministic and reviewable where state and safety matter.

---

## Challenge Requirements Checklist

| Challenge Requirement | How Kitch Satisfies It |
| :--- | :--- |
| Pick a complex problem | Household food planning involves shared state, personal state, multimodal input, persistent records, and real provider side effects. |
| Needs a system, not just a script | Kitch has a frontend, backend gateway, multi-agent runtime, database, memory layer, provider adapter, and explicit approval flow. |
| Build the solution | The repo contains the Next.js frontend, FastAPI backend, ADK agents, Supabase schema, provider adapter, tests, and docs. |
| Ship/push public repo | Prepare repo with clean env handling, no committed secrets, README/demo instructions, and current docs. |
| Problem framing | Kitch frames the hard part as trustworthy household coordination, not just AI meal generation. |
| System design | Architecture is decomposed by responsibility: UI, gateway, agents, tools, database, memory, provider adapter. |
| Tradeoffs | Product and system-design decisions are documented below with alternatives and what would change our mind. |
| Failure modes | Known failures and system behavior are documented below. |

---

## Agent Harness Talking Points

Use this section in the system-design part of the video. It explains the agentic runtime as a harness, not just a set of prompts.

### Presenter Checklist

Use this table as the compact version during recording.

| Harness Area | What To Say | Why It Matters |
| :--- | :--- | :--- |
| Harness/runtime | "Kitch uses Google ADK behind FastAPI. FastAPI receives browser requests, prepares context, and runs the ADK runner." | Shows this is a controlled runtime, not a loose prompt pasted into a UI. |
| Execution environment | "The app is split into Next.js frontend, FastAPI backend, ADK agents, Supabase persistence, and a multi-provider commerce layer." | Explains why the system has multiple components and where each responsibility lives. |
| Context/session management | "ADK Runner uses session state via `InMemorySessionService`; FastAPI and callbacks inject active user, household, date, planning week, and compaction keeps long sessions bounded." | Prevents wrong-person/wrong-date behavior while keeping long conversations manageable. |
| Memory management | "Supabase stores durable product state; ADK memory stores flexible household preferences." | Separates reliable UI records from fuzzy conversational memory. |
| Delegation/routing | "A coordinator routes to specialist agents for meal planning, vision/macros/pantry, and recipe/grocery planning." | Keeps prompts and tool access scoped instead of giving every tool to one giant agent. |
| Tools | "Agents call Python tools for deterministic reads/writes like saving meal plans, logging macros, and updating native cart rows." | Converts AI reasoning into auditable state changes. |
| MCP/provider integration | "Zepto and Instamart implement one backend adapter contract and are not exposed directly to the grocery agent." | Keeps provider-specific auth/catalog/order behavior outside core planning. |
| Guardrails | "Provider ordering is not an agent tool. The user must review a saved snapshot and explicitly approve." | Addresses real-world side effects: money, address, substitutions, delivery. |
| Failure posture | "When AI is uncertain or provider matching fails, Kitch shows reviewable state instead of silently acting." | Centers trust and debuggability. |

### 60-90 Second Agent Harness Script

> The agent harness is Google ADK running behind a FastAPI gateway. The frontend does not call a model directly. FastAPI receives chat or image requests, prepares active user and household context, injects current date and planning-week context into ADK session state, and then runs the ADK runner. For the prototype, ADK uses `InMemorySessionService`, and the ADK app uses event compaction so long conversations stay bounded.

> The agent graph is a hub-and-spoke topology. The coordinator routes intent to specialists: `chef_planner` for schedules, `vision_scanner` for plate photos, pantry scans, and macro logs, and `recipe_grocery_planner` for recipes, ingredients, groceries, and preferences. That lets each agent have a focused prompt and a scoped tool list.

> Memory is split deliberately. Supabase is the source of truth for meal plans, pantry, recipe artifacts, native cart rows, macro logs, provider connections, and checkout drafts. ADK memory is for flexible preferences like "avoid tofu" or "prefer Amul butter." Tools are the execution layer: agents call Python tools for deterministic state changes. Zepto and Swiggy Instamart are integrated through one backend commerce contract, and the key guardrail is that real order placement is never an agent tool. Kitch can prepare the cart, but final ordering requires a saved review snapshot and explicit UI approval.

### 1. Harness Overview

Talking point:

> The agent harness is the layer that turns a chat prompt into controlled system behavior. In Kitch, the harness is Google ADK 2.0 running behind FastAPI. ADK gives us the runner, agent graph, tools, session service, memory service, callbacks, and context compaction. FastAPI wraps that with browser-facing APIs, multimodal upload handling, state hydration, and safety boundaries.

Concrete components:

- `FastAPI` receives browser requests.
- `ADK Runner` executes turns.
- `kitch_coordinator` is the parent routing agent.
- Specialist agents handle meal planning, vision/pantry/macros, and recipe/grocery planning.
- Python tools perform deterministic side effects.
- Supabase persists structured product state.
- ADK memory stores flexible household preferences.

Why it matters:

- The app is not letting one model freely mutate everything.
- The harness scopes context, tools, memory, and side effects.
- The system can explain which parts are AI reasoning and which parts are deterministic backend behavior.

---

### 2. Context and Session Management

Talking point:

> Context is not just chat history. In Kitch, context and session management are handled by ADK plus FastAPI. FastAPI syncs operational context into ADK session state before each turn, and ADK's `Runner` executes the turn against that session. The prototype currently uses `InMemorySessionService`, with a planned path to `VertexAISessionService` for durable deployed sessions.

ADK/session machinery:

- ADK `Runner` executes turns against an application/session identity.
- `InMemorySessionService` stores local prototype session state.
- FastAPI updates ADK session state before agent runs.
- Backend callbacks inject current date/time and planning-week context.
- ADK `EventsCompactionConfig` and `LlmEventSummarizer` compact long event histories.

What gets injected:

- Active profile name.
- Dietary profile.
- Household size.
- Household members.
- Current date and day of week.
- Upcoming Monday-Sunday planning window.
- Planning week date list.

How compaction fits into context management:

- Long household conversations can grow quickly.
- ADK event compaction summarizes older context while keeping recent overlap.
- Durable product truth still lives in Supabase, so compacted chat history is not the source of truth for meal plans, pantry, cart rows, or macro logs.

Why it matters:

- Prevents date mistakes like treating a future Saturday as today.
- Keeps macro logs attached to the active user.
- Gives the planner enough context to generate household-scale plans.
- Keeps long sessions bounded without depending entirely on a growing prompt.

Failure mode to mention:

- If session state or context injection is wrong, the model may answer confidently for the wrong date, wrong user, or stale household state.
- If compaction drops important conversational context, the agent may forget a recent soft instruction; durable product state remains recoverable from Supabase.

Mitigation:

- Date/time and planning context are injected via backend callbacks.
- Operational context is synced into ADK session state before turns.
- Event compaction keeps long sessions bounded.
- UI state refreshes from Supabase after agent writes.

---

### 3. Memory Management

Talking point:

> Kitch splits memory into two categories. Structured product state goes into Supabase. Flexible preferences go into ADK memory. That means meal plans, pantry rows, grocery rows, recipe artifacts, and macro logs are durable records, while fuzzy preferences like "avoid tofu" or "prefer Amul butter" can stay conversational.

Structured state in Supabase:

- Profiles.
- Meal plans.
- Recipe/grocery artifacts.
- Pantry stock.
- Native grocery cart rows.
- Macro diary logs.

Flexible memory in ADK:

- Food preferences.
- Brand preferences.
- Planning style preferences.
- Household-level natural-language notes.

Tradeoff:

- In-memory ADK services are fast for prototyping but reset on backend restart.
- Supabase persists critical product records, so the app does not lose the actual plan/cart/pantry.

Future improvement:

- Replace local `InMemorySessionService` and `InMemoryMemoryService` with Vertex AI managed session and memory services for real deployed usage.

---

### 4. Delegation and Routing

Talking point:

> Kitch uses a hub-and-spoke agent topology. The coordinator does not perform side effects directly. It reads the user's intent and delegates to the right specialist. This keeps each agent's prompt and tool access scoped.

Routing model:

- Meal plans and meal swaps -> `chef_planner`.
- Plate photos, macro logs, pantry scans -> `vision_scanner`.
- Recipes, ingredients, groceries, and preferences -> `recipe_grocery_planner`.

Why not one giant agent:

- One large agent would be simpler to wire but harder to control.
- Tool misuse risk is higher when every tool is available to every task.
- Specialist agents make failure analysis easier.

Failure mode:

- The coordinator can route ambiguous requests incorrectly.

Mitigation:

- Agent descriptions are written for natural user language.
- Test scenarios validate casual prompts like "I ate dal and rice" or "what groceries do we need?"
- Cross-flow orchestration is handled by FastAPI when needed, such as fridge photo first, grocery planning second.

---

### 5. Tool and MCP Integration

Talking point:

> Tools are where model reasoning becomes system action. Kitch agents do not directly edit frontend state. They call Python tools that read and write Supabase or ADK memory. Provider integration is separate: Zepto and Instamart MCP are wrapped by deterministic backend adapters instead of being exposed directly to the recipe planner.

Internal Python tools:

- Read/save weekly schedule.
- Update one meal slot.
- Add pantry stock.
- Log macros.
- Read pantry and macro diary.
- Save recipe/grocery artifacts.
- Clear and save planned native cart rows.
- Save/search household preferences.

External/provider integration:

- Zepto and Instamart are accessed through adapters implementing `GroceryProviderAdapter`.
- Instamart is limited to Swiggy's `/im` MCP tools; Food and Dineout are inaccessible.
- A constrained Gemini matcher can rank normalized candidates but cannot call MCP or mutate external state.
- Native cart rows are mapped into provider search/cart operations.
- Provider results return actual cart items and unavailable items.

Why this matters:

- Internal app state changes are deterministic and testable.
- Provider-specific MCP details do not leak into meal planning.
- Future providers can be added behind the same adapter boundary.

Failure mode:

- Provider product matching can choose the wrong SKU or fail due to auth/catalog issues.

Mitigation:

- Show unresolved/unavailable items.
- Keep native cart usable even if any provider sync fails.
- Require user review before order placement.

---

### 6. Guardrails and Approval Boundaries

Talking point:

> The main guardrail is that the agent is not allowed to place real orders from chat. It can plan, generate recipes, update the native cart, and prepare a provider cart. But final ordering is behind deterministic backend routes, a saved review snapshot, a confirmation token, and explicit UI approval.

Guardrails:

- Coordinator has no side-effect tools.
- Specialist agents have scoped tools.
- Recipe-only requests do not update cart rows.
- Provider operations are outside the recipe/grocery agent.
- Pantry-covered rows are excluded from provider sync.
- Final order placement requires frontend approval.

Why it matters:

- Grocery delivery affects money, address, substitutions, and real external state.
- The system should be agentic, but not reckless.

Strong sentence:

> Kitch is agentic where reasoning helps, but deterministic and human-approved where mistakes have real-world consequences.

---

### 7. Execution Environment

Talking point:

> The prototype runs as a split runtime: Next.js for the product UI, FastAPI for backend orchestration, Google ADK for the agent runtime, Supabase for persistence, and MCP/provider adapters for external grocery systems.

Runtime pieces:

- Frontend: Next.js.
- Backend: FastAPI Python service.
- Agent runtime: Google ADK 2.0.
- Persistence: Supabase Postgres.
- Model runtime: native ADK Gemini, with AI Studio authentication locally and Vertex AI authentication in cloud deployments.
- Provider platform: registry, checkout service, OAuth vault, Zepto adapter, and Instamart `/im` adapter.

Why this matters:

- The frontend stays focused on rendering state and collecting explicit actions.
- The backend owns secrets, state hydration, tools, and side-effect boundaries.
- The agent runtime can evolve without rewriting the UI.

Tradeoff:

- More moving parts than a single-app prototype.
- Better separation for a system that has multimodal inputs, persistent state, and external provider side effects.

---

### 8. Agent Harness Script for Video

Use this as a concise system-design narration:

> The agent harness is Google ADK behind a FastAPI gateway. FastAPI receives chat or image requests, syncs operational context into ADK session state, injects current date and planning-week context through callbacks, and then runs the ADK runner. The prototype uses `InMemorySessionService`, and ADK event compaction keeps long conversations bounded without making chat history the source of truth. The parent coordinator routes to specialist agents: one for meal planning, one for vision and nutrition, and one for recipes and groceries.

> Memory is split deliberately. Supabase is the source of truth for structured records like meal plans, pantry, recipe artifacts, cart rows, and macro logs. ADK memory is used for flexible household preferences like "avoid tofu" or "prefer Amul butter." That keeps the UI reliable while still letting preferences stay conversational.

> Tools are the execution layer. Agents call Python tools for deterministic writes, and provider MCP tools are wrapped behind backend adapters. A constrained matcher may select only allowlisted candidates, while cart mutation and ordering remain deterministic. The agent can prepare a native cart, but final order placement requires a saved review snapshot and explicit UI approval.

---

## Tradeoffs

Use this section to show that the prototype is engineered as a system. Some tradeoffs are product decisions, but several are technical architecture choices about where state lives, where side effects happen, and how much agent autonomy is allowed.

---

## Product and Domain Tradeoffs

### 1. Shared Household Planning vs Individual Nutrition

**Decision:** Meal plans, pantry, recipe artifacts, grocery cart, and food preferences are shared household state. Macro logs are individual to the active user.

**Alternative considered:** Treat everything as per-user state.

**Why we chose this:**

- A fridge and grocery cart are physical household resources.
- Everyone in the home should see the same dinner plan.
- Nutrition is personal and should not leak across members.

**Cost of the decision:**

- The UI has to make shared vs personal state obvious.
- Active user context matters before logging food.

**What would change our mind:**

- If the product moved from household planning to single-user fitness coaching, per-user state would become more central.
- If households had multiple sub-groups with separate diets, we would need richer household membership and meal-participant modeling.

---

### 2. Lightweight Weekly Plan vs Pre-generating Every Recipe

**Decision:** The weekly planner stores meal names only. Recipes and ingredients are generated later when requested.

**Alternative considered:** Generate full recipes, nutrition, and ingredients for all 21 weekly meals upfront.

**Why we chose this:**

- Weekly planning stays fast.
- Token cost stays lower.
- Users are not flooded with recipes they may never cook.
- Ingredients do not become stale before the user is ready to shop.

**Cost of the decision:**

- Grocery generation requires another step.
- Meal names can be underspecified until recipe artifacts are generated.

**What would change our mind:**

- If users strongly wanted batch meal prep with locked recipes for the whole week, pre-generation might become worthwhile.
- If model cost/latency became negligible, eager generation could be reconsidered for richer previews.

---

### 3. One Recipe+Grocery Agent vs Separate Recipe and Grocery Agents

**Decision:** One specialist agent generates recipe artifacts and derives grocery rows from the same artifact.

**Alternative considered:** Separate recipe generation from grocery list generation.

**Why we chose this:**

- Grocery rows must match the recipe the user will actually cook.
- Splitting the logic creates drift: buy ingredients the recipe does not use, or miss ingredients the recipe needs.
- A saved recipe+grocery artifact gives the UI something auditable.

**Cost of the decision:**

- The agent has a broader responsibility.
- The tool instructions must clearly distinguish recipe-only requests from grocery/cart requests.

**What would change our mind:**

- If recipe generation and grocery optimization became independently complex, we might split them but keep a strict artifact contract between them.

---

### 4. Native Cart as Source of Truth vs Provider Carts as Source of Truth

**Decision:** Kitch owns a provider-agnostic native cart. Zepto and Instamart are time-sensitive provider projections.

**Alternative considered:** Let an external provider cart become the main cart state.

**Why we chose this:**

- Provider catalogs differ in SKUs, pack sizes, availability, auth, and payment flows.
- Kitch needs to reason about household grocery intent before matching products.
- The same native cart can later support other providers.

**Cost of the decision:**

- Native items still need provider matching.
- Provider substitutions can diverge from user intent.
- Prices and fees are unknown until provider sync.

**What would change our mind:**

- If the app became a single-provider client, that provider cart could become more central.
- If provider APIs exposed stable normalized grocery semantics, the adapter layer could become thinner.

---

### 5. Human Approval vs Autonomous Ordering

**Decision:** Chat can prepare groceries and provider carts, but cannot place real orders. Final order placement requires explicit UI approval.

**Alternative considered:** Let the agent place orders directly when the user says "order this."

**Why we chose this:**

- Grocery orders involve money, address, substitutions, delivery timing, and real external state.
- AI can make catalog or quantity mistakes.
- Human review is a safety requirement, not just a UI preference.

**Cost of the decision:**

- Less "magical" than full autonomy.
- Adds one extra checkout step.

**What would change our mind:**

- For very low-risk reorders with fixed saved baskets, spending limits, and strong confirmation policies, partial autonomy could be added later.
- Even then, the default should remain review-first.

---

### 6. Flexible Text Preferences vs Structured Preference Schema

**Decision:** Food and brand preferences live as flexible household memory text.

**Alternative considered:** Build strict preference tables for cuisines, exclusions, brands, macros, and provider mappings.

**Why we chose this:**

- Preference language is messy: "avoid mushrooms," "prefer high protein," "always get Amul butter."
- A rigid schema too early would force artificial product decisions.
- Agents can use natural-language memory effectively during planning.

**Cost of the decision:**

- Preference behavior is less deterministic.
- In-memory preferences reset on backend restart until durable memory is adopted.

**What would change our mind:**

- If preferences become central to provider matching or compliance, we should promote stable preference types into Supabase tables.

---

### 7. In-memory ADK Sessions Now vs Vertex AI Managed Memory Later

**Decision:** Current local runtime uses ADK in-memory session and memory services; deterministic state lives in Supabase.

**Alternative considered:** Set up persistent managed sessions/memory immediately.

**Why we chose this:**

- Faster local iteration.
- The core product loop is still changing.
- Supabase already persists the records the UI depends on.

**Cost of the decision:**

- Chat/session memory and flexible preferences can reset on backend restart.
- This is not final production behavior.

**What would change our mind:**

- Before real household beta usage, durable sessions and memory should move to Vertex AI managed services.

---

## System Design Tradeoffs

### 1. FastAPI Gateway vs Direct Frontend-to-Agent Calls

**Decision:** The browser talks to FastAPI, and FastAPI runs the ADK runner.

**Alternative considered:** Let the Next.js frontend call the agent runtime or model APIs directly.

**Why we chose this:**

- The backend can normalize chat, image uploads, active user context, and household state before agent execution.
- FastAPI gives one stable API contract to the UI while ADK internals can change behind it.
- Provider sync and order placement need a backend-controlled safety boundary.
- API keys, MCP auth, Supabase keys, and provider tokens stay off the client.

**Cost of the decision:**

- Adds another service to run and deploy.
- Requires CORS/API wiring between frontend and backend.
- Local development needs both Next.js and FastAPI running.

**What would change our mind:**

- If this were only a static demo with no persistence, no images, and no provider side effects, a frontend-only prototype would be simpler.
- If Next.js server routes became the only backend deployment target, some gateway responsibilities could move there, but the server-side boundary would still be needed.

---

### 2. Supabase Structured State vs LLM Memory as Source of Truth

**Decision:** Meal plans, recipes, pantry, native cart rows, profiles, and macro logs live in Supabase. ADK memory is only for flexible preferences/session context.

**Alternative considered:** Store most state in chat history or agent memory.

**Why we chose this:**

- The UI needs reliable records it can render after refresh.
- Tool side effects must be auditable.
- Shared household state should survive backend restarts.
- Deterministic app data should be queryable and editable outside the model.

**Cost of the decision:**

- Requires schema design and migrations.
- Agents need tools to read/write state instead of relying on conversation context.
- Schema drift can break flows if environments are not migrated correctly.

**What would change our mind:**

- For a pure chatbot demo, memory-only state would be acceptable.
- For production, this decision becomes even stronger; more state should become structured, not less.

---

### 3. Multi-Agent ADK Topology vs One Large Agent

**Decision:** Kitch uses a coordinator plus specialist agents: meal planning, vision/pantry/macros, and recipe/grocery planning.

**Alternative considered:** One large agent with every instruction and every tool.

**Why we chose this:**

- Tool access is scoped to the agent that needs it.
- Side effects are easier to reason about.
- Prompts stay more focused.
- The architecture maps to clear product domains.

**Cost of the decision:**

- Routing can fail if the coordinator chooses the wrong specialist.
- More agent definitions and instructions must be maintained.
- Cross-flow tasks, such as fridge photo plus grocery planning, need orchestration.

**What would change our mind:**

- If the product had only one or two simple tasks, one agent would be easier.
- If routing errors become more common than specialist complexity, we might collapse some agents or add deterministic intent classification before ADK.

---

### 4. Agent Tools for Deterministic Side Effects vs Free-form Agent Responses

**Decision:** Agents perform durable changes through Python tools that write to Supabase or ADK memory.

**Alternative considered:** Let the model describe intended changes in text and let the frontend infer updates.

**Why we chose this:**

- Tool calls make writes explicit.
- Backend code controls validation and persistence.
- The UI can refresh real state after a turn instead of trusting the assistant's prose.

**Cost of the decision:**

- Tool schemas and instructions need to be maintained.
- The agent can still misuse a tool if intent is misunderstood.
- More backend code is required than a chat-only prototype.

**What would change our mind:**

- For throwaway UX exploration, text-only responses are faster.
- For any saved household state, tool-based writes are the safer default.

---

### 5. Backend Provider Adapter vs Agent-owned Provider Tools

**Decision:** Provider sync and order placement live behind provider-keyed FastAPI routes, `GroceryCheckoutService`, and contract-based adapters, not inside the recipe/grocery agent.

**Alternative considered:** Give the grocery agent direct access to provider MCP tools.

**Why we chose this:**

- Provider actions affect real external state.
- Backend code can create review snapshots and confirmation tokens.
- Adapters isolate provider catalog, OAuth, tool-schema, payment, and order details.
- Zepto and Instamart share the same native-cart and draft boundary.

**Cost of the decision:**

- Provider sync is less conversationally seamless.
- There is more adapter code.
- Mapping native grocery intent to provider SKUs is a separate step with its own failure modes.

**What would change our mind:**

- If provider operations were read-only, agent-owned tools would be lower risk.
- The current constrained catalog matcher already demonstrates the safe limit:
  it can rank allowlisted candidates but cannot mutate carts or order.

---

### 6. Native Cart Review Snapshot vs Live Re-query at Order Time

**Decision:** Every provider order uses an environment-scoped saved review snapshot, confirmation token, and mandatory final revalidation.

**Alternative considered:** Re-run product matching and cart inspection when the user clicks place order.

**Why we chose this:**

- The user approves the exact cart state they reviewed.
- The app avoids silently changing products between review and order.
- Snapshot hashing/token validation protects against stale or modified approvals.

**Cost of the decision:**

- Review snapshots must be stored and invalidated.
- If provider inventory changes after review, the order may still fail and need a new review.

**What would change our mind:**

- If provider APIs guaranteed immutable cart sessions, snapshot logic could be simpler.
- For early demos without real order placement, a preview-only flow may be enough.

---

### 7. Local In-memory ADK Services vs Production Managed Services

**Decision:** The prototype uses `InMemorySessionService` and `InMemoryMemoryService` locally, while important product records persist in Supabase.

**Alternative considered:** Start immediately with Vertex AI sessions and memory.

**Why we chose this:**

- Faster iteration during prototype development.
- Fewer cloud moving parts while product behavior is still changing.
- Supabase already covers the app state the UI must render reliably.

**Cost of the decision:**

- Chat memory and flexible preferences reset on backend restart.
- Local behavior does not fully represent a production memory setup.

**What would change our mind:**

- Before real beta users, durable session/memory should be adopted.
- If preference persistence becomes central to the demo, this should move earlier.

---

### 8. Runtime Split Across Next.js and Python vs Single Full-stack Runtime

**Decision:** The frontend is Next.js, while backend/agents are Python FastAPI + ADK.

**Alternative considered:** Put everything in one JavaScript/Next.js app or one Python app.

**Why we chose this:**

- Next.js is a strong fit for the product UI.
- Google ADK, MCP clients, multimodal assembly, and Python tools fit naturally in the backend.
- The separation keeps agent runtime details out of the UI.

**Cost of the decision:**

- Two dev servers.
- More deployment coordination.
- More environment variables and service boundaries.

**What would change our mind:**

- If ADK/runtime needs were removed, a single Next.js app would simplify deployment.
- If UI needs became minimal, a Python-rendered app could reduce moving parts.

---

## Failure Modes

The main principle: when something goes wrong, Kitch should preserve user trust by showing what happened, avoiding silent side effects, and keeping risky actions behind review.

| Failure Mode | What Breaks | System Behavior / Mitigation |
| :--- | :--- | :--- |
| Wrong intent routing | User asks for a plan, log, pantry scan, or grocery list and the coordinator picks the wrong specialist. | Specialist tools are separated by responsibility; test scenarios use casual prompts to validate routing. Risk remains for ambiguous prompts. |
| Wrong date resolution | "Next week" or "tomorrow" points to the wrong date. | Backend injects current date and upcoming planning week dates. Agent responses and UI should show exact dates. |
| Meal edit rewrites too much | User asks to change one dated dinner but the surrounding plan changes. | `update_dated_meals_tool` applies exact ISO-date/slot edits transactionally and preserves unrelated dates and slots. |
| Recipe-only request mutates cart | User asks "how do I cook paneer butter masala?" and cart rows appear unexpectedly. | Recipe-only flow saves an artifact but does not update native cart. Cart updates are limited to grocery/cart/buy/order intent. |
| Grocery list drifts from recipe | User buys ingredients that do not match the recipe. | Recipe and grocery rows come from the same saved artifact. |
| Pantry scan misses items | App recommends buying something already in the fridge. | Fridge photo flow updates pantry first, then grocery planning runs against updated pantry. Pantry-covered rows remain visible instead of silently disappearing. |
| Pantry quantity math is imperfect | App underbuys or overbuys when units are ambiguous. | Full arbitrary unit reconciliation is deferred. The app shows pantry-covered rows and keeps review/edit controls in the native cart. |
| Macro estimate is wrong | User's calorie or macro diary is inaccurate. | Macros are estimates. Logs are scoped to active user and should support correction workflows. |
| Food logs to wrong user | Archit's meal appears in Anubhav's diary. | Active member is explicit in UI. Macro logs are individual, not household-wide. |
| Provider SKU match is wrong | External cart contains the wrong brand, pack size, or substitute. | Matcher output is allowlisted and deterministically validated; unresolved items remain visible and the user reviews the confirmed cart. |
| Provider price/fees surprise user | Kitch shows an expected amount that differs from provider checkout. | Kitch does not show fake prices before provider sync. Prices/fees come from provider response. |
| Provider cart replacement surprises user | Existing external cart is overwritten by Kitch sync. | Sync is explicit and communicates that the selected provider cart is replaced by the reviewed native intent. |
| Provider OAuth expires or MCP degrades | One provider cannot sync. | Native cart and core readiness remain available; the UI shows reconnect/degraded state for only that provider. |
| Checkout response is ambiguous | Retrying could create a duplicate order. | Persist the attempt, inspect documented order history, and block resubmission while outcome is `unknown`. |
| Real order placed accidentally | Highest-risk failure: wrong groceries or payment side effect. | Chat cannot place real orders. Order placement requires saved review snapshot, confirmation token, and explicit frontend approval. |
| Backend restart loses chat memory | Preferences or session context disappear during prototype use. | Supabase persists critical records. Durable Vertex sessions/memory are planned for production. |
| Supabase schema drift | Backend tools fail or fall back because expected tables/columns are missing. | Schema lives in `backend/database/supabase_schema.sql`. Production test docs record schema-dependent failures. |
| Model hallucination in response | Agent claims it saved or changed something it did not actually save. | UI should render backend state as source of truth after tool calls. Tool responses and state refreshes are more trustworthy than chat text alone. |

---

## System Behavior When Things Go Wrong

Use this section directly in the failure-modes part of the video.

- **If AI reasoning is wrong**, the app should still rely on Supabase-backed state for what is actually saved.
- **If vision is uncertain**, pantry and macro outputs should be treated as estimates and remain correctable.
- **If pantry coverage is uncertain**, rows should stay visible and marked as stocked/disabled rather than disappearing.
- **If provider matching fails**, unresolved items should be shown rather than silently omitted.
- **If provider auth fails**, the native cart still exists and can be reviewed manually.
- **If order placement is risky**, the system stops at review and requires explicit approval.
- **If backend memory resets**, deterministic product state remains in Supabase.

---

## Demo Flow for Video

Use a short demo that proves system behavior rather than just showing screens.

1. **Create or show a weekly plan**
   - Prompt: "Plan next week for the whole household."
   - Show Monday-Sunday dates and shared household plan.

2. **Ask for a recipe or grocery list**
   - Prompt: "What groceries do we need for tomorrow?"
   - Show recipe/grocery artifact and native cart rows.

3. **Show pantry awareness**
   - Add pantry items or mention "we already have eggs and paneer."
   - Show pantry-covered rows being muted/excluded.

4. **Show individual nutrition**
   - Switch active user or explain active user.
   - Log a food item and show it affects only that user's diary.

5. **Show provider boundary**
   - Show backend-described Zepto and Instamart choices and selected native rows.
   - Explain address-scoped cart reconciliation and provider switching isolation.
   - Emphasize that real order placement requires final approval.

---

## Short Script: Tradeoffs Section

> The biggest technical tradeoff was deciding where AI should be allowed to act versus where deterministic backend code should own the flow. Meal planning and recipe generation benefit from fuzzy reasoning, so those live in ADK agents. But provider sync and real order placement affect external state, so those go through FastAPI endpoints, provider adapters, review snapshots, and explicit UI approval.

> A second system tradeoff was using Supabase as the source of truth for structured app state instead of relying on chat history or LLM memory. That adds schema and migration work, but it means the UI can render reliable meal plans, pantry rows, carts, and macro logs after refreshes and backend restarts.

> A third tradeoff was the multi-agent topology. One large agent would be simpler to wire, but separating coordinator, meal planner, vision scanner, and recipe grocery planner keeps prompts and tool access scoped. The cost is routing complexity, so the test suite checks casual prompts across the major flows.

> On the product side, I also chose not to pre-generate every recipe for the week. It would look impressive, but it slows planning, costs more tokens, and creates stale ingredients. Instead, the weekly plan stores meal names and generates recipes/groceries only when needed.

---

## Short Script: Failure Modes Section

> The failure modes I care most about are the ones that break trust. The agent can route intent incorrectly, vision can misread a fridge or plate, pantry quantities can be ambiguous, and provider matching can choose the wrong SKU.

> The system handles this by keeping structured state in Supabase, showing pantry-covered and unresolved items instead of hiding them, and making the provider cart reviewable. The highest-risk failure is accidental ordering, so chat is not allowed to place real orders. Kitch can prepare the cart, but the user must explicitly approve the final order.

---

## What To Emphasize

- This is a system, not a script.
- The product combines AI reasoning with structured state.
- The hardest design problem is trust under uncertainty.
- The architecture separates agent reasoning from deterministic side effects.
- The best safety decision is human-in-the-loop approval for real orders.

---

## Supporting Docs

- Product vision: `docs/vision_and_requirements.md`
- System design: `docs/current_architecture.md`
- Agent architecture: `docs/current_ai_agent_architecture.md`
- Tech stack: `docs/current_technology_stack.md`
- Agent test scenarios: `docs/test_scenarios.md`
- Production verification snapshot: `docs/production_test_results.md`
