# Kitch Production Test Sections 1, 2, 5, 6, 7, 8 - Merged Artifact

- Generated: `2026-07-23T00:17:13+05:30`
- Timezone: `Asia/Kolkata`
- Source plan: `docs/production_test_results.md`, sections 1, 2, 5, 6, 7, and 8
- Source report SHA-256: `386780c01907e764234f09bf63a738213edd33dd32ddc6d253c2af7d9c051066`
- Original report modified: `no`
- Provider sync and real order placement: not exercised
- Selected evidence policy: keep passed scenarios `1.1`, `1.2`, and `7.3`; use continuation results for all remaining scenarios.

## Outcome

**3 PASS, 12 FAIL, 1 INCONCLUSIVE, 0 ERROR**

| Scenario | Section | Status | Model | Source | Result |
| :--- | :--- | :---: | :--- | :--- | :--- |
| 1.1 | Meal Plan Generation | **PASS** | `gemini-3.6-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_2026-07-22_23-24-06_IST` | 7 days/21 meals persisted with requested theme |
| 1.2 | Meal Plan Generation | **PASS** | `gemini-3.6-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_2026-07-22_23-24-06_IST` | 7 days/21 meals persisted with requested theme |
| 1.3 | Meal Plan Generation | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Plan persistence or requested theme validation failed |
| 2.1 | Plan Modification | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Unexpected plan delta or requested replacement missing |
| 2.2 | Plan Modification | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Unexpected plan delta or requested replacement missing |
| 2.3 | Plan Modification | **INCONCLUSIVE** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Generated prerequisite plan contained no salmon occurrences to replace |
| 5.1 | Grocery List Creation | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Recipe artifact or native cart persistence failed |
| 5.2 | Grocery List Creation | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Recipe artifact or native cart persistence failed |
| 6.1 | Pantry-Aware Grocery Subtraction | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Pantry persistence or cart subtraction evidence missing |
| 6.2 | Pantry-Aware Grocery Subtraction | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Vision persistence or pantry-aware follow-up evidence was incomplete |
| 7.1 | Preference Persistence | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Preference acknowledgement or recall/application failed |
| 7.2 | Preference Persistence | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Preference acknowledgement or recall/application failed |
| 7.3 | Preference Persistence | **PASS** | `gemini-3.6-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_2026-07-22_23-24-06_IST` | Preference acknowledged and recalled/applied |
| 8.1 | Datetime Awareness | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Response did not explicitly resolve Thursday |
| 8.2 | Datetime Awareness | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Response did not explicitly resolve Friday |
| 8.3 | Datetime Awareness | **FAIL** | `gemini-3.5-flash` | `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST` | Reported calorie total did not match persisted diary |

## Consolidation Notes

- The original three folders were fragments created by changing runtime conditions: Supabase paused, Gemini 3.6 quota exhausted, then Gemini 3.5 continuation.
- This folder is the canonical artifact. The fragment folders are retained under `source_fragments/` for auditability.
- The continuation run hit Gemini `503 UNAVAILABLE` high-demand responses for the remaining scenarios, so those failures mostly reflect provider unavailability rather than clean product behavior.
- Supabase remained reachable, but backend logs showed missing tables `public.grocery_cart_items` and `public.recipe_grocery_plans`; grocery persistence validations are affected by that schema gap.

## Detailed Evidence

Full structured evidence is in `results.json`. Per-scenario selected evidence summary follows.

### 1.1 - Meal Plan Generation - PASS

- Prompt: Plan my meals for next week. Keep it balanced and diverse.
- Model: `gemini-3.6-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_2026-07-22_23-24-06_IST`
- HTTP status: `200`
- Result: 7 days/21 meals persisted with requested theme
- Merge note: Previously passed; not rerun during Gemini 3.5 continuation.
- Response snippet: Here is your balanced and diverse meal plan for next week (**July 27, 2026 – August 2, 2026**): --- ### **Monday, July 27, 2026** * **Breakfast:** Berry & Nut Oatmeal with Honey * **Lunch:** Mediterranean Chickpea & Quinoa Salad * **Dinner:** Grilled Salmon with Asparagus and Brown Rice --- ### **Tuesday, July 28, 2026** * **Breakfast:** Avocado Toast with Poached Eggs * **Lunch:** Turkey and Veggie Wrap with Hummus * **Dinner:** Chicken & Broccoli Stir-Fry with Jasmine Rice --- ### **Wednesday, July 29, 2026** * **Breakfast:** Greek Yogurt Parfait with Granola & Fresh Berries * **Lunch:** Caprese Salad with Grilled Chicken * **Dinner:** Lean Beef Tacos with Black Beans and Corn Salsa --- ##

