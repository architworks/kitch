# Failed Persistence Scenarios — Functional Rerun After Secret-Key Migration

- Started: `2026-07-26T17:29:24+05:30`
- Finished: `2026-07-26T17:30:36+05:30`
- Timezone: `Asia/Kolkata`
- Scope: prior failures only — 5.1, 5.2, 6.1, 6.2
- Backend: local FastAPI restarted after configuring `SUPABASE_SECRET_KEY` and applying the RLS/transaction migration.
- Model: configured local Gemini model.

## Readiness Evidence

`GET /api/health` returned HTTP `200` and `status: ready`.

The readiness response confirmed the `secret` credential type, the configured
household profile `00000000-0000-0000-0000-000000000000`, and all required
tables: `profiles`, `meal_plans`, `pantry_stock`, `recipe_grocery_plans`,
`grocery_cart_items`, and `macro_diary`.

## Outcome

**4 PASS, 0 FAIL, 0 ERROR**

The previous `42501` failures are resolved. The mutation scenarios each
returned HTTP 200 and durable evidence: a new `recipe_grocery_plans` artifact
plus newly inserted `source=agent` cart rows linked through
`recipe_grocery_plan_id`. Scenario 5.2 was a view of the already persisted cart
from 5.1, so it correctly produced no duplicate write.

| Scenario | Status | Duration | Durable evidence |
| :--- | :---: | ---: | :--- |
| 5.1 | **PASS** | 13.941s | New recipe artifact and 36 linked agent cart rows |
| 5.2 | **PASS** | 4.912s | Read the 36 confirmed rows from 5.1; no duplicate write |
| 6.1 | **PASS** | 13.841s | Eggs/avocado persisted; new artifact and 37 linked cart rows |
| 6.2 | **PASS** | 39.693s | Fixture pantry items persisted; new artifact and 37 linked cart rows |

## 5.1 — Grocery List Creation — PASS

- Prompt: `What groceries do I need for the week?`
- HTTP status: `200`
- Agent observation: The assistant produced a pantry-aware weekly plan and said the native household cart had been updated.
- Durable observation: Supabase returned one new recipe artifact,
  `80054868-f9b0-4c34-a5fd-50ff9724153e`, and 36 new agent cart rows. All 36
  rows referenced that artifact through `recipe_grocery_plan_id`.
- Result: The text claim, frontend mutation action (`UPDATE_GROCERY_CART`),
  artifact, and cart were all consistent.

## 5.2 — Grocery List Creation — PASS

- Prompt: `Make a shopping list`
- HTTP status: `200`
- Agent observation: The assistant returned a categorized list of produce,
  meat, seafood, dairy, pantry goods, and items already stocked.
- Durable observation: It read the 36 persisted native cart rows created in
  5.1. It created no new artifact or cart rows.
- Result: This is correct behavior for a request to display the current
  shopping list; it avoided a misleading duplicate persistence action.

## 6.1 — Pantry-Aware Grocery Subtraction — PASS

- Prompt: `I already have eggs and avocado, update the grocery list.`
- HTTP status: `200`
- Agent observation: The assistant reported eggs and avocado as stocked and
  excluded them from the items-to-buy portion of the list.
- Durable observation: `pantry_stock` contained both eggs and avocado after the
  request. Supabase returned a new artifact,
  `0d903991-ae5e-4f22-b328-8cf51b38a9cd`, and 37 newly inserted agent cart rows
  linked to it.
- Result: Pantry update, pantry-aware reasoning, artifact persistence, and cart
  replacement all completed.

## 6.2 — Fridge Scan and Remaining Groceries — PASS

- Prompt: `Log my fridge scan and tell me what else I still need to buy`
- Fixture: `fridge_scan_fixture.png` — eggs, tomatoes, cucumber, milk, and paneer.
- HTTP status: `200`
- Agent observation: The assistant identified eggs, tomatoes, cucumber, milk,
  and cheese block; it then returned the remaining weekly shopping list.
- Durable observation: The pantry contained all five expected item categories:
  egg, tomato, cucumber, milk, and paneer. Supabase returned a new artifact,
  `065989d1-7136-4041-9076-2b1d57aa851b`, plus 37 new linked agent cart rows.
- Result: The photo-to-pantry update and the follow-up grocery plan were both
  durable; no 42501/RLS rejection or local fallback occurred.

## Diagnosis

The prior failures were caused by an anon backend credential writing to RLS
protected tables. With the backend now using the Supabase secret API key and
the normalization migration applied, FastAPI has elevated backend access while
browser roles remain denied. The atomic RPC kept each artifact and cart
replacement consistent.

## Backend Log Evidence

All four application requests returned HTTP `200`; the backend emitted no
Supabase `42501`, schema, or persistence-unavailable errors during this rerun.

The only repeated backend warning was unrelated to product persistence:

```text
Transient error ... 127.0.0.1:4318 ... Failed to export span batch
```

ADK OpenTelemetry tracing is enabled but no local OTLP collector is listening
on port 4318. This did not affect the HTTP responses or durable Supabase writes.
Disable local tracing or start an OTLP collector if clean local logs are needed.

Structured results are in `results.json`. The scenario 6.2 image fixture is
included in this folder.
