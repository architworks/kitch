# Kitch Functional Testing Blueprint

This document converts the historical production verification scenarios from
`docs/test_artifacts/production_test_results.md` into a reusable functional
test template.
It is intended for manual, assisted, or automated functional testing of the
full Kitch product experience.

The goal is to validate user-visible behavior and persisted product state, not
implementation details. Testers should interact with the app as a household
user would: asking the assistant for meal plans, logging food, uploading
images, updating pantry state, requesting grocery lists, and checking whether
the app remembers preferences.

Structured product state is durable only after FastAPI receives a confirmed
Supabase result. Selected natural-language household context is durable only
after the specialist receives a successful Vertex AI Memory Bank tool result.
Chat sessions remain process-local and are not required for cross-restart
preference recall.

## Artifact Reporting Standard

Every test run should produce a dated artifact that is detailed enough for
debugging. Do not record only duration and status.

The report must be easy to triage before it is detailed:

- Put the overall `PASS`, `FAIL`, `PARTIAL`, `INCONCLUSIVE`, and `BLOCKED`
  counts at the top.
- Immediately follow them with a summary table containing **Scenario**,
  **Status**, **What worked**, and **What was unsuccessful**.
- For every non-pass scenario, start its detailed section with a bold
  `Unsuccessful:` one-sentence explanation. A reader must not need to scan the
  evidence to understand why the scenario did not pass.
- Put diagnostic evidence after the decision summary. Do not lead with setup,
  implementation detail, or long narrative paragraphs.
- Keep the human-readable report concise. Put exhaustive machine evidence in
  `results.json`; do not duplicate the full structured payload in prose.

For each scenario, record:

- Scenario ID and title.
- Exact user prompt or user action.
- Any fixture used, such as the food image or fridge image.
- Assistant response summary, including important quoted phrases when useful.
- Functional observations: what changed in the meal plan, diary, pantry,
  grocery list, preferences, or delivery preview.
- Persistence observations: whether the expected state was still present after
  refresh or later query.
- Pass, fail, partial, inconclusive, or blocked status.
- Rationale for the status in plain language.
- Any environmental caveat, such as model outage, missing persistence table,
  provider unavailability, or image fixture mismatch.
- For a persistence failure, the HTTP status and safe backend error detail,
  confirmation that no success action/banner appeared, and confirmation that
  the last confirmed UI state was retained.

Recommended per-scenario result format:

```markdown
### Scenario X.Y - Short Name

- Prompt/action: ""
- Expected behavior:
- Observed assistant response:
- Observed state change:
- Persistence check:
- Status:
- Rationale:
- Notes:
```

## Test Run Setup

Before running the scenarios, prepare a consistent household test context.

- Use the same active household member throughout the run unless the scenario
  explicitly requires otherwise.
- Confirm `/api/health/live` responds immediately, then confirm
  `/api/health/ready` reports ready before starting. Readiness verifies the
  elevated backend credential, required tables/columns, and configured
  household profile while reporting provider and memory degradation separately.
- Confirm the app can read and write user profile, meal plan, pantry, food
  diary, grocery, and recipe-artifact state. Before preference scenarios,
  confirm readiness reports memory backend `vertex` and state `ready`.
- Use a stable local date and timezone in the artifact. Relative-date scenarios
  must record the actual calendar date used during the test.
- Use known image fixtures for image scenarios and link or copy them into the
  artifact folder.
- Do not place real delivery orders during functional verification unless a
  separate live-order approval test explicitly authorizes it.
- If a provider cart or grocery preview is used, treat it as a preview unless
  the product explicitly completes an approved cart sync.

### Head-Chef Capability Coverage

| Capability | Primary scenarios |
| --- | --- |
| Dated meal creation, editing, and removal | 1.1–1.8, 2.1–2.6, 10.1–10.6 |
| Recipe creation, revision, and deletion | 3.1–3.2 |
| Nutrition logging, correction, deletion, and daily clearing | 4.1–4.4, 5.1, 10.3 |
| Neutral image classification and routing | 5.1–5.3, 7.2, 7.4 |
| Pantry inspection and mutation through UI, chat, and images | 7.1–7.4 |
| Native-cart and provider-cart preparation | 6.1–6.3, 8.1–8.4 |
| Flexible household preference memory | 1.3, 8.2, 9.1–9.6 |
| Household settings and domain routing | 1.8, 4.4, 7.3, 8.2 |
| Destructive-action and order authority boundaries | 2.6, 4.4, 7.3, 8.4 |

## Meal-Plan Persistence Regression Context

The original production result document included a resolved database conflict
bug. Keep this as a regression concern during meal plan generation and edit
testing.

Functional risk to test:

- Creating a plan should replace only the requested calendar dates without
  duplicate-date errors.
- Editing one meal should not create a duplicate `(profile_id, plan_date)` row.
- Replanning a date range should leave exactly one plan entry per date.
- Repeated edits should preserve unrelated meals.

Functional pass criteria:

- The user sees a successful assistant response.
- The planner shows the requested real calendar dates.
- No duplicate dates appear.
- The edited or regenerated meal is visible after refresh or later query.

## Overall Functional Outcome Template

At the top of each run artifact, include:

- Run date and timezone.
- Environment, such as local, staging, or production.
- Model/provider used.
- Test sections included.
- Overall result count.
- Major caveats.
- Link to fixtures.
- Link to raw structured evidence, if available.

Example:

```markdown
## Overall Outcome

- PASS:
- FAIL:
- PARTIAL:
- INCONCLUSIVE:
- BLOCKED:

Major caveats:
```

## Section 1: Meal Plan Generation

These scenarios verify that the assistant can generate plans for exact dates
and ranges, while preserving complete Monday-Sunday planning when the user
explicitly requests next week.

### Scenario 1.1 - Balanced Weekly Meal Plan

- Prompt/action: "Plan my meals for next week. Keep it balanced and diverse."
- Expected behavior: The assistant creates a complete 7-day meal plan with
  breakfast, lunch, and dinner for every day.
- Observe: The response should describe a balanced and varied week, not a
  single-day plan or generic advice.
- Persistence check: Refresh or ask about the weekly plan and confirm all
  7 days and 21 meal slots are present.
- Pass criteria: Complete weekly plan is visible and persisted.
- Fail criteria: Missing days, missing meal slots, no saved plan, or only
  generic meal-planning advice.

### Scenario 1.2 - Indian Weekly Meal Plan Replacement

