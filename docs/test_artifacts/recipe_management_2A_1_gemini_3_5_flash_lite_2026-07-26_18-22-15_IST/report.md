# Recipe Management Functional Test — Scenario 2A.1

- Started: `2026-07-26T18:22:15+05:30`
- Finished: `2026-07-26T18:43:16+05:30`
- Timezone: `Asia/Kolkata`
- Environment: local Next.js frontend and local FastAPI backend with Supabase persistence
- Model: `gemini-3.5-flash-lite`
- Scope: recipe-only generation, durable recipe artifact, cart isolation, and Recipes-tab visibility

## Overall Outcome

**Scenario 2A.1: PASS**

The live assistant and persistence checks passed. Kitch generated the exact
requested recipe, saved a complete recipe artifact, returned the confirmed
`UPDATE_RECIPE_GROCERY` action, and left all 37 existing grocery-cart rows
unchanged.

The Chrome completion run also passed. The **View details** button seeded the
exact expected prompt, the chat rendered the full recipe response, and the
Recipes tab visibly rendered the saved recipe. After a hard refresh, the same
recipe remained visible and the Groceries tab still contained 37 rows.

## Readiness Evidence

`GET /api/health` returned HTTP `200` with:

- `status: ready`
- `engine: google-adk`
- `memory: ephemeral-process-local`
- `credential_type: secret`
- Required Supabase tables confirmed: `profiles`, `meal_plans`,
  `pantry_stock`, `recipe_grocery_plans`, `grocery_cart_items`, and
  `macro_diary`
- Household profile: `00000000-0000-0000-0000-000000000000`

The local frontend at `http://127.0.0.1:3000` also returned HTTP `200`.

## Scenario 2A.1 — View Recipe Details for the Next Planned Meal — PASS

### Prompt and Preconditions

- Active user: `Archit`
- Household size: `3`
- Dietary profile: `balanced`
- Meal shown as Monday dinner:
  `Grilled Paneer Steak with Herb Butter and Steamed Broccoli`
- Exact prompt seeded by the frontend's **View details** flow:

```text
Show me the recipe for Grilled Paneer Steak with Herb Butter and Steamed Broccoli
```

### Expected Behavior

- Generate a usable recipe for the exact planned meal.
- Include the title, servings, cooking time, ingredient quantities/units, and
  ordered cooking steps.
- Persist a `recipe_grocery_plans` artifact.
- Return a recipe-specific update action only after persistence succeeds.
- Set `updates_cart=false`, create no recipe-linked cart rows, and leave the
  existing native grocery cart unchanged.
- Render the saved recipe in the frontend Recipes tab and retain it after a
  browser refresh.

### Observed Assistant Response

- HTTP status: `200`
- Confirmed action: `UPDATE_RECIPE_GROCERY`
- Returned title:
  `Grilled Paneer Steak with Herb Butter and Steamed Broccoli`
- Returned scope: `Monday Dinner`
- Returned servings: `3`
- Returned cook time: `20 mins`
- Returned seven ingredient lines, including:
  - `1 block Paneer`
  - `3 tbsp Butter`
  - `1 head Broccoli`
  - `2 tbsp Mixed fresh herbs`
  - `1 tsp Minced garlic`
- Returned five ordered steps:
  1. Make the herb butter.
  2. Prepare and season the paneer steaks.
  3. Grill the paneer.
  4. Steam the broccoli.
  5. Top with herb butter and serve.
- The assistant recognized pantry coverage for paneer and broccoli.
- The response did not say groceries had been added or that the cart had been
  updated.

### Durable Recipe Observation

`GET /api/recipe-grocery/plans/latest` returned the newly created artifact:

- Artifact ID: `ae713a87-7ad2-48fe-b7fd-30edd6f00743`
- Request: exact submitted prompt
- Recipe-card count: `1`
- Ingredient count: `6` structured top-level ingredients
- Recipe title: exact requested meal title
- Recipe scope: `Monday Dinner`
- Servings: `3`
- Cook time: `20 mins`
- Cooking steps: `5`
- `updatesCart: false`
- `cartItemCount: 0`
- Created at: `2026-07-26T12:52:25.481202+00:00`

The artifact includes the exact title, description, ingredient quantities,
steps, pantry considerations, and notes needed by the Recipes page.

### Cart-Isolation Observation

- Cart before request: `37` rows
- Cart after request: `37` rows
- Existing cart artifact:
  `065989d1-7136-4041-9076-2b1d57aa851b`
- New recipe artifact:
  `ae713a87-7ad2-48fe-b7fd-30edd6f00743`
- Rows linked to the new recipe artifact: `0`
- Existing row IDs, quantities, checked state, pantry flags, and artifact links
  remained unchanged.
- The API action was `UPDATE_RECIPE_GROCERY`, not
  `UPDATE_GROCERY_CART`.

Result: the recipe-only request respected the boundary between learning how to
cook a meal and asking Kitch to buy its ingredients.

### Frontend Browser Observation

- Local frontend availability: HTTP `200`
- Browser: Chrome through the Chrome DevTools MCP server
- Home card: displayed the expected Monday dinner and an enabled
  **View details →** button.
- Seeded prompt check: clicking **View details →** populated the chat textbox
  with the exact expected prompt.
- Submission check: submitting through the frontend rendered the complete
  recipe response in the chat, including title, scope, servings, cook time,
  seven ingredient lines, and five cooking steps.
- Recipes-tab visual check: **PASS**
  - Exact recipe title displayed.
  - Description, `20 mins`, and `Serves 3` displayed.
  - Recipe view displayed five expandable cooking steps.
  - Ingredients view displayed all seven user-facing ingredient lines.
  - Recipe sidebar displayed `Grocery List 0`.
- Refresh-and-recheck visual persistence: **PASS**
  - Performed a hard browser reload.
  - Reopened **Recipes**.
  - The same title, description, cook time, servings, steps, and ingredients
    were still visible.
- Groceries-tab isolation check after refresh: **PASS**
  - `My List 37`
  - `37 items`
  - `26 selected for Zepto`
  - No recipe-only rows were added.
- Chrome network evidence:
  - `POST /api/chat`: HTTP `200`
  - All `/api/state/Archit` reloads: HTTP `200`
  - All `/api/recipe-grocery/plans/latest` reloads: HTTP `200`
- Chrome console evidence: no application errors or warnings. Chrome reported
  one accessibility issue that 156 form fields lack an `id` or `name`
  attribute; this did not affect the scenario.

### Status Rationale

**PASS** because the exact Home-card flow, recipe response, durable artifact,
Recipes-tab rendering, Ingredients interaction, hard-refresh persistence, and
cart isolation all matched the functional criteria.

## Findings

- Recipe-only routing and persistence are working correctly for the exact
  **View details** prompt.
- The recipe artifact is rich enough for the current Recipes UI.
- The cart-isolation contract worked correctly.
- No database, authorization, schema, or model error occurred.
- The browser workflow remained correct after a hard reload.
- Separate cleanup opportunity: add `id` or `name` attributes to interactive
  grocery form fields to resolve Chrome's accessibility issue.

Structured evidence is recorded in `results.json`.
