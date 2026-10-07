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
| Frontend | Next.js 16.3.x, React 19.2.4, ESLint 9 | `frontend/` |
| API | FastAPI, Uvicorn, Pydantic | `backend/app/main.py` |
| Agent runtime | Google ADK 2.x with native Gemini models | `backend/app/agent/` |
| Household memory | Vertex AI Memory Bank or ADK in-memory memory | `backend/app/agent/memory.py` |
| Database | Supabase PostgreSQL or local SQLite | `backend/app/storage.py` |
| Provider transport | MCP SDK, HTTPX, provider adapters | `backend/app/providers/` |
| Token protection | `cryptography` Fernet | `backend/app/providers/credential_crypto.py` |
| Observability | ADK OpenTelemetry, optional Jaeger/LangSmith | `backend/app/telemetry.py` |

The complete Python dependency set is in `backend/requirements.txt`; frontend
packages and exact scripts are in `frontend/package.json`.

## Local startup

The supported local path is documented in `local_setup.md`:

```bash
cp backend/.env.local.example backend/.env.local
python3.12 scripts/kitch.py setup
python3.12 scripts/kitch.py start
```

The terminal command runs both servers and performs local SQLite migrations.
Manual backend/frontend commands remain useful for development.

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

`KITCH_DATABASE_BACKEND=sqlite|supabase` selects structured persistence without
affecting memory. It defaults to `supabase` to preserve hosted deployments.
SQLite uses `KITCH_SQLITE_PATH` (default `.kitch/kitch.sqlite3`), migrates
automatically, and never falls back to Supabase. The hosted procedure is in
`supabase_setup.md`.

Database and memory selection are independent. SQLite + in-memory is the easy
local default, while Supabase + Vertex is the hosted default; SQLite + Vertex
and Supabase + in-memory are also supported when explicitly configured.

The checked-in bootstrap schema is `backend/database/supabase_schema.sql`.
Existing projects must apply every versioned migration in
`backend/database/migrations/` before the backend starts. The bootstrap schema
and migrations are both deployment sources and must remain synchronized.

`GET /api/health/live` verifies only that the FastAPI process and event loop can
serve requests. `GET /api/health/ready` verifies elevated database access,
required tables and columns, and the configured household profile. Missing
migrations are startup or readiness failures; Kitch does not substitute local
persistence. Provider and memory states are reported independently by
readiness but do not make core Kitch unready. Blocking database validation runs
off the event loop, and live provider and memory probes have bounded timeouts.

Current structured tables are:

- `households` (hosted)
- `household_accounts` (hosted)
- `profiles`
- `nutrition_targets`
- `provider_selection_state`
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
There is no OpenAI/LiteLLM runtime path. The current local and Vercel setup may
continue using AI Studio mode (`GOOGLE_GENAI_USE_VERTEXAI=FALSE`) with
`GOOGLE_API_KEY`. Setting `GOOGLE_GENAI_USE_VERTEXAI=TRUE` is an optional move
of **Gemini inference** to standard Vertex AI and also requires Google Cloud
Application Default Credentials; it is not required for deployment or for
Memory Bank.

Gemini inference and household memory have separate authentication paths. A
deployment may therefore use `GOOGLE_API_KEY` for Gemini while Memory Bank uses
standard Google Cloud credentials. Locally those credentials come from ADC;
on Vercel they are short-lived credentials obtained through OIDC federation.

### Structured persistence

| Variable | Purpose |
| --- | --- |
| `KITCH_DATABASE_BACKEND` | `sqlite` for local state or `supabase` for hosted state. Defaults to `supabase`. |
| `KITCH_SQLITE_PATH` | SQLite file path, used only by the SQLite backend. |

### Supabase

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL. |
| `SUPABASE_SECRET_KEY` | Preferred backend-only `sb_secret_...` credential. |
| `SUPABASE_SERVICE_ROLE_KEY` | Temporary legacy `service_role` JWT support. |