- Prompt/action: "Actually, I'm feeling like eating Indian food next week. Plan
  a completely new weekly meal plan focusing on delicious Indian dishes."
- Expected behavior: The assistant replaces the prior plan with a new Indian
  meal plan.
- Observe: The plan should contain recognizable Indian dishes such as dal,
  paneer, roti, dosa, poha, curry, biryani, rice, or similar dishes.
- Persistence check: Confirm the stored weekly plan changed from the prior
  balanced plan and still has 7 days and 21 meal slots.
- Pass criteria: A complete Indian-themed weekly plan replaces the previous
  plan.
- Fail criteria: The previous plan remains unchanged, only some meals change
  when the user asked for a new plan, or the saved plan is incomplete.

### Scenario 1.3 - Keto Weekly Meal Plan and Preference Change

- Prompt/action: "Change my preference to keto and make a full weekly keto meal
  plan for next week."
- Expected behavior: The assistant acknowledges or applies keto preference and
  creates a complete keto-oriented weekly plan.
- Observe: Meals should be plausibly keto: eggs, avocado, paneer, chicken,
  fish, tofu, salads, low-carb vegetables, nuts, chia, or similar items. Heavy
  carb staples should not dominate the plan.
- Persistence and recall check: Confirm the weekly plan remains after refresh
  and the keto statement is absent from profile columns. Restart the backend,
  request a later meal suggestion, and confirm persistent household memory
  still guides the response.
- Pass criteria: Complete keto plan is saved and later behavior respects keto.
- Fail criteria: Incomplete plan, non-keto plan, preference not remembered, or
  old cuisine plan remains.

### Scenario 1.4 - Plan Tomorrow Only

- Record before testing: Household timezone, today's ISO date, and tomorrow's
  ISO date.
- Prompt/action: "Plan breakfast, lunch, and dinner for tomorrow."
- Expected behavior: Exactly tomorrow's household-calendar date is planned.
  The assistant confirmation must name that date, and dates outside tomorrow
  must remain unchanged.
- UI check: After success, the planner opens the week containing tomorrow and
  selects tomorrow. The hero and selected day show the same next meal/date.
- Persistence check: Confirm one durable row exists for tomorrow with all three
  slots and no meal was projected onto the same weekday in another week.
- Pass criteria: Chat, database, planner, and hero agree on the exact date.
- Fail criteria: The meal appears next week, another weekday-equivalent date is
  changed, or the UI stays on an unrelated week.

### Scenario 1.5 - Plan the Remainder of This Week

- Prompt/action: Run midweek: "Plan meals for this week."
- Expected behavior: Kitch replaces today through the coming Sunday only.
- Persistence check: Confirm each requested date has breakfast, lunch, and
  dinner. Earlier dates in the week are unchanged, as are dates after Sunday.
- Pass criteria: The persisted range begins today and ends Sunday.
- Fail criteria: Past dates are rewritten, next week is used, or any requested
  date is missing.

### Scenario 1.6 - Plan an Exact Future Date

- Prompt/action: Choose a future ISO date and ask: "Plan my meals for
  <human-readable exact date>."
- Expected behavior: Only that date is created or replaced, and the response
  confirms the exact date.
- UI check: The planner navigates to that date's week and selects it.
- Pass criteria: Exactly one requested date changes and unrelated dates remain
  byte-for-byte equivalent in persisted meal names.
- Fail criteria: Kitch plans a full week, uses the wrong date, or edits a past
  date.

### Scenario 1.7 - Plan a Rolling Date Range

- Prompt/action: "Plan the next 3 days," then separately test "Plan the next 3
  days starting tomorrow."
- Expected behavior: The first request covers today plus two dates; the second
  covers tomorrow plus two dates. Each replacement is atomic.
- Persistence check: Confirm exact range boundaries and complete meal slots.
- Transaction check: Force one invalid row in a test environment and confirm no
  date in that operation is partially replaced.
- Pass criteria: Both phrases resolve to the documented exact ranges and
  failures roll back the complete range.
- Fail criteria: Off-by-one dates, week projection, or partial persistence.

### Scenario 1.8 - Keep Configuration, Goals, and Preferences in Their Domains

- Prompt/action: In separate chat turns, change the household size and timezone,
  change the active member's calorie or macro goal, and state a natural-language
  dietary preference. Then send an unrelated chat message from a browser whose
  locally displayed state has not yet refreshed.
- Expected behavior: Household size/timezone persist as factual profile data;
  nutrition goals persist in nutrition state; dietary preference is stored only
  in agent memory. An ordinary chat message must not rewrite any of them.
- Isolation check: Provider authentication and the checkout UI's selected
  ordering app remain unchanged.
- Persistence check: Refresh the page and confirm factual configuration,
  nutrition goals, and provider workflow state remain. Restart the backend and
  confirm the dietary preference remains usable through Memory Bank even
  though the chat session itself is gone.
- Pass criteria: Each value affects its owning domain, no semantic preference is
  written to `profiles`, and no unrelated state changes.
- Fail criteria: A preference appears in profile storage, stale UI state
  overwrites confirmed data, the preference is lost after restart, or a setting
  change alters provider authentication/selection.

## Section 2: Plan Modification

These scenarios verify that targeted edits affect only the requested meals and
preserve the rest of the weekly schedule.

### Scenario 2.1 - Swap Thursday Dinner to Vegan

- Prerequisite: Open a planner week whose Thursday is not in the past and has a
  dinner. Record the exact selected Thursday date.
- Prompt/action: "Actually, swap Thursday dinner with something vegan."
- Expected behavior: Only Thursday dinner changes to a vegan meal.
- Observe: The assistant should identify or update Thursday dinner and not
  regenerate the whole week.
- Persistence check: Compare the plan before and after the request. All other
  days and meal slots should remain unchanged.
- Pass criteria: Exactly Thursday dinner changes, and the replacement is
  clearly vegan.
- Fail criteria: Multiple unrelated meals change, Thursday dinner does not
  change, or the plan becomes incomplete.

### Scenario 2.2 - Change Monday Breakfast to Chia Pudding

- Prerequisite: Open a planner week whose Monday is not in the past and has a
  breakfast. Record the exact selected Monday date.
- Prompt/action: "Change Monday breakfast to chia pudding"
- Expected behavior: Only Monday breakfast changes to chia pudding.
- Observe: The assistant should perform a narrow edit rather than suggesting a
  recipe without updating the plan.
