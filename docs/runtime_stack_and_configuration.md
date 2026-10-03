# Kitch Runtime Stack and Configuration

This is the operational reference for dependencies, local startup, environment
variables, database deployment, telemetry, and hosting. It intentionally does
not describe component flows or agent topology.

- End-to-end component and data-flow design: `system_architecture.md`
- Gemini/ADK agents, tools, routing, memory, and authority:
  `ai_agent_topology.md`
- User-facing behavior: `ux_user_flows.md`

## Runtime inventory

| Layer | Current implementation | Location |
| --- | --- | --- |
| Frontend | Next.js 16.2.6, React 19.2.4, ESLint 9 | `frontend/` |
| API | FastAPI, Uvicorn, Pydantic | `backend/app/main.py` |
| Agent runtime | Google ADK 2.x with native Gemini models | `backend/app/agent/` |
| Database | Supabase PostgreSQL | `backend/database/` |
| Provider transport | MCP SDK, HTTPX, provider adapters | `backend/app/providers/` |
| Token protection | `cryptography` Fernet | `backend/app/providers/credential_crypto.py` |
| Observability | ADK OpenTelemetry, optional Jaeger/LangSmith | `backend/app/telemetry.py` |

The complete Python dependency set is in `backend/requirements.txt`; frontend
packages and exact scripts are in `frontend/package.json`.

## Local startup

Backend:

```bash
cd backend
venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend development server:

```bash
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Frontend production-mode validation:

```bash
cd frontend
npm run lint
npm run build
npm run start -- --hostname 127.0.0.1 --port 3000
```

The frontend reads `NEXT_PUBLIC_API_BASE_URL`; its local default is
`http://localhost:8000`.

## Database deployment

The checked-in bootstrap schema is `backend/database/supabase_schema.sql`.
Existing projects must apply every versioned migration in
`backend/database/migrations/` before the backend starts. The bootstrap schema
and migrations are both deployment sources and must remain synchronized.

`GET /api/health/live` verifies only that the FastAPI process and event loop can
serve requests. `GET /api/health/ready` verifies elevated database access,
required tables and columns, and the configured household profile. Missing
migrations are startup or readiness failures; Kitch does not substitute local
persistence. Provider states are reported by readiness but do not make core
Kitch unready. Blocking database validation runs off the event loop, and live
provider probes have a bounded timeout.

Current structured tables are:

- `profiles`
- `meal_plans`
- `recipe_grocery_plans`
- `pantry_stock`
- `grocery_cart_items`
- `macro_diary`
- `provider_checkout_drafts`
- `provider_connections`
- `provider_oauth_clients`
- `provider_oauth_flows`
- `pending_agent_actions`

Table ownership and transaction boundaries are documented once in
`system_architecture.md`.

## Core backend environment

### Gemini

| Variable | Purpose |
| --- | --- |
| `KITCH_LLM_MODEL` | Gemini model ID. Defaults to `gemini-3.6-flash`; non-Gemini IDs are rejected. |
| `GOOGLE_API_KEY` | Google AI Studio authentication for local/API-key mode. |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` for AI Studio; `TRUE` for Vertex AI. |
| `GOOGLE_CLOUD_PROJECT` | Required in Vertex AI mode. |
| `GOOGLE_CLOUD_LOCATION` | Required in Vertex AI mode. |

All Kitch agents and the event compactor use the native ADK Gemini adapter.
There is no OpenAI/LiteLLM runtime path.

### Supabase

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL. |
| `SUPABASE_SECRET_KEY` | Preferred backend-only `sb_secret_...` credential. |
| `SUPABASE_SERVICE_ROLE_KEY` | Temporary legacy `service_role` JWT support. |

`SUPABASE_KEY`, publishable keys, anon JWTs, malformed keys, and redacted keys
are rejected. Configure exactly one elevated credential. Browser code never
receives it.

### Prototype household

Prototype members are centralized in:

- `backend/app/household_config.py`
- `frontend/src/app/householdConfig.js`

Shared resources currently use the configured household-owner profile;
nutrition rows remain member-specific. Auth-backed registration and multiple
households are not implemented yet.

## Session and memory services

Local development uses:

- `InMemorySessionService`
- `InMemoryMemoryService`

Backend restarts therefore clear conversations and natural-language household
preferences. Structured product state remains in Supabase. The planned cloud
replacement is `VertexAISessionService` plus `VertexAIMemoryBank`; this changes
durability, not the agent topology or the flexible-text memory model.

## Telemetry

Tracing is off by default and is initialized programmatically before the ADK
runner is created.

| Variable | Purpose |
| --- | --- |
| `KITCH_ADK_TRACING_ENABLED` | Explicitly enable tracing. |
| `KITCH_ADK_TRACING_REQUIRED` | Fail startup if tracing cannot initialize. |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | OTLP HTTP trace endpoint. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Shared OTLP endpoint. |
| `OTEL_SERVICE_NAME` | Defaults to `kitch-backend`. |
| `OTEL_RESOURCE_ATTRIBUTES` | Deployment/resource metadata. |
| `LANGSMITH_API_KEY` | Add LangSmith as an OTLP trace destination. |
| `LANGSMITH_PROJECT` | LangSmith project. |
| `LANGSMITH_OTEL_TRACES_ENDPOINT` | Optional LangSmith endpoint override. |
| `KITCH_LANGSMITH_TRACING_ENABLED` | Explicit LangSmith toggle. |

Local Jaeger example:

```bash
docker run --rm --name kitch-jaeger \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

