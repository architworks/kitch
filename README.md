# Kitch

Kitch is an AI household kitchen companion for shared meal planning, pantry-aware recipe and grocery preparation, delivery-cart review, and individual nutrition logging.

The product is built around a simple distinction: meal plans, pantry stock, recipes, and grocery carts are shared household state, while nutrition logs remain personal to the active household member. The current prototype household is configured as Archit, Anubhav, and Naman while full auth-backed household registration is deferred.

## What Is Kitch

Kitch helps a household answer the everyday kitchen questions that usually live across chat threads, memory, notes apps, and grocery carts:

- What should we cook this week?
- What is already in the fridge or pantry?
- What ingredients do we need for a recipe or planned meal?
- What should be added to a delivery cart?
- What did I personally eat today, and how many macros did that add?

The app combines conversational control with structured, reviewable state. Users can ask for a weekly plan, swap a meal, scan a fridge photo, log a plate, generate groceries, or prepare a Zepto cart through natural language. The saved plan, pantry, recipe artifacts, native cart rows, and macro diary are persisted in Supabase so the UI can render what actually changed.

## What Can Kitch Do

- Generate a Monday-Sunday meal plan for the upcoming planning week.
- Store meal names in a lightweight weekly schedule without pre-generating every recipe.
- Modify one meal slot without rewriting the rest of the plan.
- Answer schedule questions such as "what's for dinner tonight?"
- Generate recipe cards, ingredients, and cooking steps on demand.
- Derive grocery rows from the same recipe artifact so recipes and groceries stay aligned.
- Track shared household pantry and fridge stock from text or fridge photos.
- Mark pantry-covered grocery rows as visible but excluded from provider sync.
- Preserve manual native-cart rows when the agent replans grocery requirements.
- Sync selected, non-stocked native cart rows to Zepto for review.
- Surface actual Zepto cart items and unavailable or unresolved provider items.
- Require explicit frontend approval before placing a real order.
- Log personal meals and estimated macros from text or plate photos.
- Keep macro diaries scoped to the active user.
- Store flexible household food and brand preferences in ADK memory.

## How Kitch Works

### Overall System Design

Kitch is split into five main runtime layers:

1. **Next.js frontend** renders the dashboard, Recipes page, Groceries page, floating chat, member switching, and explicit approval controls.
2. **FastAPI backend gateway** exposes browser-facing APIs, prepares ADK turns, handles image uploads, hydrates UI state, and guards provider/order workflows.
3. **Google ADK 2.0 runtime** runs the multi-agent graph behind the backend.
4. **Supabase PostgreSQL** stores deterministic product records such as meal plans, pantry stock, recipe artifacts, native cart rows, profiles, and macro diary logs.
5. **Provider adapters** translate Kitch's native grocery cart into external provider carts. Zepto MCP is the current live provider integration.

The browser does not call the model, ADK, Supabase admin APIs, or Zepto MCP directly. It talks to FastAPI, and FastAPI owns secrets, context preparation, tool execution, provider review snapshots, and order safety boundaries.

### Agent Topology

Kitch uses a Google ADK hub-and-spoke topology:

- `kitch_coordinator`: parent triage agent. It interprets natural language, routes work to specialists, and avoids direct side effects.
- `chef_planner`: lightweight household meal scheduler. It generates weekly meal-name plans, reads plans, answers schedule questions, and updates individual slots.
- `vision_scanner`: food intake and pantry/fridge scanner. It estimates macros from text or plate photos, logs meals to the active user, and updates shared pantry stock from text or fridge photos.
- `recipe_grocery_planner`: recipe, ingredient, pantry-aware grocery, native-cart, and preference planner. It generates recipe artifacts, reads pantry, derives native cart rows, preserves manual rows, and stores/searches household preferences.

Agents call Python tools for deterministic reads and writes. Supabase is the source of truth for structured app state; ADK memory is used for flexible household preference text such as "avoid tofu" or "prefer Amul butter."

### Zepto MCP Integration

Kitch owns a provider-agnostic native grocery cart. Zepto is a translation target, not the source of truth.

The Zepto flow is:

1. The user reviews native Kitch grocery rows in the Groceries page.
2. The user selects eligible rows to move to Zepto.
3. FastAPI excludes unselected and pantry-covered rows.
4. Backend code applies household brand preferences to provider search terms where possible.
5. `ZeptoProviderAdapter` uses Zepto MCP to search products, replace/update the Zepto cart, and read the resulting provider cart.
6. FastAPI saves a Zepto review snapshot with matched items, unavailable items, checkout context, snapshot hash, and confirmation token.
7. The frontend displays the actual provider cart for review.
8. A real order can only be placed after explicit frontend approval using the saved review snapshot.

