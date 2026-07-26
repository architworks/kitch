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
- Confirm the app can read and write user profile, meal plan, pantry, food
  diary, grocery, and preference state.
- Use a stable local date and timezone in the artifact. Relative-date scenarios
  must record the actual calendar date used during the test.
- Use known image fixtures for image scenarios and link or copy them into the
  artifact folder.
- Do not place real delivery orders during functional verification unless a
  separate live-order approval test explicitly authorizes it.
- If a provider cart or grocery preview is used, treat it as a preview unless
  the product explicitly completes an approved cart sync.

## Historical Regression Context: Meal Plan Upsert Conflict

The original production result document included a resolved database conflict
bug. Keep this as a regression concern during meal plan generation and edit
testing.

Functional risk to test:

- Creating a new weekly meal plan should replace or update the existing week
  without duplicate-day errors.
- Editing one meal should not create a duplicate day.
- Replanning the whole week should leave exactly one plan entry per day.
- Repeated edits should preserve unrelated meals.

Functional pass criteria:

- The user sees a successful assistant response.
- The planner still shows one complete weekly plan.
- No duplicate days appear.
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

These scenarios verify that the assistant can generate complete weekly meal
plans and replace an existing weekly plan when the user changes dietary or
cuisine preference.

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

- Prompt/action: "Actually, I'm feeling like eating Indian food this week. Plan
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
  plan."
- Expected behavior: The assistant acknowledges or applies keto preference and
  creates a complete keto-oriented weekly plan.
- Observe: Meals should be plausibly keto: eggs, avocado, paneer, chicken,
  fish, tofu, salads, low-carb vegetables, nuts, chia, or similar items. Heavy
  carb staples should not dominate the plan.
- Persistence check: Confirm the weekly plan is stored and the keto preference
  is reflected in later meal or grocery requests.
- Pass criteria: Complete keto plan is saved and later behavior respects keto.
- Fail criteria: Incomplete plan, non-keto plan, preference not remembered, or
  old cuisine plan remains.

## Section 2: Plan Modification

These scenarios verify that targeted edits affect only the requested meals and
preserve the rest of the weekly schedule.

### Scenario 2.1 - Swap Thursday Dinner to Vegan

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

## Section 7: Preference Persistence

These scenarios verify that brand and category preferences persist and affect
later grocery or delivery-preparation behavior.

### Scenario 7.1 - Bread Brand Preference

- Prompt/action: "For bread, always get Baker's Dozen whole wheat"
- Expected behavior: The assistant stores a bread brand/type preference.
- Observe: The response should acknowledge the specific brand and bread type.
- Persistence check: Later ask for or preview a bread grocery item and confirm
  the preference is recalled or applied.
- Pass criteria: Bread preference is remembered and used in later grocery or
  provider payload preparation.
- Fail criteria: Preference not acknowledged, not remembered, or later bread
  item ignores the preference.

### Scenario 7.2 - Grocery Category Exclusion

- Prompt/action: "Never add cereals or cookies to my grocery list - only dairy,
  fruits, and veggies."
- Expected behavior: The assistant stores the category exclusion and future
  grocery guidance respects it.
- Observe: The response should acknowledge cereals and cookies as excluded and
  the allowed categories as dairy, fruits, and vegetables.
- Persistence check: Later grocery list requests should not include cereals or
  cookies unless the user explicitly overrides the preference.
- Pass criteria: The exclusion is remembered and applied.
- Fail criteria: Preference not saved, ignored later, or grocery lists include
  excluded categories without user override.

### Scenario 7.3 - Amul Butter Preference

- Prompt/action: "I prefer Amul butter over any other brand"
- Expected behavior: The assistant stores an Amul butter brand preference.
- Observe: The response should clearly acknowledge Amul butter.
- Persistence check: Later ask for butter or preview a butter grocery item and
  confirm Amul is recalled or applied.
- Pass criteria: Amul butter preference is remembered and used in later grocery
  or provider payload preparation.
- Fail criteria: Preference not acknowledged, not remembered, or provider
  payload/grocery preview uses generic butter without applying the preference.

## Section 8: Datetime Awareness

These scenarios verify that relative dates are resolved correctly and used to
query meal or diary state.

Record the actual date and timezone in the artifact before running this
section. The expected weekday depends on the run date.

### Scenario 8.1 - Dinner Tonight

- Prompt/action: "What's for dinner tonight?"
- Expected behavior: The assistant resolves "tonight" to the current calendar
  day and returns that day's dinner from the saved plan.
- Observe: The response should state or imply the correct weekday and name the
  scheduled dinner.
- Persistence check: Compare the answer with the current saved weekly plan.
- Pass criteria: Correct date resolution and correct dinner.
- Fail criteria: Wrong weekday, wrong meal, generic answer, or no plan lookup.

### Scenario 8.2 - Tomorrow Morning

- Prompt/action: "What am I eating tomorrow morning?"
- Expected behavior: The assistant resolves "tomorrow morning" to tomorrow's
  breakfast and returns the saved meal.
- Observe: The response should state or imply tomorrow's correct weekday.
- Persistence check: Compare the answer with tomorrow's breakfast in the saved
  weekly plan.
- Pass criteria: Correct date resolution and correct breakfast.
- Fail criteria: Wrong weekday, wrong meal, generic answer, or no plan lookup.

### Scenario 8.3 - Calories Today So Far

- Prompt/action: "How many calories have I eaten today so far?"
- Expected behavior: The assistant queries today's food diary and totals
  calories for the current date.
- Observe: The response should report the current day's consumed calories and
  should not mix in older diary entries.
- Persistence check: Compare the total with today's logged diary entries.
- Pass criteria: Total matches the persisted diary for today.
- Fail criteria: Wrong date, old entries included, logged entries omitted, or
  no total when diary entries exist.

## Final Run Summary Template

Close every artifact with a functional summary.

```markdown
## Summary

- Meal planning:
- Plan edits:
- Text macro logging:
- Image macro logging:
- Grocery generation:
- Pantry-aware groceries:
- Preference persistence:
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

- Weekly plans can be generated, replaced, and narrowly edited without
  duplicate days or lost meals.
- Text and image food logging create persisted diary entries with plausible
  nutrition.
- Fridge scans and pantry updates persist stocked items.
- Grocery lists are generated from the active meal plan and account for pantry
  stock.
- Brand and category preferences are remembered and applied to later grocery or
  delivery-preparation flows.
- Relative-date questions resolve to the correct day in the configured
  timezone.
- Daily calorie totals are computed from the persisted diary for the current
  date.

