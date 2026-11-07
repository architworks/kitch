# Keep AI Code Off Everyday Request Paths

**Status:** Accepted (6 November 2026)

## Decision

Requests that do not use a model must not load model or agent code, and
independent database reads within one request run at the same time.

- **Lazy AI imports.** Agent frameworks, Vertex AI and Gemini SDK modules are
  imported inside the functions that need them, not at module load. This
  follows the existing `_LazyGroceryCheckoutService` pattern in
  `backend/app/main.py`.
- **Cheap metadata endpoints.** `GET /api/grocery/providers` reads the provider
  registry directly. It no longer builds the checkout service, which imports
  the Instamart cart agent and Vertex AI.
- **Parallel state load.** `GET /api/state/{member}` reads the household
  profile first, because it supplies the timezone. It then runs the remaining
  reads together with `asyncio.gather(asyncio.to_thread(...))`: pantry, diary,
  meal plan, recipe plan, members, targets and cart. `to_thread` copies the
  request's context variables, so household identity carries into each thread.
  The response shape is unchanged.

## Context

After the backend moved next to the database
([ADR 0006](0006-run-the-backend-next-to-the-database.md)), warm requests took
about 250–470 ms. Two problems remained:

1. **Slow first visit to Groceries.** On a freshly started instance, the first
   `/api/grocery/providers` call took 14–15 s. Listing grocery apps is static
   metadata, but the endpoint built the AI checkout service to answer it. That
   imported the cart agent, Vertex AI and Memory Bank: about 1.3 s locally and
   about 14 s on a cold serverless filesystem.
2. **Sequential dashboard reads.** The dashboard state load ran about eight
   independent queries one after another.

Moving one import in `pantry_service.py` (`google.genai.types`) inside the
function that uses it cut local backend import time from about 627 ms to
233 ms.

## Measurements

| | Before | After |
|---|---|---|
| First `/grocery/providers` on a fresh deployment | 14.2 s | 0.95 s (normal cold start) |
| Warm `/grocery/providers` (median) | 332 ms | 297 ms |
| Dashboard state load (median, Tokyo) | 467 ms | 410 ms |
| Full app load on a fresh deployment, all backend calls | — | about 2.8 s |

Once the function sits next to the database, parallel reads save only about
60 ms. They would have saved far more in the old topology, where round-trip
time dominated. The cold-import fix is the one users notice, because it removes
a 14-second freeze on first use.

## Rejected alternatives

- **Warm-up pings to keep instances hot.** These cost invocations and hide the
  problem without removing it; a fresh deployment or a scale-out still hits a
  cold path.
- **One combined SQL function for the dashboard.** It would be fewer round
  trips, but it would duplicate the logic in several existing Python readers.
  With the database a few milliseconds away, the gain no longer justifies it.

## Addendum (7 November 2026): keep the backend warm after idle

The rejection of warm-up pings above was about the 14-second Groceries freeze,
which had a code cause that we removed. A second, separate delay remained:
Vercel stops the Python backend after it has been idle, and the next request
waits for a new instance. That took 4.27 s after 20 minutes idle, then 0.29 s
once warm. Supabase was not involved; its queries during a slow login
returned in milliseconds. This delay has no code cause. It is how serverless
hosting behaves for a low-traffic app.

Decision: an external monitor (UptimeRobot, free plan) requests
`/backend/api/health/live` every 5 minutes. That endpoint touches no database
and does no model work.

- **Cost:** about 8,640 calls a month. That is under 1% of the Hobby plan's
  1 million calls, a minute or two of its 4 hours of CPU time, and about
  1.5 GB-hours of its 360. Vercel charges memory only while a request runs.
- **Why external:** Vercel's own cron on Hobby runs at most once a day.
  GitHub Actions schedules are disabled after 60 days without commits, which
  would silently bring the cold starts back.
- **Why not make startup lighter instead:** importing the Instamart modules
  only when needed would shorten the login wait, but users would then wait the
  same amount when they first open Instamart. Keeping the instance warm
  removes both waits.
- **Side benefit:** the monitor also emails the owner if the backend goes down.

The home screen also stopped loading in a chain. It used to run the sign-in
check, then the meal plan, then the rest of the household state. It now loads
the meal plan and the household state together after the sign-in check.

## Consequences

- New endpoints that only read data should not touch
  `grocery_checkout_service`, the ADK runner or memory modules.
- `python -X importtime -c "import app.main"` is the quick check for import
  regressions.
- Tests: `test/test_state_load.py` checks the shape is unchanged and that the
  reads overlap. `test/test_grocery_providers_endpoint.py` fails if listing
  providers loads the checkout service.