Chat text can plan groceries and prepare cart state, but it must not place a real order by itself.

## Local Deployment

### Prerequisites

- Python 3.12 or newer.
- Node.js and npm.
- A Supabase project.
- An LLM provider configuration for either Gemini or an OpenAI-compatible endpoint.
- Optional: Zepto MCP authentication if you want live Zepto cart sync.

### 1. Install Backend Dependencies

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Supabase

1. Create a Supabase project.
2. Open the Supabase SQL editor.
3. Run the schema in `backend/database/supabase_schema.sql`.
4. Ensure the prototype household profile IDs exist, or update the configured IDs in `backend/app/household_config.py` and `frontend/src/app/householdConfig.js`.

The default prototype IDs are:

| Member | UUID |
| --- | --- |
| Archit | `00000000-0000-0000-0000-000000000000` |
| Anubhav | `11111111-1111-1111-1111-111111111111` |
| Naman | `22222222-2222-2222-2222-222222222222` |

Because the schema enables Row Level Security and `profiles.id` references `auth.users.id`, local development is simplest with a backend-only Supabase service role key plus matching Supabase auth users/profiles. If you create real auth users through Supabase Auth, copy their UUIDs into the household config files instead of using the prototype UUIDs above. Never expose the service role key to the frontend.

### 3. Create Backend Environment File

Create `backend/.env`:

```bash
SUPABASE_URL=...
SUPABASE_KEY=...

# Recommended production-style Gemini setup
KITCH_LLM_PROVIDER=gemini
KITCH_LLM_MODEL=gemini-flash-latest
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=...

# Optional Zepto MCP setup
ZEPTO_MCP_ENABLED=false
```

`backend/.env` is loaded by FastAPI and the ADK runtime. Keep this file gitignored.

### 4. Choose an LLM Provider

Gemini mode:

```bash
KITCH_LLM_PROVIDER=gemini
KITCH_LLM_MODEL=gemini-flash-latest
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=...
```

OpenAI-compatible mode:

```bash
KITCH_LLM_PROVIDER=openai_compatible
KITCH_LLM_MODEL=...
KITCH_LLM_API_KEY=...
KITCH_LLM_API_BASE=...
KITCH_LLM_LITELLM_PREFIX=openai
KITCH_LLM_CUSTOM_PROVIDER=openai
```

The backend also supports legacy local fallback names:

```bash
OPENAI_MODEL_NAME=...
OPENAI_API_KEY=...
OPENAI_API_BASE=...
```

### 5. Configure Zepto MCP (Optional)

Leave Zepto disabled for basic local development:

```bash
ZEPTO_MCP_ENABLED=false
```

To enable Zepto MCP, configure one of the supported auth paths:

```bash
ZEPTO_MCP_ENABLED=true
ZEPTO_MCP_URL=https://mcp.zepto.co.in/mcp
ZEPTO_MCP_ACCESS_TOKEN=...
```

Alternate token/header variables supported by the adapter:

```bash
ZEPTO_MCP_BEARER_TOKEN=...
ZEPTO_ACCESS_TOKEN=...
ZEPTO_MCP_HEADERS='{"Header-Name":"value"}'
```

For local browser OAuth bridge mode, omit the token and allow the adapter to use:

```bash
npx -y mcp-remote https://mcp.zepto.co.in/mcp
```

Advanced transport variables:

```bash
ZEPTO_MCP_TRANSPORT=...
ZEPTO_MCP_REMOTE_COMMAND=npx
ZEPTO_MCP_REMOTE_ARGS='["-y","mcp-remote","https://mcp.zepto.co.in/mcp"]'
```

### 6. Run the Backend

From `backend/`:

```bash
venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

### 7. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 8. Configure Frontend Environment

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

If this variable is omitted, the frontend falls back to `http://localhost:8000`.

### 9. Run the Frontend

From `frontend/`:

