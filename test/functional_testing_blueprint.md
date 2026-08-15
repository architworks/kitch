# Kitch Functional Testing Blueprint

This document converts the historical production verification scenarios from
`docs/production_test_results.md` into a reusable functional test template.
It is intended for manual, assisted, or automated functional testing of the
full Kitch product experience.

The goal is to validate user-visible behavior and persisted product state, not
implementation details. Testers should interact with the app as a household
user would: asking the assistant for meal plans, logging food, uploading
images, updating pantry state, requesting grocery lists, and checking whether
the app remembers preferences.

Structured product state is durable only after FastAPI receives a confirmed
Supabase result. Food and brand preferences currently use intentionally
ephemeral process-local ADK memory, so they are tested for same-process recall,
not persistence across a backend restart.

## Artifact Reporting Standard

Every test run should produce a dated artifact that is detailed enough for
debugging. Do not record only duration and status.

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
- Confirm `/api/health` reports ready before starting. It verifies the elevated
  backend credential, required tables/columns, and configured household profile.
- Confirm the app can read and write user profile, meal plan, pantry, food
  diary, grocery, and recipe-artifact state. Preference memory is explicitly
  ephemeral in this release.
- Use a stable local date and timezone in the artifact. Relative-date scenarios
  must record the actual calendar date used during the test.
- Use known image fixtures for image scenarios and link or copy them into the
  artifact folder.
- Do not place real delivery orders during functional verification unless a
  separate live-order approval test explicitly authorizes it.
- If a provider cart or grocery preview is used, treat it as a preview unless
  the product explicitly completes an approved cart sync.

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
- Persistence and recall check: Confirm the weekly plan is stored and the keto
  preference is reflected in later meal or grocery requests within the same
  backend process.
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

## Section 2A: Recipe Management

These scenarios verify that users can request full cooking details for a
planned meal without implicitly asking Kitch to buy anything. They cover the
Home-page **View details** flow, which seeds a `Show me the recipe for ...`
prompt, and the persisted recipe rendered in the Recipes page.

### Scenario 2A.1 - View Recipe Details for the Next Planned Meal

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

## Section 3: Macro Logging via Text Message

These scenarios verify that plain text food messages are converted into diary
entries with reasonable calorie and macro estimates.

### Scenario 3.1 - Roti and Dal Lunch

- Prompt/action: "I ate 2 rotis and dal for lunch today"
- Expected behavior: The assistant logs lunch for today with rotis and dal.
- Observe: The response should mention a logged meal and reasonable nutrition
  estimates.
- Persistence check: Confirm today's food diary includes the roti and dal meal.
- Pass criteria: Diary entry exists with plausible calories, protein, carbs,
  and fat.
- Fail criteria: No diary entry, wrong date, wrong meal, or wildly implausible
  nutrition.

### Scenario 3.2 - Smoothie Ingredients

- Prompt/action: "Had a smoothie - banana, peanut butter, oats, milk"
- Expected behavior: The assistant logs a smoothie based on the listed
  ingredients.
- Observe: The response should include a calorie estimate that reflects banana,
  peanut butter, oats, and milk.
- Persistence check: Confirm today's diary includes the smoothie.
- Pass criteria: Smoothie is saved with plausible nutrition.
- Fail criteria: Missing diary entry, missing major ingredients, or implausible
  estimate.

### Scenario 3.3 - Black Coffee

- Prompt/action: "Just had a black coffee, nothing else"
- Expected behavior: The assistant logs black coffee as a very low-calorie
  item.
- Observe: The response should not inflate calories by assuming milk, sugar, or
  snacks.
- Persistence check: Confirm today's diary includes black coffee.
- Pass criteria: Black coffee is saved with near-zero or low calories.
- Fail criteria: No entry, wrong food item, or added ingredients the user did
  not mention.

## Section 4: Macro Logging via Image

These scenarios verify multimodal food and fridge image handling.

### Scenario 4.1 - Salad Plate Photo

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

### Scenario 4.2 - Fridge Scan Updates Pantry

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

## Section 5: Grocery List Creation

These scenarios verify that the assistant can turn the active meal plan into a
usable grocery list.

### Scenario 5.1 - Weekly Groceries

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

