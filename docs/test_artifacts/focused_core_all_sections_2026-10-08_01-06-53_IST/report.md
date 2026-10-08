# Focused Core Functional Test — All Sections

## Overall Outcome

- Run: 2026-10-08 01:06:53 IST
- Environment: local Next.js/FastAPI connected to Supabase, Vertex AI, Vertex Memory Bank, and the authorized Swiggy Instamart MCP account
- Model: `gemini-3.5-flash-lite`
- PASS: 12
- FAIL: 0
- PARTIAL: 0
- INCONCLUSIVE: 0
- BLOCKED: 0
- Provider safety: synchronized a two-item Instamart preview; did not place an order
- Image fixture: `static/food_bowl.png`
- Raw evidence: `results.json`

| Scenario | Status | What worked | What was unsuccessful |
| --- | --- | --- | --- |
| 1.1 Balanced Weekly Meal Plan | PASS | Saved Oct 12–18 with 7 dates and 21 meal slots. | Nothing after the fix. |
| 2.1 Swap Thursday Dinner to Vegan | PASS | Changed only Oct 15 dinner; other dates and meal slots stayed intact. | Nothing. |
| 3.1 View Recipe Details | PASS | Saved and rendered a complete Masala Dosa recipe without adding grocery rows. | Initial run exposed unsaved/metadata-only recipe handling; fixed and retested. |
| 4.1 Roti and Dal Lunch | PASS | Logged lunch for Oct 8 with persisted calories and macros. | Nothing. |
| 5.1 Salad Plate Photo | PASS | Classified the fixture as a meal and persisted Mixed Green Salad nutrition. | Nothing. |
| 6.1 Weekly Groceries | PASS | Generated a meal-plan-derived artifact and durable native cart. | Nothing. |
| 7.1 Already Have Eggs and Avocado | PASS | Persisted pantry stock and explicitly reconciled the grocery cart. | Initial run misrouted pantry subtraction as manual cart deletion; fixed and retested. |
| 8.2 Provider Cart Synchronization | PASS | Matched two selected native rows into a fresh Instamart review. | Nothing; no order was placed. |
| 9.1 Bread Brand Preference | PASS | Saved Baker's Dozen whole-wheat preference and recalled it after restart. | Nothing. |
| 10.1 Dinner Tonight | PASS | Resolved Oct 8 in Asia/Kolkata and returned the stored dinner exactly. | Initial response added irrelevant bread advice; fixed and retested. |
| 11.1 Empty Local First Run | PASS | Fresh SQLite reported uninitialized, created two members, and contained no activity data. | Nothing. |
| 12.3 Member Rename Preserves Identity | PASS | Renamed Naman, observed it through state, and restored the name with the same UUID. | Nothing. |

## Scenario Evidence

### 1.1 — Balanced Weekly Meal Plan

- Prompt/action: `Plan my meals for next week. Keep it balanced and diverse.`
- Observed state: Oct 12–18 contained exactly seven durable dates and 21 meal slots.
- Status: PASS.

### 2.1 — Swap Thursday Dinner to Vegan

- Prompt/action: swap Thursday dinner to a vegan meal.
- Observed state: Oct 15 dinner became `Vegan Tofu Stir-Fry with Mixed Vegetables and Jasmine Rice`; breakfast, lunch, and the other six dates were unchanged.
- Status: PASS.

### 3.1 — View Recipe Details for the Next Planned Meal

- Prompt/action: `Show me the recipe for Masala Dosa planned on 2026-10-08` through the Home-page recipe action.
- Observed state: complete saved recipe with 12 ingredients and six steps; Recipes UI rendered it; recipe grocery count remained zero.
- Status: PASS after fixing explicit recipe routing and the state API's full-artifact contract.

### 4.1 — Roti and Dal Lunch

- Prompt/action: `I ate 2 rotis and dal for lunch today`.
- Observed state: Oct 8 lunch persisted as 320 kcal, 12 g protein, 50 g carbs, 6 g fat, and 8 g fiber.
- Status: PASS.

### 5.1 — Salad Plate Photo

- Prompt/action: uploaded `static/food_bowl.png` with `Log this salad plate photo`.
- Observed state: classified as meal, identified `Mixed Green Salad`, and persisted 150 kcal, 3 g protein, 10 g carbs, 11 g fat, and 3 g fiber.
- Status: PASS.

### 6.1 — Weekly Groceries

- Prompt/action: `What groceries do I need for the week?`
- Observed state: returned `UPDATE_GROCERY_CART`; saved a grocery artifact with 14 generated rows. The complete cart contained 16 rows including two pre-existing manual rows.
- Status: PASS.

### 7.1 — Already Have Eggs and Avocado

- Prompt/action: `I already have eggs and avocado, update the grocery list.`
- Observed state: Eggs (12 pieces) and Avocado (2 pieces) remained durable in pantry; cart reconciliation completed with `UPDATE_GROCERY_CART` and no nonexistent cart-row deletion.
- Status: PASS after fixing stocked-item routing and adding a recoverable direct-cart guard.

### 8.2 — Provider Cart Synchronization and Reconciliation

- Prompt/action: synchronized two selected native rows (`Lemons` and `Baker's Dozen Whole Wheat Bread`) to the authorized Instamart account.
- Observed state: two native rows, two mapped rows, and two confirmed matches were saved in a fresh `ready` review; the review remained order-eligible.
- Status: PASS. No payment was selected and no order was placed.

### 9.1 — Bread Brand Preference

- Prompt/action: `For bread, always get Baker's Dozen whole wheat`; restart backend; ask `Which bread should I buy?`
- Observed response after restart: recalled `The Baker's Dozen whole wheat`.
- Status: PASS.

### 10.1 — Dinner Tonight

- Prompt/action: `What's for dinner tonight?`
- Expected stored row: Oct 8 `Mix Veg Curry with Roti` in `Asia/Kolkata`.
- Observed response: `For dinner tonight, you have Mix Veg Curry with Roti scheduled!`
- Browser check: same response visible in the chat UI; no browser console errors.
- Status: PASS after preventing factual schedule reads from expanding into unrelated recommendations.

### 11.1 — Empty Local First Run

- Prompt/action: start an isolated SQLite/in-memory instance, inspect bootstrap, then create `Local Alpha` and `Local Beta` in `Asia/Kolkata`.
- Observed state: initial `initialized=false`; after bootstrap household size was two with zero pantry, cart, recipe, meal-plan, and nutrition records.
- Status: PASS.

### 12.3 — Member Rename Preserves Identity and History

- Prompt/action: rename `Naman` to `Naman QA`, reload state, then restore `Naman`.
- Observed state: renamed value appeared through the API and the profile UUID stayed `22222222-2222-2222-2222-222222222222` throughout.
- Status: PASS.

## Automated Regression Checks

- Backend: 171 tests passed.
- Frontend: ESLint passed.
- Frontend: production build passed.
- Final browser smoke: authenticated Household page loaded, persisted planner/pantry/cart state rendered, chat returned the exact saved dinner, and console errors were empty.