```bash
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open:

```text
http://127.0.0.1:3000
```

## Environment Variables Reference

### Backend Required

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL. |
| `SUPABASE_KEY` | Supabase backend key. For local development with RLS, use a server-side service role key. |

### Backend LLM Provider

| Variable | Purpose |
| --- | --- |
| `KITCH_LLM_PROVIDER` | `gemini` or `openai_compatible`. Defaults to `openai_compatible`. |
| `KITCH_LLM_MODEL` | Model name passed to the selected adapter. |
| `KITCH_LLM_API_KEY` | Generic API key for OpenAI-compatible mode. |
| `KITCH_LLM_API_BASE` | Generic base URL for OpenAI-compatible mode. |
| `KITCH_LLM_LITELLM_PREFIX` | LiteLLM model prefix. Defaults to `openai`. |
| `KITCH_LLM_CUSTOM_PROVIDER` | LiteLLM custom provider. Defaults to `openai`. |
| `GOOGLE_API_KEY` | Google AI Studio key for Gemini API-key mode. |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` for AI Studio API-key mode, `TRUE` for Vertex AI mode. |
| `GOOGLE_CLOUD_PROJECT` | Required for Vertex AI mode. |
| `GOOGLE_CLOUD_LOCATION` | Required for Vertex AI mode. |
| `OPENAI_MODEL_NAME` | Legacy local fallback model name. |
| `OPENAI_API_KEY` | Legacy local fallback API key. |
| `OPENAI_API_BASE` | Legacy local fallback base URL. |

### Zepto MCP (Optional)

| Variable | Purpose |
| --- | --- |
| `ZEPTO_MCP_ENABLED` | Set to `false` to disable Zepto MCP calls. |
| `ZEPTO_MCP_URL` | Zepto MCP endpoint. Defaults to `https://mcp.zepto.co.in/mcp`. |
| `ZEPTO_MCP_ACCESS_TOKEN` | Bearer token for Zepto MCP. |
| `ZEPTO_MCP_BEARER_TOKEN` | Alternate bearer token variable. |
| `ZEPTO_ACCESS_TOKEN` | Alternate token variable. |
| `ZEPTO_MCP_HEADERS` | Optional JSON object of extra MCP headers. |
| `ZEPTO_MCP_TRANSPORT` | Optional transport override. |
| `ZEPTO_MCP_REMOTE_COMMAND` | Local OAuth bridge command. Defaults to `npx`. |
| `ZEPTO_MCP_REMOTE_ARGS` | Optional custom `mcp-remote` argument list. |

### Frontend

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Browser-visible FastAPI base URL. Defaults to `http://localhost:8000`. |

## Project Structure

```text
backend/
  app/
    agent/              ADK agent graph, prompts, tools, sessions, memory
    providers/          Zepto MCP provider adapter
    main.py             FastAPI gateway and browser-facing routes
    supabase_client.py  Supabase data access layer
  database/
    supabase_schema.sql Supabase schema

frontend/
  src/app/              Next.js app, dashboard, recipes, groceries, chat UI

docs/
  vision_and_requirements.md
  ux_user_flows.md
  current_architecture.md
  current_ai_agent_architecture.md
  current_technology_stack.md
  test_scenarios.md
  production_test_results.md
```

## Key Product Boundaries

- Meal planning is shared household state.
- Pantry, recipes, recipe-grocery artifacts, and native grocery cart rows are shared household state.
- Macro diary entries are individual to the active member.
- Recipe-only requests save recipe artifacts but do not update the cart.
- Grocery/cart/buy/order requests save recipe artifacts and update agent-planned native cart rows.
- Manual cart rows are preserved across agent grocery replanning.
- Pantry-covered rows remain visible but are excluded from provider sync.
- Provider prices and fees should only come from provider responses.
- Chat cannot place real orders.
- Zepto order placement requires a saved review snapshot, confirmation token, and explicit frontend approval.

## Current Limitations

- Multi-household registration and auth-backed membership are deferred.
- ADK sessions and memory currently use in-memory local services, so backend restarts clear chat/session memory and flexible preferences.
- Supabase persists product-critical records.
- Blinkit live cart insertion is not implemented.
- Pantry quantity reconciliation across arbitrary units is intentionally limited.
- Zepto MCP auth and catalog behavior depend on the external provider.
- Known orchestration issue: compound requests that span multiple specialist agents may currently be routed to only one sub-agent.

## More Documentation

Start with these files for deeper context:

- `docs/vision_and_requirements.md`
- `docs/current_architecture.md`
- `docs/current_ai_agent_architecture.md`
- `docs/current_technology_stack.md`
- `docs/ux_user_flows.md`
- `docs/known_issues.md`