### Scenario 5.2 - Shopping List

- Prompt/action: "Make a shopping list"
- Expected behavior: The assistant creates a usable shopping checklist from the
  active plan and pantry context.
- Observe: The response should be practical: item names, quantities where
  available, categories, or checklist format.
- Persistence check: Confirm the grocery list can be reviewed later.
- Pass criteria: A coherent shopping list is generated and persisted.
- Fail criteria: No list, no persistence, or the list ignores the active meal
  plan.

### Scenario 5.3 - Groceries for an Exact Date Range

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

## Section 6: Pantry-Aware Grocery Subtraction

These scenarios verify that the assistant updates pantry state and avoids
recommending items already stocked.

### Scenario 6.1 - Already Have Eggs and Avocado

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

### Scenario 6.2 - Fridge Scan and Remaining Groceries

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

## Section 7: Ordering App Integration

These scenarios verify the essential handoff from Kitch's durable native
grocery cart to the selected ordering app. Zepto is the current live provider;
Blinkit is a disabled future option. These tests stop before real order
placement.

### Scenario 7.1 - Move Selected Native Cart Items to Zepto

- Prerequisite: The native grocery cart contains at least two eligible,
  selected items, saved Zepto addresses load successfully, and the Zepto
  connection reports configured.
- Workflow check: Open **Groceries** and confirm the main column shows six
  chronological stages with round numbered markers: native cart, ordering app,
  delivery address, transfer, Zepto cart review, and payment and order. Later
  stages must remain visible but locked until their prerequisites are
  satisfied.
- Progress-state check: Pending stage markers must be light green and completed
  stages dark green. After a successful transfer, edit any native-cart row and
  confirm the transfer, review, and order markers return to pending until the
  cart is synchronized and reviewed again.
- Native-cart check: Confirm the native cart can be expanded for row-level
  review and collapsed back to its item/category/selection summary.
- Provider check: Confirm Zepto is selected by default. Blinkit must show
  **Coming soon**, remain disabled, and issue no provider requests.
- Prompt/action: Review the selected items, choose a saved delivery address,
  and click **Move to Zepto cart** from the main workflow.
- Expected behavior: Kitch establishes Zepto store context for the selected
  address before searching products, sends the selected eligible items to
  Zepto, and opens a review showing the resolved products, quantities, and
  availability.
- Review check: Compare the native selection with the Zepto review. Every
  successfully resolved item should correspond to a selected native row and
  must appear in the provider-confirmed cart with the exact returned product
  id, store-product id, and quantity;
  unavailable or substituted items should be clearly identified. Confirm the
  cart-item list uses the main-column width and the order summary appears in
  the right sidebar. Review the subtotal, discounts, fee lines, total, and
  total-source label.
- Cart-row check: Confirm each resolved row shows the Zepto product image when
  returned, mapped Kitch item, unit price, read-only quantity, pack size, and
  line subtotal. Rows must be ordered by `price × quantity` descending. No
  match-quality badges or direct `+`/`−` quantity controls should appear.
- Transfer-stage check: Confirm stage 4 is one compact row containing its title,
  explanation, and single transfer button without an extra inner section.
- Total check: If Zepto returns a final cart total, it must be shown unchanged.
  If Zepto omits it and returns exact line prices/quantities with no adjustment,
  their exact sum may be shown and labelled **Exact line-item total**. If any
  fee, tax, discount, or other adjustment exists without a Zepto final total,
  the total must be **Unavailable**; Kitch must not calculate it.
- Native-state check: Syncing to Zepto must not delete, check off, or otherwise
  mutate the durable native grocery cart.
- Availability check: A catalog search result alone must not count as success.
  Products with missing, ambiguous, false, or insufficient availability must
  remain unresolved, and items absent from the confirmed cart must not appear
  as successfully transferred.
- Concurrency and loading check: Start the sync and, while it is running,
  confirm that a modal transfer animation is visible and retains focus. Verify
  that selection, quantity, unit, add, delete, clear, quick-action, and address
  controls are disabled. If a native-cart save is already in progress, the
  Zepto sync must wait rather than snapshotting stale values.