`SUPABASE_KEY`, publishable keys, anon JWTs, malformed keys, and redacted keys
are rejected. Configure exactly one elevated credential. Browser code never
receives it.

### Household identity

An empty SQLite installation uses first-run household bootstrap. Every entered
name creates a profile, the first profile owns shared state, household size is
the number of profiles, and the browser supplies its system IANA timezone.
Hosted Supabase requires Google Sign-In: one verified Google subject creates or
loads one household and one owner profile. Other household members remain
editable internal profiles, not login accounts. In both modes the frontend
hydrates stable member IDs and editable names from backend state.

| Variable | Purpose |
| --- | --- |
| `GOOGLE_OAUTH_CLIENT_ID` | Backend audience used to verify hosted Google ID tokens. |
| `KITCH_AUTH_SESSION_SECRET` | At least 32 random characters used to sign HttpOnly Kitch sessions. |
| `KITCH_LEGACY_HOUSEHOLD_OWNER_EMAIL` | One-time optional owner email allowed to claim the pre-authentication household. Remove after the account mapping exists. |
| `KITCH_ALLOWED_ORIGINS` | Comma-separated exact browser origins allowed by CORS. |
| `KITCH_EXPOSE_API_DOCS` | Keep unset/false in hosted environments; explicit opt-in for OpenAPI routes. |
| `KITCH_MAX_REQUEST_BYTES` | Maximum non-upload request body size; defaults to 2 MiB. |
| `KITCH_MAX_UPLOAD_BYTES` | Maximum image payload; defaults to 10 MiB. |

The frontend uses the same public web-client ID in
`NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID`. Direct Google Identity Services credential
mode needs authorized JavaScript origins, not an OAuth redirect URI.

## Session and memory services

Chat sessions use `InMemorySessionService` in every environment. A backend
restart can therefore end a short conversation, by design; Kitch does not use
Agent Platform Sessions or submit whole sessions to memory.

Household kitchen context uses a configurable ADK memory service:

| Variable | Purpose |
| --- | --- |
| `KITCH_MEMORY_SERVICE` | `in_memory` for tests/optional local work, or `vertex` for persistent Memory Bank. |
| `KITCH_MEMORY_BANK_ID` | Bare reasoning-engine ID or full resource name created for Memory Bank. Required for `vertex`. |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project that owns the Memory Bank. |
| `GOOGLE_CLOUD_LOCATION` | Memory Bank location, currently `global`. |
| `GCP_PROJECT_NUMBER` | Numeric Google Cloud project ID used in the Vercel WIF audience. Vercel only. |
| `GCP_SERVICE_ACCOUNT_EMAIL` | Service account impersonated by Vercel. Vercel only. |
| `GCP_WORKLOAD_IDENTITY_POOL_ID` | Workload Identity Pool ID. Vercel only. |
| `GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID` | Vercel OIDC provider ID in that pool. Vercel only. |

Local processes default to `in_memory` when the service variable is omitted;
that supported local memory intentionally resets on backend restart. Vercel
defaults to `vertex`, so a deployment missing its Memory Bank
or federation configuration reports degraded memory rather than silently
creating a local memory store. Set the service variable explicitly in every
environment.

With `vertex`, Kitch uses `VertexAiMemoryBankService`; selected
specialists submit deliberate natural-language user events and await Google’s
generation/consolidation result. It does not ingest every turn. Searches and
writes are scoped to app `kitch` plus the stable household-owner profile UUID.
No automatic fallback to process-local memory occurs when persistent memory is
misconfigured or unavailable. Memory tools report the failure explicitly while
structured-persistence features remain usable.

Create or identify the empty Memory Bank once (this does not deploy an agent
runtime):

```bash
cd backend
venv/bin/python scripts/setup_memory_bank.py --create
```

Copy the printed `KITCH_MEMORY_BANK_ID` into the local or Vercel backend
environment. `GET /api/health/ready` reports the memory backend, durability,
state, and a credential-safe diagnostic. The resource starts empty; old
process-local preferences have no durable source and are intentionally not
migrated.