- Persistence check: Confirm Monday breakfast is saved as chia pudding or a
  clear chia-pudding variant after refresh.
- Pass criteria: Exactly Monday breakfast changes and all other meals remain
  intact.
- Fail criteria: No saved change, unrelated meals change, or the assistant only
  gives advice.

### Scenario 2.3 - Replace Salmon Everywhere

- Prompt/action: "I don't like salmon, replace it wherever it appears in my
  weekly meal plan."
- Expected behavior: Every salmon occurrence is replaced with a non-salmon
  alternative.
- Observe: The assistant should search the active plan and update all matching
  meals, not just one.
- Persistence check: Inspect the saved weekly plan and confirm no meal names
  contain salmon.
- Pass criteria: All salmon meals are replaced, no non-salmon meals are
  unnecessarily changed, and the plan remains complete.
- Inconclusive condition: The prerequisite plan contains no salmon before the
  test begins.
- Fail criteria: Salmon remains, unrelated meals change, or the plan becomes
  incomplete.

### Scenario 2.4 - Same Weekday in Different Weeks Remains Independent

- Prerequisite: Store meals for two different Thursdays in adjacent weeks.
- Prompt/action: While the first Thursday's week is visible, select that date
  and ask to change its dinner.
- Expected behavior: The bare weekday is resolved from the visible planner
  context and only that exact Thursday changes.
- Persistence check: Compare both dated rows before and after.
- Pass criteria: The selected week's Thursday changes; the other Thursday and
  every unrelated slot remain unchanged.
- Fail criteria: Both Thursdays change or the wrong week is selected.

### Scenario 2.5 - Atomic Multi-Date Meal Edit

- Prompt/action: Ask for two specific future dated meal-slot changes in one
  message.
- Expected behavior: Both edits are applied together while every unrelated
  meal and date remains unchanged.
- Transaction check: Force one edit to fail in a test environment and confirm
  neither edit persists.
- Pass criteria: All requested edits succeed together or all roll back.
- Fail criteria: Partial persistence or unrelated changes.

### Scenario 2.6 - Remove Future Meal Slots, Dates, and Ranges

- Prerequisite: Save distinct meals across several future dates and record the
  plan before testing.
- Prompt/action: Remove one future meal slot, then one explicitly named future
  date, and finally request removal across a future date range.
- Expected behavior: Only the requested scope is removed. Kitch states the
  exact affected dates and slots, and empty dated rows disappear instead of
  rendering blank meal placeholders.
- Broad-removal check: For a range or otherwise broad request, verify the user
  understands the scope before it is applied. Treat confirmation as a product
  safeguard rather than requiring one rigid dialog or interaction pattern.
- Boundary check: Ask Kitch to remove or change a past meal. It must explain
  that past plans cannot be modified and leave persisted state unchanged.
- Persistence check: Refresh and compare all unrelated dates and slots with the
  recorded baseline.
- Pass criteria: The intended future scope is removed, its exact dates are
  communicated, and unrelated or past state remains unchanged.
- Fail criteria: The wrong date or slot is removed, broad deletion is
  surprising or unclear, past state changes, or unrelated plans are lost.

## Section 3: Recipe Management

These scenarios verify that users can request full cooking details for a
planned meal without implicitly asking Kitch to buy anything. They cover the
Home-page **View details** flow, which seeds a `Show me the recipe for ...`
prompt, and the persisted recipe rendered in the Recipes page.

### Scenario 3.1 - View Recipe Details for the Next Planned Meal

- Prerequisite: The active meal plan has a named next meal on the Home page.
  Record that meal name before beginning.
- Prompt/action: Click **View details** for the next meal and confirm the chat
  input is seeded with `Show me the recipe for <next meal>`. Submit that exact
  prompt.
- Expected behavior: The assistant generates a complete recipe for the exact
  named meal. The response should provide usable cooking details rather than
  only describing the dish or changing the meal plan.
- Recipe-content check: Confirm the saved recipe contains the exact or clearly
  equivalent meal title, servings, ingredients with quantities or units,
  ordered cooking instructions, and cooking time where appropriate.
- Recipe-management check: Open the **Recipes** tab and confirm it renders the
  generated recipe title, ingredients, and cooking steps. Exercise the Recipe
  and Ingredients views to confirm both parts of the artifact are usable.
- Cart-isolation check: Record the native grocery cart before and after the
  request. A recipe-only request must not add, remove, or replace cart rows,
  must not claim that groceries were added, and must not show an
  `UPDATE_GROCERY_CART` success action.
- Persistence check: Refresh the browser, return to the **Recipes** tab, and
  confirm the same recipe remains visible. Confirm a durable
  `recipe_grocery_plans` artifact exists with `updates_cart=false` and no
  recipe-linked cart rows.
- Pass criteria: The exact requested recipe is generated, saved, visible in the
  Recipes tab after refresh, and the grocery cart remains unchanged.
- Fail criteria: The assistant returns only a meal summary, generates the wrong
  recipe, omits usable ingredients or instructions, fails to save the recipe,
  loses it after refresh, or changes the grocery cart.
- Persistence-failure criteria: A storage failure must return HTTP 503 and the
  frontend must preserve the last confirmed recipe and cart state without
  showing a success banner.

### Scenario 3.2 - Revise and Delete a Saved Recipe

- Prerequisite: Save two recipe artifacts. Let the first populate linked
  recipe-generated grocery rows, and add a separate manual native-cart row.
- Prompt/action: Ask Kitch to revise the first recipe's ingredients and steps,
  including an ingredient change that affects its grocery requirements. Then
  explicitly ask to delete that recipe.
- Expected behavior: The revision updates the existing recipe rather than
  creating a duplicate. Only grocery rows belonging to that recipe change.
- Isolation check: The manual cart row, the second recipe, and its linked rows
  remain unchanged. If purchase intent changes, any outdated provider review
  is cleared before checkout can continue.
- Persistence check: Refresh after revision and deletion. Confirm stable recipe
  identity during revision and complete removal after deletion.
- Failure check: Simulate a persistence failure and confirm a recipe change is
  not left partially applied to either the recipe or its grocery rows.
- Pass criteria: Revision and deletion affect only the intended recipe and its
  linked grocery state.
- Fail criteria: A duplicate recipe is created, unrelated or manual rows are
  replaced, linked rows become orphaned, or only part of a revision persists.

## Section 4: Macro Logging via Text Message

These scenarios verify that plain text food messages are converted into diary
entries with reasonable calorie and macro estimates.