- Pass criteria: The sync completes, the prominent **Zepto cart review**
  accurately represents the selected native items and the sidebar accurately
  represents either the authoritative provider total or safe line-item total,
  the cart stays locked only for the duration of the request, payment/order
  controls unlock only after review, and no order is placed.
- Fail criteria: Nothing reaches the Zepto review, unrelated items are added,
  quantities are materially wrong without explanation, native rows change, or
  the UI claims success after a provider failure. A missing or unserviceable
  address must fail before product search rather than marking every grocery
  item unavailable.

### Scenario 7.2 - Selection, Pantry Exclusion, and Repeat Sync

- Prerequisite: Keep one eligible item selected, leave another eligible item
  unselected, and include at least one pantry-covered row.
- Prompt/action: Sync the cart to Zepto, inspect the review, then repeat the
  sync without changing the native selection.
- Expected behavior: Only selected, non-pantry-covered rows are offered to
  Zepto. Unselected and already-stocked rows are excluded. Repeating the same
  sync should refresh or reproduce the same reviewed cart rather than
  multiplying quantities or creating duplicate products.
- Stale-review check: After a successful sync, change a native quantity,
  selection, delivery address, or provider choice. The old provider review,
  payment state, and acknowledgement must be invalidated, and order placement
  must remain locked until another sync.
- Durable-draft check: Reload the frontend or restart the backend and return to
  Groceries. The same Supabase-backed checkout draft should be restored rather
  than disappearing or being reconstructed from browser-local state. A true
  reload must require a fresh final acknowledgement.
- Timed revalidation check: Make the draft older than five minutes or return
  focus after that interval. Confirm that Kitch locks checkout editing, reads
  the live Zepto cart, and revalidates expected products before unlocking it.
- Repair check: Simulate one previously orderable product becoming unavailable.
  Kitch should search in the same address/store context, replace it with a
  confirmed orderable alternative, rebuild the complete provider cart, and
  show the before/after product. Payment and acknowledgement must reset.
- Unresolved check: If no orderable alternative exists, keep the unresolved
  native item visible and block the complete order rather than silently
  removing it or allowing a partial checkout.
- Pass criteria: The review respects selection and pantry coverage, the second
  sync remains equivalent without duplicates, and any later native/provider
  change invalidates the old review before ordering.
- Fail criteria: Unselected or pantry-covered items are sent, selected eligible
  items disappear without explanation, or the retry duplicates products or
  quantities.

### Scenario 7.3 - Zepto Failure and Final-Approval Safety

- Prompt/action: Exercise a recoverable provider failure, unavailable-item
  response, or incomplete checkout state during cart sync or review.
- Expected behavior: The UI explains what failed or is unavailable, preserves
  the native cart, and allows a safe retry. It must not display a completed
  sync when the provider rejected the operation.
- Approval check: Confirm that placing an order remains unavailable until the
  exact Zepto cart, delivery address, payment method, and final acknowledgement
  have been reviewed. Do not grant final approval or place a real order during
  this functional test.
- Final-revalidation check: With a test double or other non-ordering fixture,
  make the provider cart change during the final availability check. The API
  must return `409`, show the updated draft, reset approval, and never invoke
  order placement. An unchanged fixture may proceed only up to the mocked
  provider-order boundary; never place a live order during this test.
- Pass criteria: Provider problems are visible and recoverable, native state is
  preserved, and no order can be placed accidentally or from a stale review.
- Fail criteria: The UI hides the failure, loses native cart state, shows false
  success, or permits order placement without the required review and explicit
  final approval.

## Section 8: Ephemeral Preference Recall

These scenarios verify that brand and category preferences affect later grocery
or delivery-preparation behavior within the running backend process. They do
not claim persistence across a backend restart until Vertex AI memory is used.

### Scenario 8.1 - Bread Brand Preference

- Prompt/action: "For bread, always get Baker's Dozen whole wheat"
- Expected behavior: The assistant stores a bread brand/type preference.
- Observe: The response should acknowledge the specific brand and bread type.
- Recall check: Later ask for or preview a bread grocery item in the same
  backend process and confirm the preference is recalled or applied.
- Pass criteria: Bread preference is remembered and used in later grocery or
  provider payload preparation.
- Fail criteria: Preference not acknowledged, not remembered, or later bread
  item ignores the preference.