### 1.2 - Meal Plan Generation - PASS

- Prompt: Actually, I'm feeling like eating Indian food this week. Plan a completely new weekly meal plan focusing on delicious Indian dishes.
- Model: `gemini-3.6-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_2026-07-22_23-24-06_IST`
- HTTP status: `200`
- Result: 7 days/21 meals persisted with requested theme
- Merge note: Previously passed; not rerun during Gemini 3.5 continuation.
- Response snippet: Here is your new Indian meal plan for next week (**July 27, 2026 – August 2, 2026**): --- ### **Monday, July 27, 2026** * **Breakfast:** Poha with Roasted Peanuts & Curry Leaves * **Lunch:** Dal Tadka with Jeera Rice & Cucumber Raita * **Dinner:** Paneer Tikka Masala with Garlic Naan --- ### **Tuesday, July 28, 2026** * **Breakfast:** Masala Dosa with Sambar & Coconut Chutney * **Lunch:** Chana Masala with Whole Wheat Parathas * **Dinner:** Chicken Curry with Steamed Basmati Rice --- ### **Wednesday, July 29, 2026** * **Breakfast:** Aloo Paratha with Fresh Curd & Pickle * **Lunch:** Rajma Masala with Steamed Rice * **Dinner:** Palak Paneer with Rotis & Salad --- ### **Thursday, July 30, 2026

### 1.3 - Meal Plan Generation - FAIL

- Prompt: Change my preference to keto and make a full weekly keto meal plan.
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Plan persistence or requested theme validation failed
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 2.1 - Plan Modification - FAIL

- Prompt: Actually, swap Thursday dinner with something vegan.
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Unexpected plan delta or requested replacement missing
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 2.2 - Plan Modification - FAIL

- Prompt: Change Monday breakfast to chia pudding
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Unexpected plan delta or requested replacement missing
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 2.3 - Plan Modification - INCONCLUSIVE

- Prompt: I don't like salmon, replace it wherever it appears in my weekly meal plan.
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Generated prerequisite plan contained no salmon occurrences to replace
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 5.1 - Grocery List Creation - FAIL

- Prompt: What groceries do I need for the week?
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Recipe artifact or native cart persistence failed
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 5.2 - Grocery List Creation - FAIL

- Prompt: Make a shopping list
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Recipe artifact or native cart persistence failed
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 6.1 - Pantry-Aware Grocery Subtraction - FAIL

- Prompt: I already have eggs and avocado, update the grocery list.
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Pantry persistence or cart subtraction evidence missing
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 6.2 - Pantry-Aware Grocery Subtraction - FAIL

- Prompt: Log my fridge scan and tell me what else I still need to buy
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Vision persistence or pantry-aware follow-up evidence was incomplete
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 7.1 - Preference Persistence - FAIL

- Prompt: For bread, always get Baker's Dozen whole wheat
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Preference acknowledgement or recall/application failed
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 7.2 - Preference Persistence - FAIL

- Prompt: Never add cereals or cookies to my grocery list — only dairy, fruits, and veggies.
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Preference acknowledgement or recall/application failed
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 7.3 - Preference Persistence - PASS

- Prompt: I prefer Amul butter over any other brand
- Model: `gemini-3.6-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_2026-07-22_23-24-06_IST`
- HTTP status: `200`
- Result: Preference acknowledged and recalled/applied
- Merge note: Previously passed; not rerun during Gemini 3.5 continuation.
- Response snippet: You asked never to add **cereals** or **cookies** to your grocery list (focusing instead on dairy, fruits, veggies, and specified household staples). I have also updated your household food preferences to save that you **prefer Amul butter over any other brand**.

### 8.1 - Datetime Awareness - FAIL

- Prompt: What's for dinner tonight?
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Response did not explicitly resolve Thursday
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 8.2 - Datetime Awareness - FAIL

- Prompt: What am I eating tomorrow morning?
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Response did not explicitly resolve Friday
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

### 8.3 - Datetime Awareness - FAIL

- Prompt: How many calories have I eaten today so far?
- Model: `gemini-3.5-flash`
- Source: `docs/test_artifacts/production_sections_1_2_5_6_7_8_merged_2026-07-23_00-16-29_IST/source_fragments/production_sections_1_2_5_6_7_8_remaining_gemini_3_5_flash_2026-07-22_23-49-05_IST`
- HTTP status: `500`
- Result: Reported calorie total did not match persisted diary
- Merge note: Continuation result after model switch.
- Response snippet: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}