### Scenario 4.1 - Roti and Dal Lunch

- Prompt/action: "I ate 2 rotis and dal for lunch today"
- Expected behavior: The assistant logs lunch for today with rotis and dal.
- Observe: The response should mention a logged meal and reasonable nutrition
  estimates.
- Persistence check: Confirm today's food diary includes the roti and dal meal.
- Pass criteria: Diary entry exists with plausible calories, protein, carbs,
  and fat.
- Fail criteria: No diary entry, wrong date, wrong meal, or wildly implausible
  nutrition.

### Scenario 4.2 - Smoothie Ingredients

- Prompt/action: "Had a smoothie - banana, peanut butter, oats, milk"
- Expected behavior: The assistant logs a smoothie based on the listed
  ingredients.
- Observe: The response should include a calorie estimate that reflects banana,
  peanut butter, oats, and milk.
- Persistence check: Confirm today's diary includes the smoothie.
- Pass criteria: Smoothie is saved with plausible nutrition.
- Fail criteria: Missing diary entry, missing major ingredients, or implausible
  estimate.

### Scenario 4.3 - Black Coffee

- Prompt/action: "Just had a black coffee, nothing else"
- Expected behavior: The assistant logs black coffee as a very low-calorie
  item.
- Observe: The response should not inflate calories by assuming milk, sugar, or
  snacks.
- Persistence check: Confirm today's diary includes black coffee.
- Pass criteria: Black coffee is saved with near-zero or low calories.
- Fail criteria: No entry, wrong food item, or added ingredients the user did
  not mention.

### Scenario 4.4 - Correct, Delete, and Clear Nutrition Safely

- Prompt/action: Correct one named diary entry, delete one explicitly identified
  entry, then request clearing today's diary.
- Expected behavior: Correction updates the same row; single deletion executes
  directly; clearing the day shows an exact-impact confirmation first.
- Isolation check: Another household member's diary remains unchanged.
- Persistence check: Refresh after each operation and confirm the corrected
  entry, daily totals, and other household member's diary remain consistent.
- Pass criteria: Correction does not create a duplicate, deletion affects only
  the intended entry, clearing happens only after the user accepts its stated
  impact, and cancellation changes nothing.
- Fail criteria: The wrong entry or person changes, totals disagree with the
  diary, or a cancelled clear still removes data.

### Scenario 4.5 - Dated Nutrition Dashboard and Meal Grouping

- Prompt/action: Log one item with an explicit meal such as "I had oats for
  breakfast," then log another item without naming a meal. Open Nutrition,
  navigate across the visible week, edit one portion, and update one daily goal.
- Expected behavior: Explicit meal context wins. The entry without meal context
  is grouped from the request receipt time in the household timezone. Both
  appear on the correct date, and the selected-day totals and weekly trend use
  the same persisted entries.
- UI check: The page shows the calorie/macro summary, seven-day trend,
  Breakfast/Lunch/Snack/Dinner groups, entry edit/delete controls, and editable
  daily goals. Empty meal groups remain concise.
- Persistence check: Reload and confirm the entry correction, dated meal
  groups, trend totals, and updated goal still agree with the database.
- Pass criteria: Dated navigation, grouping, manual correction, goals, and
  derived totals remain consistent after reload and member switching.
- Fail criteria: Browser time changes the saved date, explicit meal context is
  ignored, totals drift from entries, another member changes, or reload loses
  the update.

## Section 5: Macro Logging via Image

These scenarios verify that Camera and Gallery share one non-mutating classifier
before the image is routed to Nutrition Tracker or Recipe/Grocery Planner.

### Scenario 5.1 - Salad Plate Photo

- Prompt/action: Upload a salad plate image with the prompt "Log this salad
  plate photo".
- Fixture: Use a clear image of a salad plate.
- Expected behavior: The assistant identifies the image as a salad or salad
  plate and logs it as a meal or snack.
- Observe: The response should describe the recognized food and provide a
  reasonable nutrition estimate.
- Persistence check: Confirm today's diary contains the image-derived salad
  entry.
- Pass criteria: Food is recognized, logged, and persisted with plausible
  nutrition.
- Fail criteria: Image ignored, food not logged, wrong food recognized, or no
  persisted diary entry.

### Scenario 5.2 - Fridge Scan Updates Pantry

- Prompt/action: Upload a fridge image with the prompt "Update my pantry with
  this fridge scan".
- Fixture: Use a clear fridge image with visible items such as eggs, milk,
  vegetables, paneer, or similar items.
- Expected behavior: The assistant identifies stocked fridge items and updates
  pantry state.
- Observe: The response should list recognized items and indicate pantry update
  behavior.
- Persistence check: Confirm recognized fridge items appear in pantry or stock
  state after refresh.
- Pass criteria: At least the clearly visible items are recognized and
  persisted.
- Partial criteria: The image is understood and items are named, but persistence
  is incomplete.
- Fail criteria: Image ignored, no pantry update, or clearly visible items are
  missed without explanation.

### Scenario 5.3 - Neutral Image Classification and Ambiguity

- Prompt/action: Submit the same meal and pantry fixtures once from Camera and
  once from Gallery, then submit an image whose purpose is genuinely ambiguous.
- Expected behavior: Acquisition method never changes routing. Meal goes to
  Nutrition Tracker; pantry goes to Recipe/Grocery Planner. Ambiguous returns
  exactly that state, persists nothing, retains the file, and offers **Treat as
  meal** and **Treat as pantry**.
- Pass criteria: No confidence threshold is shown, no mutation occurs before
  classification is resolved, and an override uses the retained file once.

## Section 6: Grocery List Creation

These scenarios verify that the assistant can turn the active meal plan into a
usable grocery list.

### Scenario 6.1 - Weekly Groceries

- Prompt/action: "What groceries do I need for the week?"
- Expected behavior: The assistant generates groceries for the active weekly
  meal plan.
- Observe: The response should group or list ingredients needed for the week's
  meals and should not be generic.
- Persistence check: Confirm a grocery list, cart, or recipe-grocery artifact is
  available after the response.
- Pass criteria: Grocery list is generated from the current meal plan and is
  saved or available for later review.
- Fail criteria: No grocery list, generic advice, missing persistence, or list
  unrelated to current meals.

### Scenario 6.2 - Shopping List

- Prompt/action: "Make a shopping list"
- Expected behavior: The assistant creates a usable shopping checklist from the
  active plan and pantry context.
