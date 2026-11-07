# Kitch request latency, November 2026

Measured from a browser in India on kitch.archit-mishra.com, signed in, using the same script each time: 5 sequential calls per endpoint, after one warm-up request. Values in ms; median, with (min–max).

Database: Supabase, Tokyo (`ap-northeast-1`).

| Endpoint | A: baseline (backend in Washington, `iad1`) | B: backend in Tokyo (`hnd1`) | C: + code fixes |
|---|---|---|---|
| `GET /api/health/live` (no database) | 927 (540–979) | 253 (248–326) | 256 (249–287) |
| `GET /api/auth/session` (identity check) | 1590 (741–1615) | 286 (273–391) | 307 (297–383) |
| `GET /api/meal-plan` | 1771 (1138–2163) | 320 (299–351) | 307 (291–396) |
| `GET /api/state/{member}` (dashboard load) | 4158 (3308–4391) | 467 (428–525) | 410 (339–413) |
| `GET /api/grocery/providers` | 1944 (1850–15240) | 332 (306–489) | 334 (300–14209) |
| `DELETE /api/grocery/cart/items/{missing}` | 1028 (1007–2241) | 332 (311–385) | 329 (309–411) |

Notes:
- A, 6 Nov 2026: one `/grocery/providers` call took 15.2 s (a cold path), the other four 1.8–2.0 s.
- B, 6 Nov 2026: `x-vercel-id` reads `bom1::hnd1`. The first `/grocery/providers` batch failed once with a browser "Failed to fetch"; the rerun is shown.
- C, 6 Nov 2026 (`91055fb`): the first `/grocery/providers` call on the new deployment took 14.2 s again. Cause: listing providers built the checkout service, which imports the Instamart cart agent and Vertex AI. Fixed in the next commit by reading the provider registry directly.
- After that fix (`f3db13f`), first calls on a fresh deployment: `/grocery/providers` 297 (269–950), with the 950 ms first call a normal cold start. A full app load on a fresh deployment finished all backend calls in about 2.8 s.
- UI checks on production (`e4e9360`), 7 Nov 2026: a new cart item shows within 50 ms, a rename within 60 ms (the edit box now closes at once), and a double-clicked delete removes the row within 60 ms with no error. The server cart matched afterwards.
- Cold start, 7 Nov 2026: after 20 minutes idle, `/api/health/live` took 4.27 s, then 0.29 s and 0.28 s. Supabase was not involved: its queries during a slow login returned in milliseconds.
- Home load order (`3caf2e4`): the meal plan and household state now start together. Before, it was sign-in check → meal plan → state, one after another. On production the two calls now start within 1 ms of each other and finish about 0.5 s after the sign-in check.
