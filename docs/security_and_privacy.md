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
- Household members are profiles. A new owner names them, or just sets a
  headcount, on a one-time setup screen. The owner can also share an invite
  link (7-day expiry, only its SHA-256 hash stored, a new link replaces the old)
  so others join with their own Google account, either claiming an unclaimed
  member profile or as someone new. Renaming a profile preserves its ID,
  nutrition records, and linked history.
- `household_accounts.owner_profile_id` is the household's shared-data anchor
  for every account; `profile_id` is the account's own member profile and
  `role` is `owner` or `member`. Only the owner manages invites, connects or
  disconnects grocery apps, places orders, and deletes the household; a member
  can only leave, which deletes their own login and profile.
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
| Checkout review, mapping, minimal payment state and order outcome | Expires 24 hours after its latest active update. PostgreSQL purges expired rows hourly; draft reads also purge, and SQLite purges at startup. Payment hand-off URLs are never persisted. |
| Environment-level dynamic OAuth client registration | Retained while that provider/environment remains configured; it contains no household access token. |

The windows are configurable with `KITCH_OAUTH_FLOW_RETENTION_HOURS`,
`KITCH_PROVIDER_DRAFT_RETENTION_HOURS`, and
`KITCH_EXPIRED_PROVIDER_CONNECTION_RETENTION_DAYS`.

Swiggy processes delegated authentication, account addresses, catalogue/cart
operations and checkout under its own service terms and infrastructure. Kitch
must complete Swiggy production onboarding before advertising production
availability. Do not assume a data-processing region that Swiggy has not
contractually documented.

## Legal notice, consent and account deletion

- The public Privacy Policy (`/privacy`) and Terms of Use (`/terms`) are
  versioned by `LEGAL_TERMS_VERSION`, kept identical in `backend/app/legal.py`
  and `frontend/src/kitch/legal.js`. Bump both when either document changes
  materially; every owner is then asked to accept again.
- Hosted owners confirm they are 18+ and accept the notice, including
  health-related nutrition logs, before Google sign-in or on a one-time
  consent screen. The accepted version and timestamps are stored on
  `household_accounts`, and the version rides in the signed session cookie.
- Until the current version is accepted, the API answers `403
  consent_required` for everything except session, consent, sign-out, account
  deletion and health checks.
- `DELETE /api/account` disconnects Swiggy (best-effort provider logout),
  purges the household's Vertex Memory Bank memories, deletes the account and
  household rows (cascading to every profile record), and clears the session.
- Local SQLite mode has no sign-in, so it shows the legal links but no consent
  gate or account deletion.
- The privacy contact shown on the legal pages and footers defaults to
  architmishrapro@gmail.com; `NEXT_PUBLIC_KITCH_CONTACT_EMAIL` overrides it.

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