- Observe: The response should be practical: item names, quantities where
  available, categories, or checklist format.
- Persistence check: Confirm the grocery list can be reviewed later.
- Pass criteria: A coherent shopping list is generated and persisted.
- Fail criteria: No list, no persistence, or the list ignores the active meal
  plan.

### Scenario 6.3 - Groceries for an Exact Date Range

- Prerequisite: Persist distinct meals in the current and following week.
- Prompt/action: Ask for groceries for one exact date, then for a bounded date
  range.
- Expected behavior: Ingredients are derived only from meals within the named
  dates, with pantry stock subtracted as usual.
- Persistence check: Confirm the recipe-grocery artifact records the intended
  dated meal context and the native cart does not include ingredients unique
  to dates outside the request.
- Pass criteria: The grocery result respects exact range boundaries.
- Fail criteria: Kitch silently uses the visible or next full week instead.

## Section 7: Pantry-Aware Grocery Subtraction

These scenarios verify that the assistant updates pantry state and avoids
recommending items already stocked.

### Scenario 7.1 - Already Have Eggs and Avocado

- Prompt/action: "I already have eggs and avocado, update the grocery list."
- Expected behavior: The assistant adds eggs and avocado to pantry/stock state
  and updates the grocery list accordingly.
- Observe: The response should acknowledge eggs and avocado as already stocked
  and remove, reduce, or mark them as already available in the shopping list.
- Persistence check: Confirm eggs and avocado remain in pantry state after
  refresh or later query.
- Pass criteria: Pantry state is updated and grocery recommendations account
  for stocked eggs and avocado.
- Fail criteria: Pantry not updated, grocery list still asks the user to buy
  those items without qualification, or state is lost.

### Scenario 7.2 - Fridge Scan and Remaining Groceries

- Prompt/action: Upload a fridge scan and ask "Log my fridge scan and tell me
  what else I still need to buy".
- Fixture: Use a clear fridge image with known visible items.
- Expected behavior: The assistant identifies fridge items, updates pantry
  state, and returns a remaining-to-buy list that accounts for those items.
- Observe: The response should separate stocked items from items still needed.
- Persistence check: Confirm fridge items are present in pantry state and the
  grocery list reflects them.
- Pass criteria: Image recognition, pantry update, and pantry-aware grocery
  subtraction all work together.
- Partial criteria: Image is interpreted but state or grocery subtraction is
  incomplete.
- Fail criteria: Image ignored, pantry not updated, or remaining grocery list
  ignores visible stocked items.

### Scenario 7.3 - Inspect, Edit, Remove, and Empty Pantry

- Prompt/action: Open the Pantry tab, inspect all rows and timestamps, add one
  item, set and decrement quantities, and remove one row. Repeat equivalent
  updates through chat, then choose **Mark pantry empty** and cancel once before
  confirming.
- Expected behavior: Every successful edit refreshes pantry without silently
  changing native purchase quantities. UI and chat operate on the same shared inventory. Single-row
  removal is direct. Emptying shows its impact and marks the pantry fully
  reviewed only after confirmation; partial edits do not claim a full review.
- Read-before-update check: Establish a known existing quantity, then ask Kitch
  to add, reduce, or otherwise update that item. The resulting total must
  reflect the previously stored row, demonstrating that the agent considered
  current pantry state rather than treating the request as an isolated value.
- Semantic interpretation check: Express compatible quantities in different
  natural forms across the existing row and the requested change. Judge the
  resulting inventory by whether its meaning and total are correct, not by the
  spelling, abbreviation, or display unit chosen by the agent.
- Concurrency check: Repeat a mutation with a stale revision and require HTTP
  409 with no partial pantry change.
- Pass criteria: The UI never shows only a count, cancellation changes nothing,
  chat and UI agree on the resulting inventory, and confirmed replacement
  survives refresh.
- Fail criteria: Kitch ignores existing stock, produces an incoherent total,
  changes the wrong row, loses confirmed state after refresh, or applies a
  cancelled replacement.

### Scenario 7.4 - Photo Semantics and Explicit Cart Reconciliation

- Prompt/action: Upload the same current-inventory pantry photo twice, then an
  explicitly described purchase photo.
- Expected behavior: Current inventory uses absolute `set` semantics and does
  not accumulate twice; purchase observations increase stock. The native cart
  remains unchanged until the tester explicitly chooses **Update cart from pantry**
  or asks Kitch to recalculate it.
- Functional reconciliation check: Include full and partial pantry coverage.
  Confirm the native cart communicates what is required, what the pantry
  covers, and what remains to buy in quantities a user can understand. Do not
  require a particular internal representation or unit notation.
- Separation check: After changing pantry state, confirm native purchase
  quantities and provider review remain untouched. Then explicitly reconcile
  and confirm fully covered items are excluded while partially covered items
  retain only what remains to buy.
- Provider check: Explicit reconciliation invalidates an outdated provider
  review only when the resulting purchase intent changes.
- Rollback check: Force explicit reconciliation failure and confirm the native
  cart and provider review remain unchanged; the already-confirmed pantry edit
  remains intact.
- Pass criteria: Repeated observations do not accumulate unintentionally,
  no implicit cart update occurs, explicit remaining purchase quantities are
  functionally correct, and failure does not leave partial cart changes.
- Fail criteria: The same observed stock is counted twice, purchase quantities
  change without an explicit command, ignore pantry coverage after explicit
  reconciliation, or a failed reconciliation partially persists.

## Section 8: Ordering App Integration

These four scenarios apply the same functional contract to Zepto and Swiggy
Instamart. Use fixtures or Swiggy staging for order-path tests. Never place an
automated or browser-test order against production.

### Scenario 8.1 - Provider Selection, Connection, and Address

- Prerequisite: Apply the multi-provider migration and configure at least one
  test provider. Use an authorized Swiggy local/staging account for Instamart.
- Prompt/action: Open **Groceries**, inspect provider cards, connect Instamart,
  switch between Zepto and Instamart, confirm saved addresses load automatically,
  and choose one when needed.
- Provider check: Cards, environment, capabilities, connection state, and API
  actions must come from the backend registry. Blinkit remains visible,
  disabled, labelled **Coming soon**, and issues no request.
- Preference check: The last selected provider persists for the household. With
  no preference, connected Zepto wins, then connected Instamart; when neither
  is connected, provider selection remains active.
