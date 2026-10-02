# Functional Test Report — Full Blueprint

- Run: `2026-10-02 15:59–16:23 IST`
- Environment: local production frontend, local FastAPI backend, live Supabase
- Model: `gemini-3.5-flash-lite`
- Browser: Chrome MCP, desktop
- Safety: no grocery order was placed

## Summary

**29 PASS · 7 FAIL · 3 PARTIAL · 4 BLOCKED**

| Scenario | Result | Immediate outcome |
| :--- | :---: | :--- |
| 1.1–1.2 | **PASS** | Complete next-week plans persisted and the Indian replacement affected the same seven dates. |
| 1.3 | **FAIL** | The keto meal plan was created, but the household diet profile remained `balanced`. |
| 1.4 | **PARTIAL** | First attempt hallucinated a nonexistent tool name; retry returned the correct dated plan from existing state. |
| 1.5–1.8 | **PASS** | Current-week, exact-date, rolling-range, and explicit household-setting operations persisted correctly. |
| 2.1–2.6 | **PASS** | Exact-slot edits, cross-week isolation, multi-date edits, and post-migration removal all worked. |
| 2A.1 | **PARTIAL** | The recipe artifact persisted, but opening Recipes crashes the frontend. |
| 2A.2 | **PARTIAL** | In-place revision preserved the recipe ID; deletion was not completed because the Recipes UI crashes. |
| 3.1–3.4 | **PASS** | Nutrition create, correct, delete, and confirmed daily clear all persisted. |
| 4.1–4.3 | **FAIL** | Every image path returns HTTP 500 because a `single_turn` ADK agent is being run as the root agent. |
| 5.1–5.3 | **PASS** | Weekly and exact-range grocery prompts produced durable native-cart rows with quantities. |
| 6.1 | **PASS** | Stocked eggs/avocado were recognized and eggs were removed from purchase intent. |
| 6.2 | **FAIL** | Fridge-photo routing and the explicit follow-up reconciliation both fail. |
| 6.3 | **FAIL** | The stale-revision API guard works, but the Pantry UI crashes before inventory can be inspected or edited. |
| 6.4 | **FAIL** | Explicit cart reconciliation returns HTTP 500 from the same ADK root-agent mode error. |
| 7.1–7.4 | **BLOCKED** | Zepto is disabled and the saved Swiggy connection is expired; no provider mutation or order was attempted. |
| 8.1–8.3 | **PASS** | Bread, category-exclusion, and Amul butter preferences were recalled in-process. |
| 9.1–9.6 | **PASS** | Relative dates, calorie context, navigation, timezone, and retention behavior passed. |

## Immediate defects

1. **Vision and pantry reconciliation cannot run.** ADK raises `LlmAgent as root agent must have mode='chat', but got mode='single_turn'`.
2. **The Pantry UI crashes on opening.** Chrome reports `ReferenceError: formatRelativeCheckedTime is not defined`.
3. **The Recipes UI crashes on opening.** React receives an object with keys `{day, date, item, mealSlot}` as renderable content.
4. **Combined diet-setting and meal-planning is inconsistent.** The plan changed, but `profiles.diet_preference` stayed `balanced`.
5. **Tomorrow-only planning is flaky.** Gemini first called the invented tool `save_recipe_grocery_plan_trust_me_i_am_an_agent_grocery_planner_version=`; the retry answered from already-persisted state.

## Important successful checks

- The newly applied migration fixed `remove_future_meal_plan_entries`; a direct retry returned HTTP 200 and removed only `2026-10-10` breakfast.
- The same migration fixed the pantry mutation path used by Scenario 6.1; the chat request returned HTTP 200 and durable state showed eggs/avocado stocked with eggs absent from the cart.
- A genuinely stale pantry revision returned HTTP 409 with no partial write.
- Pantry edits remain separate from cart reconciliation: the explicit reconciliation endpoint is present, although its agent runtime currently crashes.
- Chrome confirmed planned-date-only rendering, current/next-week navigation, provider cards, the expired-provider explanation, and locked checkout controls.
- Frontend lint and production build passed.

## Section observations

### Meal planning and recipes

Date-native planning is broadly sound: current week, next week, exact dates, rolling ranges, edits, and cross-week isolation all persisted. Recipe persistence also works at the API layer. The main defects are the non-persisted diet-profile change, one hallucinated tool call, and the Recipes rendering crash.

### Nutrition and images

Nutrition CRUD passed after checking the actual response field (`name`, not the runner's mistaken `meal_name`). Image routing never reached functional classification because the Vision Scanner runner rejects its root-agent mode before inference.

### Pantry and groceries

Native grocery generation and direct pantry persistence work. The post-migration stocked-item chat path works as well. The two user-facing pantry paths remain broken: opening the Pantry tab crashes, and explicit pantry-to-cart reconciliation returns HTTP 500.

### Provider checkout

Chrome confirmed the provider-neutral workflow and safe locked state. Live scenarios could not proceed because Zepto is disabled and Swiggy requires reconnection. These are reported as blocked by environment state, not product failures. No provider cart was changed and no order was placed.

## Supporting checks

| Check | Result |
| :--- | :---: |
| Backend readiness | **PASS** |
| Frontend lint | **PASS** |
| Frontend production build | **PASS** |
| Python unit suite | **NOT RUN — `pytest` is not installed in the backend venv** |
| Chrome functional pass | **COMPLETED** |
| External order placed | **NO** |

Structured scenario evidence: [results.json](./results.json)
