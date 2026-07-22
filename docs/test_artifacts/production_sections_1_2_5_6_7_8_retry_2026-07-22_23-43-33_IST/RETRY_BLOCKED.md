# Production Test Subset Retry Blocked

- Retry folder timestamp: `2026-07-22_23-43-33_IST`
- Scope requested: `docs/production_test_results.md` sections 1, 2, 5, 6, 7, and 8
- Backend target: `http://127.0.0.1:8000`
- Runtime model: Google ADK native Gemini, `gemini-3.6-flash`
- Historical test plan file modified: no

## What happened

Supabase DNS and an authenticated Supabase read both succeeded after the paused project was resumed.

The first retry run was completed and saved in:

`docs/test_artifacts/production_sections_1_2_5_6_7_8_2026-07-22_23-24-06_IST/`

That run produced:

- `report.md`
- `results.json`
- `fridge_scan_fixture.png`

However, the run hit Gemini quota after scenario 1.2. The generated report is therefore useful as an execution artifact, but not as a clean product-regression signal for the full requested scenario set.

## Why a clean retry was not run

The runner was patched to pace Gemini requests and retry `429 RESOURCE_EXHAUSTED` responses. Before starting the throttled rerun, the backend restart logs showed the current Gemini key/model had exhausted the free-tier daily quota:

`Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash`

At that point, waiting between requests would not make the full test subset pass through the model today with the current key/model.

The restart logs also showed these Supabase schema gaps, which affect the grocery sections:

- missing table: `public.grocery_cart_items`
- missing table: `public.recipe_grocery_plans`

Those code paths fall back to process-local memory, so sections 5 and 6 cannot be treated as fully production-persistent until those tables exist or the code is updated to use existing production tables.

## Next valid retry conditions

A clean rerun needs:

- Gemini quota available for `gemini-3.6-flash`, or a paid/higher-quota Gemini key/model configured.
- Supabase tables present for grocery cart and recipe grocery plan persistence, or an intentional schema/code migration away from those tables.