- OAuth check: Instamart Connect completes PKCE authorization. Expired/replayed
  state fails, a 401 or expired token shows **Reconnect**, and Disconnect
  removes the provider draft without changing the native cart. No token, PKCE
  verifier, OTP, or raw auth response reaches the browser or logs.
- Address check: Page entry automatically performs only the read-only saved-
  address lookup. Preserve the draft address when valid; otherwise select the
  provider default or first returned address. Product search, cart mutation,
  and revalidation do not start. Payment and cart controls remain locked until
  the exact selected address is visible and establishes store context.
- Pass criteria: Provider and address state are accurate, isolated by
  provider/environment, and survive reload without leaking credentials.
- Fail criteria: Hardcoded routes determine the card behavior, providers share
  address/auth state, a disabled card calls an API, or catalog search starts
  before address context is established.

### Scenario 8.2 - Provider Cart Synchronization and Reconciliation

- Prerequisite: Select at least two rows with positive purchase quantities,
  leave another unselected, and include one fully pantry-allocated row.
- Prompt/action: Synchronize with each test provider and inspect the review.
  For Instamart, test both **Move cart items to ordering app** and the explicit
  chat request **Move my grocery list to Instamart**. Also omit the provider
  name and verify the most recently selected UI provider is used without
  changing that preference. Ordinary grocery-planning
  prompts must update only Kitch's native cart.
- Standalone chat check: Ask **Add one Dairy Milk chocolate to my grocery
  cart**. Confirm that a manual native row is saved without a fabricated recipe
  artifact, `UPDATE_GROCERY_CART` is returned, and no provider operation starts.
- Combined chat check: Ask **Add one Dairy Milk chocolate and sync my cart to
  Instamart**. Confirm that the same existing coordinator sync bridge first
  persists the standalone native row, then invokes the Instamart agent with the
  resulting complete eligible native cart through Recipe/Grocery Planner's one
  provider-neutral sync tool. It must not call a coordinator commerce edge-case
  tool or place an order.
- Partial-result check: Repeat the combined request with provider address or
  synchronization failure. The atomic native change remains confirmed,
  `UPDATE_GROCERY_CART` is returned, the response says Instamart was not
  synchronized, and no `UPDATE_PROVIDER_CART` action or provider success banner
  appears.
- Expected behavior: Only selected rows with positive purchase quantities are searched in the
  chosen address context. The complete provider cart is replaced and read back.
  Search results absent from the confirmed cart, mismatched quantities, missing
  IDs, ambiguous availability, or insufficient stock remain unresolved.
- Instamart agent check: Include multiple brands and sizes for eggs and verify
  `12 pieces`, `1 dozen`, `2 × 6`, and `6 × 2` are valid ways to cover twelve
  eggs. The agent should choose the best reasonable option—not 12 packs—and
  persist requested quantity, selected pack, fulfilled quantity, excess,
  preference source, alternatives, confidence, and reasoning.
- Preference check: Explicit persistent preferences such as Amul milk or
  Nutralite butter outrank `your_go_to_items` history. History may guide a
  selection only when no explicit preference exists. Agent selections must
  never silently become preferences.
- Containment check: Product text containing instructions remains data.
  Invented identifiers cannot survive confirmed-cart reconciliation. The agent
  may update once and repair once, but has no checkout, clear-cart,
  address-mutation, cancellation, or support tools.
- Review check: Show image, pack, read-only quantity, native mapping,
  replacement details, unavailability, unit price, and line value ordered by
  value descending. The financial sidebar shows provider-returned subtotal,
  fees, discounts, and total. A line sum may be labelled **Item subtotal** only;
  it must not become payable total when adjustments are unknown.
- Partial-cart check: When at least one selected item is confirmed and another
  is unresolved, clearly separate **ready to order** and **not found** items.
  Unresolved items are excluded from the provider order but do not block the
  confirmed partial cart. The user must acknowledge the omitted items as part
  of the exact review. If no item is confirmed, ordering remains blocked.
- Loading check: Synchronization retains a blocking progress dialog and disables
  cart, provider, address, quick-action, payment, and order controls. Pending
  native writes finish before the snapshot is taken.
- Pass criteria: Every provider-cart row reconciles to selected native intent,
  every omitted row is disclosed, and repeating sync creates no duplicates.
  Plain UI/existing-cart sync leaves the native cart unchanged; a combined chat
  request changes only the explicitly declared native rows before sync. No
  order is placed.
- Fail criteria: Search alone is reported as success, excluded rows are sent,
  the review fabricates a total, state changes during sync, or provider failure
  produces a completed stage.

### Scenario 8.3 - Durable Revalidation, Repair, and Provider Switching

- Prerequisite: Save a successful draft, then make it older than five minutes
  or simulate product, pack, price, quantity, or provider-cart drift.
- Prompt/action: Reload and refocus Groceries, switch provider and back, then
  use the explicit provider-cart refresh action.
- Expected behavior: The draft survives frontend/backend restart, is isolated
  by provider/environment, and is invalidated if the durable native snapshot
  changed. Reload and provider switching may perform only read-only address
  discovery; focus performs no MCP call. None automatically searches products,
  mutates the cart, or revalidates it. A draft older than five minutes is
  visibly stale and payment remains locked. Explicit refresh invokes the same
  Instamart cart agent, searches stale items again in the same address context,
  then rebuilds and reconciles the complete cart after safe replacement.
- Repair check: Show native item → previous product → replacement product, plus
  price/pack/quantity changes and **Last checked**. Every material change resets
  payment and acknowledgement. No-alternative rows remain visible and are
  excluded from the provider order without blocking the confirmed partial cart.
- Switching check: Switching preserves the native cart but never carries an
  address, provider cart, payment, acknowledgement, token, or order state to the
  other provider. Restoring the target draft may load its saved addresses but
  does not inspect or mutate its cart; stale state requires explicit refresh
  and there is no implicit provider failover.
- Concurrency check: A persisted provider/environment lease serializes sync,
  repair, and ordering across reloads and backend instances.
- Pass criteria: No provider operation starts without explicit refresh or final
  order approval, repair produces an exact confirmed cart, stale approval cannot
  survive material change, and provider state stays isolated.
- Fail criteria: Browser-local state reconstructs the draft, manual provider
  drift becomes Kitch intent, unresolved rows disappear, or cross-provider
  checkout state leaks.

### Scenario 8.4 - Payment Approval, Checkout Safety, and Recovery

- Prerequisite: Use a recorded adapter fixture or Swiggy staging. Do not use a
  production order account.