For local development, authenticate ADC once before starting Kitch:

```bash
gcloud auth application-default login
```

For Vercel, the backend reads the signed `x-vercel-oidc-token` request header,
exchanges it through the configured Workload Identity Provider, and
impersonates the configured service account. No long-lived Google credential
or Memory Bank API key is stored in Vercel.

## Telemetry

Tracing is off by default and is initialized programmatically before the ADK
runner is created.

Memory operations emit only operation type, backend, normalized outcome, and
latency. API keys, submitted statements, search queries, and returned memory
facts are never written by Kitch telemetry.

| Variable | Purpose |
| --- | --- |
| `KITCH_ADK_TRACING_ENABLED` | Explicitly enable tracing. |
| `KITCH_ALLOW_SENSITIVE_ADK_TRACES` | Required second opt-in because ADK spans may contain prompts, responses and tool arguments. |
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
KITCH_ALLOW_SENSITIVE_ADK_TRACES=true
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces
OTEL_SERVICE_NAME=kitch-backend
```

## Grocery-provider configuration

Provider behavior and checkout safety live in `system_architecture.md`; agent
authority over provider tools lives in `ai_agent_topology.md`. This section
contains configuration only.

Provider retention defaults are configured with
`KITCH_OAUTH_FLOW_RETENTION_HOURS=24`,
`KITCH_PROVIDER_DRAFT_RETENTION_HOURS=24`, and
`KITCH_EXPIRED_PROVIDER_CONNECTION_RETENTION_DAYS=30`. See
`security_and_privacy.md` for the exact lifecycle and deletion behavior.

### Zepto

| Variable | Purpose |
| --- | --- |
| `ZEPTO_MCP_ENABLED` | Enable or disable Zepto. Defaults to disabled/Coming Soon unless explicitly set to `true`. |
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
| `SWIGGY_INSTAMART_ENV` | Optional explicit override: `local`, `staging`, or `production`. When omitted, an HTTPS callback or Vercel production deployment is treated as production; localhost remains local. |
| `SWIGGY_INSTAMART_MCP_URL` | MCP URL; must target the `/im` surface. |
| `SWIGGY_OAUTH_BASE_URL` | OAuth and dynamic-registration origin. |
| `SWIGGY_OAUTH_REDIRECT_URI` | Exact callback URI; HTTPS is required in production. |
| `SWIGGY_OAUTH_SCOPE` | Delegated scope; defaults to `mcp:tools`. |
| `SWIGGY_OAUTH_CLIENT_NAME` | Dynamic-registration client name. |
| `SWIGGY_INSTAMART_PRODUCTION_APPROVED` | Explicit production approval gate. |
| `FRONTEND_URL` | Optional cross-origin browser destination after OAuth callback; omit for same-origin deployment. |

One dynamic OAuth client is stored per environment and one encrypted
connection per household/provider/environment. OAuth state is single-use and
expires after ten minutes. With no usable refresh-token flow, token expiry or
HTTP 401 moves the connection to `reconnect_required`.

Canonical console procedures are in `vertex_memory_setup.md` and
`vercel_wif_setup.md`; this reference defines runtime behavior and variables.

## Deployment direction

- Frontend: Vercel or equivalent Next.js hosting.
- Backend: Vercel-hosted FastAPI with ADK and MCP client support.
- Database: Supabase with migrations applied before backend rollout.
- Household preference durability: Vertex AI Agent Engine Memory Bank through
  local ADC or Vercel OIDC federation; conversations remain intentionally
  ephemeral.

Provider outages degrade only that provider; they do not make core persistence
readiness fail. Instamart production remains gated by provider approval and
staging validation. Blinkit remains a disabled `Coming soon` descriptor.

Current defects and deliberately deferred engineering work are tracked only in
`known_issues_and_optimisations.md`.