### Scenario 8.2 - Grocery Category Exclusion

- Prompt/action: "Never add cereals or cookies to my grocery list - only dairy,
  fruits, and veggies."
- Expected behavior: The assistant stores the category exclusion and future
  grocery guidance respects it.
- Observe: The response should acknowledge cereals and cookies as excluded and
  the allowed categories as dairy, fruits, and vegetables.
- Recall check: Later grocery list requests in the same backend process should
  not include cereals or cookies unless the user explicitly overrides the
  preference.
- Pass criteria: The exclusion is remembered and applied.
- Fail criteria: Preference not saved, ignored later, or grocery lists include
  excluded categories without user override.

### Scenario 8.3 - Amul Butter Preference

- Prompt/action: "I prefer Amul butter over any other brand"
- Expected behavior: The assistant stores an Amul butter brand preference.
- Observe: The response should clearly acknowledge Amul butter.
- Recall check: Later ask for butter or preview a butter grocery item in the
  same backend process and confirm Amul is recalled or applied.
- Pass criteria: Amul butter preference is remembered and used in later grocery
  or provider payload preparation.
- Fail criteria: Preference not acknowledged, not remembered, or provider
  payload/grocery preview uses generic butter without applying the preference.

## Section 9: Datetime Awareness

These scenarios verify that relative and explicit dates are resolved using the
household timezone and used to query the exact dated meal or diary state.

Record the actual date and timezone in the artifact before running this
section. The expected weekday depends on the run date.

### Scenario 9.1 - Dinner Tonight

- Prompt/action: "What's for dinner tonight?"
- Expected behavior: The assistant resolves "tonight" to the current calendar
  day and returns that day's dinner from the saved plan.
- Observe: The response should state or imply the correct weekday and name the
  scheduled dinner.
- Persistence check: Compare the answer with the row whose `plan_date` is
  today's household-calendar date.
- Pass criteria: Correct date resolution and correct dinner.
- Fail criteria: Wrong weekday, wrong meal, generic answer, or no plan lookup.

### Scenario 9.2 - Tomorrow Morning

- Prompt/action: "What am I eating tomorrow morning?"
- Expected behavior: The assistant resolves "tomorrow morning" to tomorrow's
  breakfast and returns the saved meal.
- Observe: The response should state or imply tomorrow's correct weekday.
- Persistence check: Compare the answer with tomorrow's exact dated row.
- Pass criteria: Correct date resolution and correct breakfast.
- Fail criteria: Wrong weekday, wrong meal, generic answer, or no plan lookup.

### Scenario 9.3 - Calories Today So Far

- Prompt/action: "How many calories have I eaten today so far?"
- Expected behavior: The assistant queries today's food diary and totals
  calories for the current date.
- Observe: The response should report the current day's consumed calories and
  should not mix in older diary entries.
- Persistence check: Compare the total with today's logged diary entries.
- Pass criteria: Total matches the persisted diary for today.
- Fail criteria: Wrong date, old entries included, logged entries omitted, or
  no total when diary entries exist.

### Scenario 9.4 - Week Navigation and Planned-Date-Only Rendering

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

### Scenario 9.5 - Household Timezone Overrides Browser Timezone

- Setup: Keep the household timezone at `Asia/Kolkata` and run the browser in a
  substantially different local timezone.
- Prompt/action: Around a date boundary, ask about today and tomorrow, reload,
  and inspect the planner and hero.
- Expected behavior: Chat, API, planner, hero, and persisted `plan_date` values
  all use the household date, not browser or naive server time.
- Pass criteria: The same dates and next chronological meal remain visible
  before and after reload and backend restart.
- Fail criteria: Any surface changes date because of browser timezone.

### Scenario 9.6 - Past Meal-Plan Retention Cleanup

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
- Zepto cart integration:
- Ephemeral preference recall:
- Datetime awareness:

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
- Selected native grocery rows can be reviewed in Zepto without sending
  excluded or pantry-covered items, duplicating retries, mutating native cart
  state, or bypassing final-order approval.
- Brand and category preferences are remembered and applied to later grocery or
  delivery-preparation flows.
- Relative-date questions resolve to the correct day in the configured
  timezone.
- Daily calorie totals are computed from the persisted diary for the current
  date.