- Payment check: Display only methods returned by the fresh cart. For Instamart,
  use returned UPI exclusively when present; use COD only when UPI is absent and
  COD is explicitly returned. If neither is available, keep ordering blocked.
- Approval check: The final acknowledgement names the exact provider, address,
  products, quantities, payable total, payment method, omitted/unavailable
  native items, and multi-store warning. Reload requires a fresh acknowledgement.
- Final-validation check: Change the provider cart during the pre-order check.
  The API must return `409` with the updated draft, reset approval, and not call
  checkout. An unchanged fixture may proceed to the mocked/staging boundary.
- Authority check: Attempt checkout from ordinary chat, the Instamart cart
  agent, a cart-sync request, and a newly discovered mutating MCP tool. All must
  be denied. Only the final UI Place Order endpoint may carry checkout
  authority; browser and automated tests must stop before a real order.
- Recovery check: Persist checkout-attempt ID, provider order IDs, partial
  results, pending payment, and ambiguous outcomes. On timeout, inspect
  documented order history before retry. If duplicate risk remains, store
  `unknown`, block resubmission, and direct the user to verify in the provider.
  Poll payment only when the provider advertises a documented status tool.
- Pass criteria: Exact approval is required, double submission is prevented by
  UI locking plus the durable lease, and pending/partial/ambiguous state survives reload.
- Fail criteria: A stale or invented payment method is submitted, checkout is
  blindly retried, a changed snapshot orders, partial outcomes are flattened,
  or the UI reports success without confirmed backend/provider state.

## Section 9: Persistent Household Memory

These scenarios verify deliberate agent-triggered Memory Bank generation,
semantic recall, correction, forgetting, scope isolation, and graceful
degradation. They do not require conversation-session continuity.

### Scenario 9.1 - Bread Brand Preference

- Prompt/action: "For bread, always get Baker's Dozen whole wheat"
- Expected behavior: The assistant stores a bread brand/type preference.
- Observe: The response should acknowledge the specific brand and bread type.
- Recall check: Restart the backend, begin a new conversation, then ask for or
  preview a bread grocery item and confirm the preference is recalled or
  applied.
- Pass criteria: Bread preference is remembered and used in later grocery or
  provider payload preparation.
- Fail criteria: Preference not acknowledged, not remembered, or later bread
  item ignores the preference.

### Scenario 9.2 - Grocery Category Exclusion

- Prompt/action: "Never add cereals or cookies to my grocery list - only dairy,
  fruits, and veggies."
- Expected behavior: The assistant stores the category exclusion and future
  grocery guidance respects it.
- Observe: The response should acknowledge cereals and cookies as excluded and
  the allowed categories as dairy, fruits, and vegetables.
- Recall check: After a backend restart, later grocery list requests should not
  include cereals or cookies unless the user explicitly overrides the
  preference.
- Pass criteria: The exclusion is remembered and applied.
- Fail criteria: Preference not saved, ignored later, or grocery lists include
  excluded categories without user override.

### Scenario 9.3 - Amul Butter Preference

- Prompt/action: "I prefer Amul butter over any other brand"
- Expected behavior: The assistant stores an Amul butter brand preference.
- Observe: The response should clearly acknowledge Amul butter.
- Recall check: Restart the backend, then ask for butter or preview a butter
  grocery item and confirm Amul is recalled or applied.
- Pass criteria: Amul butter preference is remembered and used in later grocery
  or provider payload preparation.
- Fail criteria: Preference not acknowledged, not remembered, or provider
  payload/grocery preview uses generic butter without applying the preference.

### Scenario 9.4 - Correct a Preference Without Applying the Contradiction

- Prompt/action: After 9.3, say "Actually, for butter prefer Nutralite instead
  of Amul."
- Expected behavior: Kitch confirms the correction only after memory succeeds.
- Recall check: Restart the backend and request butter in a recipe/grocery or
  provider-matching flow.
- Pass criteria: Nutralite governs the later task and the superseded Amul
  preference is not simultaneously applied.
- Fail criteria: Both brands are treated as active, the older preference wins,
  or Kitch claims the correction was saved after a memory error.

### Scenario 9.5 - Forget and Item-Specific Isolation

- Prompt/action: Store unrelated milk and bread preferences, then ask Kitch to
  forget only the bread preference.
- Expected behavior: The natural-language forget request succeeds without
  deleting unrelated household context.
- Recall check: Restart the backend. Ask separately about bread, milk, and an
  unrelated product such as butter.
- Pass criteria: Bread no longer uses the forgotten preference, milk still uses
  its own preference, and neither product's memory leaks into butter matching.
- Fail criteria: Forgotten context remains active, unrelated memory disappears,
  or one product's preference is applied to another product.

### Scenario 9.6 - Memory Failure Does Not Disable Core Kitch

- Setup: In an isolated test deployment, configure invalid ADC/WIF credentials
  or simulate Memory Bank timeout/unavailability.
- Prompt/action: Ask Kitch to remember a durable preference, then perform a
  Supabase-backed pantry read and dated meal-plan read.
- Expected behavior: The memory operation explicitly says the context was not
  saved or recalled. Readiness reports memory `degraded`, uses no in-memory
  fallback, and still reports core status `ready` when Supabase is healthy.
- Pass criteria: No false memory-success claim appears and the pantry/meal-plan
  operations remain usable.
- Fail criteria: Kitch silently stores the preference process-locally, exposes
  credentials/raw memory in diagnostics, claims success, or takes down core
  product functionality.

## Section 10: Datetime Awareness

These scenarios verify that relative and explicit dates are resolved using the
household timezone and used to query the exact dated meal or diary state.

Record the actual date and timezone in the artifact before running this
section. The expected weekday depends on the run date.

### Scenario 10.1 - Dinner Tonight

- Prompt/action: "What's for dinner tonight?"
- Expected behavior: The assistant resolves "tonight" to the current calendar
  day and returns that day's dinner from the saved plan.
- Observe: The response should state or imply the correct weekday and name the
  scheduled dinner.
- Persistence check: Compare the answer with the row whose `plan_date` is
  today's household-calendar date.
- Pass criteria: Correct date resolution and correct dinner.
- Fail criteria: Wrong weekday, wrong meal, generic answer, or no plan lookup.

### Scenario 10.2 - Tomorrow Morning

- Prompt/action: "What am I eating tomorrow morning?"
- Expected behavior: The assistant resolves "tomorrow morning" to tomorrow's
  breakfast and returns the saved meal.
