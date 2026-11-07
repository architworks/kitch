# Run the Backend Next to the Database

**Status:** Accepted (6 November 2026)

## Decision

Kitch's Vercel functions run in Tokyo (`hnd1`), the same region as the Supabase
database (`ap-northeast-1`). The region is set in the Vercel dashboard
(Settings → Functions → Function Region); `vercel.json` is unchanged.

When the database moves, the function region moves with it. Function placement
follows the database, not the user.

## Context

Simple, non-AI actions on the hosted app were slow: deleting a cart row took
about a second, and loading the dashboard took about four. The slowness was bad
enough to cause a bug. People clicked delete twice because nothing happened,
and the second request failed with "durable storage is unavailable".

The obvious suspects were the LLM and agent steps, but none of these requests
touch a model. The cause was deployment topology:

```
Browser (India) ──► Vercel edge (Mumbai, bom1)
                     └─► Function (Washington DC, iad1)
                           └─► Supabase (Tokyo) × several queries, one after another
```

Each database query crossed the Pacific, about 150–170 ms per round trip. A
typical request makes several queries in sequence: an identity and role check,
the action, then a reload of the result. The dashboard state load made about
eight queries. The latency came from multiplying those round trips, not from
any single slow query.

## Measurements

The same script ran each time from a signed-in browser in India: one warm-up
call, then 5 sequential calls per endpoint. Medians are in ms. The full table
and method are in `docs/performance/latency-2026-11.md`.

| Endpoint | Washington (`iad1`) | Tokyo (`hnd1`) | Change |
|---|---|---|---|
| Health check (no database) | 927 | 253 | 3.7× |
| Sign-in check | 1590 | 286 | 5.6× |
| Meal plan | 1771 | 320 | 5.5× |
| Dashboard state load | 4158 | 467 | 8.9× |
| Grocery app list | 1944 | 332 | 5.9× |
| Cart delete | 1028 | 332 | 3.1× |

Endpoints that make more queries improved more, as round-trip multiplication
predicts. The region change was a single setting with no code change, and it
produced most of the total improvement. The code changes in
[ADR 0007](0007-make-everyday-cart-actions-instant-and-idempotent.md) and
[ADR 0008](0008-keep-ai-code-off-everyday-request-paths.md) came after it.

## Why Tokyo and not Mumbai

Putting the function near the user (Mumbai, `bom1`) looks attractive but would
change little. The browser-to-function hop happens once per request, while the
function-to-database hop happens once per query. With the database in Tokyo,
every query would still cross India ↔ Tokyo. Co-locating the function with the
database removes the hop that repeats.

## Rejected alternatives

- **Keep Washington and cache reads.** This adds invalidation complexity to
  household data that changes often, such as cart, pantry and diary, and it
  does nothing for writes.
- **Functions in several regions.** The Hobby plan allows one region. With a
  single database region, extra function regions would be further from the
  data anyway.
- **Move the database to Mumbai and the functions to `bom1`.** This is the best
  end state for users in India, but a Supabase project's region cannot be
  changed in place. It needs a new project, a data migration, new keys and
  downtime. Kitch may do it later; if so, the function region moves with the
  database under this ADR.

## Consequences

- Household data does not move. Only compute moves, from the US to Japan, and
  the privacy policy's "processed outside India" wording stays accurate.
- Calls to Vertex AI Memory Bank (US region) get slightly slower for chat. That
  cost is small next to model time, and chat is not an everyday instant action.
- Verify the region with
  `curl -sD- https://kitch.archit-mishra.com/backend/api/health/live | grep x-vercel-id`.
  The middle segment should read `hnd1`.

## Lesson

Agentic apps are not slow only because of their agents. Here, every non-AI
action was 3–9× slower than it needed to be because the server sat on a
different continent from its database. Measure where the time goes before
optimising prompts or models.
