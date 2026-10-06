# Kitch Security and Privacy

This is the canonical security reference for hosted authentication, household
isolation, browser/API boundaries, provider credentials, telemetry, and data
retention. Provider workflow behavior remains in `system_architecture.md`.

## Hosted identity and household isolation

- Hosted Supabase deployments require Google Sign-In.
- FastAPI verifies the Google ID token against `GOOGLE_OAUTH_CLIENT_ID`, then
  issues a signed, seven-day, HttpOnly, SameSite=Lax session cookie.
- One verified Google `sub` maps to one row in `household_accounts`, one
  household, and one owner profile.
- Every protected request establishes a server-owned household context. Storage
  functions derive owner/member IDs from that context rather than accepting a
  household ID from the browser.
- Household members are internal profiles. Renaming a profile preserves its ID,
  nutrition records, and linked history.
- The browser never receives a Supabase secret/service-role key.

SQLite local mode intentionally bypasses hosted authentication and supports one
local household.

## Browser and API controls

- CORS accepts only `KITCH_ALLOWED_ORIGINS`; credentials are never combined
  with a wildcard origin. Without an override, hosted Supabase mode accepts
  only the production Kitch origin, while local SQLite mode accepts only the
  documented localhost origins.
- Hosted OpenAPI endpoints are disabled unless
  `KITCH_EXPOSE_API_DOCS=true` is explicitly set.
- Public liveness and readiness responses expose only safe status. Detailed
  component/provider diagnostics require an authenticated household.
- Frontend and backend responses apply frame, MIME-sniffing, referrer,
  permissions, same-origin resource isolation, and the Google-compatible
  `same-origin-allow-popups` opener policy. Hosted responses also apply HSTS,
  and the frontend applies a restrictive Content Security Policy.
- JSON request bodies and image uploads have separate configurable size limits.
- Authentication, chat, photo upload, and checkout endpoints have bounded
  process-local throttles. A distributed public deployment should add an edge
  rate limiter in front of FastAPI as a second layer.
- Public errors use normalized messages; raw provider, database and token
  payloads stay in credential-safe server logs.

## Provider credentials and checkout authority

- Swiggy authorization uses Dynamic Client Registration plus OAuth 2.1 PKCE.
- A flow is owned by the current household owner, hashed by state, expiring and
  single-use. The callback must also carry the same Kitch session cookie.
- Access tokens and PKCE verifiers are encrypted with the dedicated provider
  credential key. They are never returned to the browser or an agent.
- Agents may prepare reversible carts. Checkout, payment approval and order
  placement remain backend operations invoked only by the reviewed UI flow.
- Disconnect deletes the household token and checkout draft after best-effort
  provider logout.

## Retention and deletion

Kitch keeps deterministic household data until the user edits/deletes it or the
household is removed. Provider security records use shorter defaults:

| Data | Default retention behavior |
| --- | --- |
| OAuth state and encrypted PKCE verifier | Expiring and single-use; expired records are purged after 24 hours when another flow starts. |
| Active provider connection | Retained until disconnect or token expiry. Connections expired for more than 30 days are deleted when next accessed. |
| Checkout review, mapping, payment and order-attempt state | Retained for reload/recovery, then deleted after 30 days of inactivity when next accessed. |
| Environment-level dynamic OAuth client registration | Retained while that provider/environment remains configured; it contains no household access token. |

The windows are configurable with `KITCH_OAUTH_FLOW_RETENTION_HOURS`,
`KITCH_PROVIDER_DRAFT_RETENTION_DAYS`, and
`KITCH_EXPIRED_PROVIDER_CONNECTION_RETENTION_DAYS`.

Swiggy processes delegated authentication, account addresses, catalogue/cart
operations and checkout under its own service terms and infrastructure. Kitch
must complete Swiggy production onboarding before advertising production
availability. Do not assume a data-processing region that Swiggy has not
contractually documented.

## Telemetry

Custom memory/provider telemetry excludes tokens, addresses, raw provider
payloads and memory text. ADK framework traces may contain prompts, model
responses and tool arguments, so exporter configuration alone is insufficient:
they are exported only when `KITCH_ALLOW_SENSITIVE_ADK_TRACES=true` is also set.
Use that opt-in only with a destination approved for household content.

## Dependency audit status

The 2026-10-06 release audit found no known vulnerabilities in
`backend/requirements.txt` with `pip-audit`. `npm audit --omit=dev` found no
high or critical vulnerabilities; its remaining moderate transitive Next.js
finding has no upstream fix and is tracked as `SEC-001` in
`known_issues_and_optimisations.md`.