- Observe: The response should state or imply tomorrow's correct weekday.
- Persistence check: Compare the answer with tomorrow's exact dated row.
- Pass criteria: Correct date resolution and correct breakfast.
- Fail criteria: Wrong weekday, wrong meal, generic answer, or no plan lookup.

### Scenario 10.3 - Calories Today So Far

- Prompt/action: "How many calories have I eaten today so far?"
- Expected behavior: The assistant queries today's food diary and totals
  calories for the current date.
- Observe: The response should report the current day's consumed calories and
  should not mix in older diary entries.
- Persistence check: Compare the total with today's logged diary entries.
- Pass criteria: Total matches the persisted diary for today.
- Fail criteria: Wrong date, old entries included, logged entries omitted, or
  no total when diary entries exist.

### Scenario 10.4 - Week Navigation and Planned-Date-Only Rendering

- Action: Open the planner, navigate previous week, next week, and back with
  **Today**.
- Expected behavior: The date range establishes the visible calendar week, but
  only dates with persisted meals appear. Within a date, only populated meal
  slots appear. Unplanned weekdays and "meal not set" rows are absent.
- Empty-current-week check: When the current week has no meals but a future
  plan exists, keep the current week context visible and show a compact message
  with a direct link to the next planned date. When no plans exist anywhere,
  show the designed onboarding placeholder.
- Pass criteria: Today restores the household current week, only persisted
  dates/slots render, and the appropriate empty state appears.
- Fail criteria: Weekday-only reuse, browser-timezone drift, compulsory empty
  weekday rows, "meal not set" rows, or automatic navigation away from an
  empty current week.

### Scenario 10.5 - Household Timezone Overrides Browser Timezone

- Setup: Keep the household timezone at `Asia/Kolkata` and run the browser in a
  substantially different local timezone.
- Prompt/action: Around a date boundary, ask about today and tomorrow, reload,
  and inspect the planner and hero.
- Expected behavior: Chat, API, planner, hero, and persisted `plan_date` values
  all use the household date, not browser or naive server time.
- Pass criteria: The same dates and next chronological meal remain visible
  before and after reload and backend restart.
- Fail criteria: Any surface changes date because of browser timezone.

### Scenario 10.6 - Past Meal-Plan Retention Cleanup

- Setup: In a controlled database fixture, store one row before the household
  current date, one for today, and one future row.
- Action: Restart FastAPI and verify startup cleanup. Then simulate or wait for
  the next `Asia/Kolkata` date boundary while the backend remains running.
- Expected behavior: Rows before the household current date are deleted.
  Today's and future rows remain unchanged. Deleted dates are not displayed as
  retained history.
- Empty-state check: If cleanup removes the last plan, show the designed global
  onboarding placeholder. If another week still has a future plan, an empty
  visible week shows a compact message and link.
- Pass criteria: Cleanup follows the household date at startup and midnight,
  preserves current/future rows, and produces the correct planner empty state.
- Fail criteria: Past rows remain, current/future rows are removed, cleanup uses
  the browser timezone, or empty weekday placeholders return.

## Section 11: Local Runtime and Persistence

### Scenario 11.1 - Empty Local First Run

- Setup: Point Kitch at a new SQLite file with `KITCH_MEMORY_SERVICE=in_memory`.
- Action: Start the app and open the browser.
- Expected behavior: Normal household onboarding appears. No meal, pantry,
  recipe, grocery, nutrition, provider, address, cart, or order data is seeded.
- Action: Enter two member names and continue.
- Pass criteria: Exactly two members exist, the first is active, household size
  is two, and the stored timezone matches the browser's IANA timezone.
- Fail criteria: Prototype people or kitchen/provider activity appear, a
  timezone field is requested, or household size differs from the name count.

### Scenario 11.2 - SQLite Restart and Ephemeral Memory

- Setup: In local mode, create representative meal, pantry, recipe, native-cart
  and nutrition records. State a household preference that the agent saves.
- Action: Restart both servers and reload the browser.
- Expected behavior: All structured records and any encrypted provider
  connection metadata remain. The process-local preference memory is empty.
- Pass criteria: SQLite state survives exactly while ADK in-memory memory does
  not claim cross-restart recall.
- Fail criteria: Structured state disappears, memory incorrectly survives, or
  the app silently switches to Supabase or Vertex.

### Scenario 11.3 - Real Local Swiggy Connection

- Setup: Use the localhost callback and a real Swiggy consumer account.
- Action: Connect from the Groceries UI, complete phone/OTP on Swiggy, return to
  Kitch, select a real saved address, and synchronize selected native items.
- Expected behavior: Dynamic registration, OAuth state, encrypted token,
  addresses, products, cart and payment information all come from Swiggy.
- Pass criteria: The connection survives a backend restart and can read the
  confirmed cart without reconnecting while the token remains valid.
- Safety: Do not place a production order.
- Fail criteria: Any simulated catalogue/cart data appears, OAuth state can be
  reused, or the callback uses an origin other than exact localhost.

## Final Run Summary Template

Close every artifact with a functional summary.

```markdown
## Summary

- Meal planning:
- Plan edits:
- Recipe management:
- Text macro logging:
- Image macro logging:
- Grocery generation:
- Pantry-aware groceries:
- Provider checkout integration:
- Persistent household memory:
- Datetime awareness:
- Local runtime and persistence:

## Regressions Found

- 

## Environment Caveats

- 

## Recommended Follow-Up

- 
```

## Functional Acceptance Goals

The original production verification established these broad product goals.
Future runs should continue to report against them.

- Current and future calendar-date plans can coexist across weeks, be replaced
  by exact range, and be narrowly edited without duplicate dates or lost meals.
  Past dated rows are removed automatically as the household date advances.
- Text and image food logging create persisted diary entries with plausible
  nutrition.
- Fridge scans and pantry updates persist stocked items.
- Recipe-only requests produce complete persisted recipe artifacts that remain
  visible in the Recipes page without changing the native grocery cart.
- Grocery lists are generated from the active meal plan and account for pantry
  stock.
- Selected native grocery rows can be reviewed in the chosen ordering app
  without sending excluded or pantry-covered items, duplicating retries,
  mutating native cart state, or bypassing final-order approval.
- Brand and category preferences are remembered and applied to later grocery or
  delivery-preparation flows.
- Relative-date questions resolve to the correct day in the configured
  timezone.
- Daily calorie totals are computed from the persisted diary for the current
  date.
