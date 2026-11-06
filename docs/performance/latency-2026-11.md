# Kitch request latency, November 2026

Measured from a browser in India on kitch.archit-mishra.com, signed in, using the same script each time: 5 sequential calls per endpoint, after one warm-up request. Values in ms; median, with (min–max).

Database: Supabase, Tokyo (`ap-northeast-1`).

| Endpoint | A: baseline (backend in Washington, `iad1`) | B: backend in Tokyo (`hnd1`) | C: + code fixes |
|---|---|---|---|
| `GET /api/health/live` (no database) | 927 (540–979) | 253 (248–326) | |
| `GET /api/auth/session` (identity check) | 1590 (741–1615) | 286 (273–391) | |
| `GET /api/meal-plan` | 1771 (1138–2163) | 320 (299–351) | |
| `GET /api/state/{member}` (dashboard load) | 4158 (3308–4391) | 467 (428–525) | |
| `GET /api/grocery/providers` | 1944 (1850–15240) | 332 (306–489) | |
| `DELETE /api/grocery/cart/items/{missing}` | 1028 (1007–2241) | 332 (311–385) | |

Notes:
- A, 6 Nov 2026: one `/grocery/providers` call took 15.2 s (a cold path), the other four 1.8–2.0 s.
- B, 6 Nov 2026: `x-vercel-id` reads `bom1::hnd1`. The first `/grocery/providers` batch failed once with a browser "Failed to fetch"; the rerun is shown.