```bash
KITCH_ADK_TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces
OTEL_SERVICE_NAME=kitch-backend
```

## Grocery-provider configuration

Provider behavior and checkout safety live in `system_architecture.md`; agent
authority over provider tools lives in `ai_agent_topology.md`. This section
contains configuration only.

### Zepto

| Variable | Purpose |
| --- | --- |
| `ZEPTO_MCP_ENABLED` | Enable or disable Zepto. |
| `ZEPTO_MCP_URL` | MCP endpoint; defaults to `https://mcp.zepto.co.in/mcp`. |
| `ZEPTO_MCP_ACCESS_TOKEN` | Preferred bearer-token variable. |
| `ZEPTO_MCP_BEARER_TOKEN` | Alternate bearer-token variable. |
| `ZEPTO_ACCESS_TOKEN` | Alternate bearer-token variable. |
| `ZEPTO_MCP_HEADERS` | Optional JSON MCP headers. |
| `ZEPTO_MCP_TRANSPORT` | Optional transport override. |
| `ZEPTO_MCP_REMOTE_COMMAND` | Local bridge command; defaults to `npx`. |
| `ZEPTO_MCP_REMOTE_ARGS` | Optional bridge argument list. |

Default local OAuth bridge:

```bash
npx -y mcp-remote https://mcp.zepto.co.in/mcp
```

### Swiggy Instamart

| Variable | Purpose |
| --- | --- |
| `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` | Fernet key for tokens and PKCE verifiers. |
| `SWIGGY_INSTAMART_ENABLED` | Enable the provider adapter and card. |
| `SWIGGY_INSTAMART_ENV` | `local`, `staging`, or `production`. |
| `SWIGGY_INSTAMART_MCP_URL` | MCP URL; must target the `/im` surface. |
| `SWIGGY_OAUTH_BASE_URL` | OAuth and dynamic-registration origin. |
| `SWIGGY_OAUTH_REDIRECT_URI` | Exact callback URI; HTTPS is required in production. |
| `SWIGGY_OAUTH_SCOPE` | Delegated scope; defaults to `mcp:tools`. |
| `SWIGGY_OAUTH_CLIENT_NAME` | Dynamic-registration client name. |
| `SWIGGY_INSTAMART_PRODUCTION_APPROVED` | Explicit production approval gate. |
| `FRONTEND_URL` | Browser destination after OAuth callback. |

One dynamic OAuth client is stored per environment and one encrypted
connection per household/provider/environment. OAuth state is single-use and
expires after ten minutes. With no usable refresh-token flow, token expiry or
HTTP 401 moves the connection to `reconnect_required`.

## Deployment direction

- Frontend: Vercel or equivalent Next.js hosting.
- Backend: a persistent Python runtime capable of FastAPI, ADK, and MCP client
  processes.
- Database: Supabase with migrations applied before backend rollout.
- Future session/memory durability: Vertex AI managed services.

Provider outages degrade only that provider; they do not make core Supabase
readiness fail. Instamart production remains gated by provider approval and
staging validation. Blinkit remains a disabled `Coming soon` descriptor.

Current defects and deliberately deferred engineering work are tracked only in
`known_issues_and_optimisations.md`.
