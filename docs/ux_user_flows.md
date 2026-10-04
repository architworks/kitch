# Kitch UX User Flows and Functional Experience Brief

This document is for UI/UX design planning. It describes what users need to accomplish with Kitch, how the experience should behave, and what interactions need to be designed.

It intentionally does not prescribe screens, page layouts, components, or visual treatments.

---

## 1. Product Idea

Kitch is an AI-powered household meal planning, nutrition logging, pantry tracking, and grocery preparation assistant.

The app is designed for a shared household where multiple people eat from the same meal plan and pantry, but still track their own personal nutrition. In the current prototype, the household is prefilled with three members: Archit, Anubhav, and Naman.

Kitch should feel like a practical kitchen companion:

- It helps the household decide what to eat.
- It creates plans for exact calendar dates, from one day to full weeks.
- It remembers preferences.
- It tracks what food is already available at home.
- It turns planned meals into a grocery list.
- It helps each individual log what they ate.

The central UX challenge is that Kitch combines two modes:

1. **Conversational control**
   Users can ask for plans, changes, pantry updates, meal logs, grocery lists, and preferences in natural language.

2. **Structured household state**
   Users also need to see and trust the current meal plan, pantry, grocery requirements, and personal nutrition records.

The experience should make those two modes feel connected: when the agent says it changed something, the structured household state should visibly reflect that change.

---

## 2. Core Experience Principles

### Clarity Over Magic

The AI can reason and generate, but users must always understand what changed, what was saved, and what still needs review.

### Household First, Individual Where Needed

Meal plans, pantry, and grocery preparation belong to the household. Macro logs and daily nutrition progress belong to the active individual.

### Explicit Dates for Planning

When a user asks for a weekly plan, the plan should clearly belong to a real date range. If today is Saturday and the user asks for next week, the plan should start on the upcoming Monday and run through Sunday. Future Saturdays should not be labeled as today.

### Fast Everyday Use

Common actions should work through short, casual language:

- "What's for dinner?"
- "Plan next week."
- "We have eggs and paneer."
- "I ate dal and rice."
- "Add Amul butter as my preference."

### Review Before External Order

Provider cart sync and order placement are separate. Explicit chat or UI action
may prepare a reversible provider cart. Only the UI may authenticate, choose the
saved provider default, select payment, approve the final snapshot, or order.

---

## 3. User Types and Context

### Household Member

A household member uses Kitch to:

- See what the household is eating.
- Ask for changes to the shared meal plan.
- Update pantry items.
- Prepare grocery requirements.
- Log their own meals and nutrition.
- Ask everyday food questions.

### Active Member

At any moment, the app has an active member context. This matters for personal nutrition logging.

When a meal is logged, it should be logged for the active member unless the user explicitly says otherwise.

### Household Context

The household context includes:

- Shared date-specific meal plan.
- Shared pantry and fridge stock.
- Shared grocery preparation.
- Shared brand and shopping preferences.
- Household size for scaling planned food.

---

## 4. Primary User Goals

Users should be able to:

1. Create a dated meal plan for one day, a range, this week, or next week.
2. Understand what is planned for a specific day or meal.
3. Modify one meal without damaging the rest of the plan.
4. Update pantry stock manually, conversationally, or from a fridge photo.
5. Generate a grocery list from the current plan and pantry.
6. Sync eligible grocery rows to Zepto or Swiggy Instamart for review.
7. Save brand preferences for future grocery preparation.
8. Log personal food intake from text or a plate photo.
9. See personal daily nutrition progress.
10. Switch active member context without mixing personal logs.

---

## 5. Flow: Create a Dated Household Meal Plan

### User Intent

The user wants Kitch to decide what the household should eat on one or more
real calendar dates.

Example prompts:

- "Create a meal plan for next week."
- "Plan balanced meals for the three of us."
- "Make next week Indian and high protein."
- "Give us a keto meal plan for the coming week."
- "Plan tomorrow's meals."
- "Plan the next three days starting tomorrow."
- "Plan meals for August 20."

### Expected Experience

1. The user expresses the planning request naturally.
2. Kitch resolves the requested dates using the household timezone.
3. Kitch generates exactly the requested range. "Next week" remains the next
   Monday through Sunday, while "tomorrow" affects only tomorrow.
4. Kitch accounts for household size, diet preference, and known preferences.
5. Kitch saves the plan as structured household state.
6. Kitch replies with a readable summary including exact dates.
7. The planner navigates to the first affected date and selects it.

### Functional UX Requirements

- The date range must be explicit.
- Each planned day should be associated with a date.
- The plan should be clearly household-wide, not personal to one member.
- If the user asks for "next week," the plan starts on the next Monday even
  when the current week still has future dates.
- "This week" covers today through Sunday; it never rewrites past dates.
- "Next N days" begins today unless the user explicitly says to start tomorrow.
- Plans for other dates and weeks must coexist unchanged.
- If the user gives vague constraints, Kitch should make reasonable choices rather than force a long setup.
- If the user gives incompatible constraints, Kitch should ask a clarifying question.

### Important States

- No plan exists yet.
- Plan generation is in progress.
- Plan successfully saved.
- Plan partially failed to save.
- Requested dates are being replaced atomically.
- Existing plan should be preserved and only changed in requested places.

---

## 6. Flow: Check What Is Planned

### User Intent

The user wants to know what they or the household will eat.

Example prompts:

- "What's for dinner tonight?"
- "What's planned for Monday lunch?"
- "What are we eating tomorrow morning?"
- "Show me next week's dinners."

### Expected Experience

1. Kitch resolves the date or meal being asked about.
2. Kitch reads the saved household plan.
3. Kitch answers with the relevant meal or meals.
4. If the plan has no meal for that slot, Kitch says that clearly and offers to fill it.

### Functional UX Requirements

- "Tonight" should refer to the real current date.
- A bare weekday should refer to the week visible in the planner. Without that
  UI context, it means the nearest non-past occurrence.
- The experience should distinguish between the current real day and a future day in the meal plan.
- If there is ambiguity, Kitch should clarify rather than confidently answering the wrong day.

---

## 7. Flow: Modify the Meal Plan

### User Intent

The user wants to change part of the plan.

Example prompts:

- "Change Thursday dinner to something vegan."
- "Replace salmon wherever it appears."
- "Make Monday breakfast lighter."
- "Swap tomorrow's dinner with something Indian."

### Expected Experience

1. User describes the desired change.
2. Kitch reads the current saved plan.
3. Kitch changes only the relevant meal slots.
4. Kitch saves the updated plan.
5. Kitch explains what changed.
6. The structured plan updates to match the change.

### Functional UX Requirements

- Single-meal changes should not rewrite the entire week.
- Multi-meal replacements should clearly list all affected exact dates.
- Past meal-plan rows are automatically deleted when the household calendar
  date advances. They cannot be created, changed, or used as retained history.
- If the requested meal does not exist, Kitch should explain that and offer alternatives.
- If the replacement affects groceries, future grocery preparation should use the updated plan.
- The user should be able to revise the plan through conversational follow-ups.

---

## 8. Flow: Update Pantry and Fridge Stock

### User Intent

The user wants Kitch to know what the household already has.

Example prompts:

- "We have 6 eggs and a block of paneer."
- "Add two cartons of milk."
- "Remove bread from pantry."
- "Scan this fridge photo."

### Expected Experience

1. The user provides items through text, manual entry, or photo. For an update
   to existing stock, Kitch reads the current pantry before deciding the new
   state.
2. The Pantry tab shows every row, amount, unit, last update, revision freshness,
   add/edit/remove controls, and “Mark pantry empty.”
3. For a photo, Vision Scanner first classifies it as `meal`, `pantry`, or
   `ambiguous`; Camera and Gallery follow the identical path.
4. A pantry observation routes to Recipe/Grocery Planner. Current inventory is
   set rather than repeatedly accumulated; explicitly new purchases are added.
5. An ambiguous image changes nothing and offers “Treat as meal” and “Treat as pantry.”
6. Kitch leaves the native cart unchanged and offers an explicit **Update cart from pantry** action. If invoked, it recalculates purchase quantities and invalidates a provider review only when purchase intent changes.

### Functional UX Requirements

- Pantry is shared across the household.
- Pantry updates should never be personal to only one member.
- Every added, set, or adjusted item must identify its quantity; Kitch must not
  persist a quantity-bearing change after dropping the observed amount.
- Kitch should handle approximate quantities when exact amounts are unknown.
- Classification uses explicit states rather than a displayed confidence score.
- Complete replacement and emptying require an exact-impact confirmation.
- Incremental edits do not reset the full-review age.
- Duplicate items should merge or update rather than becoming confusing duplicates.
- Users should be able to correct pantry mistakes quickly.

### Important States

- Empty pantry.
- Item added.
- Existing item quantity increased.
- Item removed.
- Photo scan in progress.
- Photo scan uncertain.
- Pantry update failed.

---

## 9. Flow: Generate Grocery Requirements

### User Intent

The user wants to know what to buy for the household.

Example prompts:

- "What groceries do we need this week?"
- "Make a shopping list."
- "Compile the grocery list for next week's plan."
- "What do we still need after accounting for pantry?"

### Expected Experience

1. Kitch reads the dated meal range implied or specified by the request.
2. Kitch reads the shared pantry stock.
3. Kitch infers ingredients needed for the planned meals.
4. Kitch scales quantities for household size.
5. Kitch subtracts what is already available.
6. Kitch presents a categorized grocery requirement list.
7. Kitch saves the native household grocery cart so the Groceries page reflects the plan.

### Functional UX Requirements

- Grocery requirements should be derived from the saved plan, not a static recipe database.
- Pantry stock should visibly affect what is needed.
- Items already available should be shown as pantry-covered, not treated as items to buy.
- Users should understand why an item is or is not included.
- The result should support review and adjustment before checkout preparation.

### Current Product Boundary

The native grocery cart is structured backend state. The Groceries page presents
one visible, prerequisite-locked workflow: native cart review, ordering-app
selection, delivery address, provider transfer, provider cart review, then
payment and order. Zepto and Swiggy Instamart are backend-described providers;
Blinkit is disabled with `Coming soon`.

The native cart is also allowed to contain standalone `source=manual` intent
that did not come from a recipe. For example:

```text
"Add one Dairy Milk chocolate to my grocery cart."
```

Kitch routes this to the existing grocery specialist, persists the row without
inventing a recipe artifact, and reports only the confirmed native-cart change.

---

## 10. Flow: Prepare and Approve a Provider Cart

### User Intent

The user wants to project the reviewed native Kitch cart into a supported
ordering app without losing control of substitutions, price changes, or order approval.

Example prompts:

- "Open my groceries so I can order them."
- "Put tomorrow's groceries in Instamart."
- "Help me review this cart in Zepto."
- "Move my grocery list to Instamart."
- "Add one Dairy Milk chocolate and sync my cart to Instamart."

### Expected Experience

1. Native intent may come from recipe planning, standalone chat changes, or
   manual UI edits. The user may review and select eligible rows in the UI, but
   opening that screen is not mandatory for an explicit chat synchronization.
2. The user chooses Zepto or Swiggy Instamart. Blinkit remains visible and
   disabled. Kitch remembers the household's last selection.
3. If required, the user connects or reconnects the provider. Instamart shows
   its environment and uses a household-owned OAuth connection.
4. The user selects a saved delivery address.
5. The user starts synchronization from the separate, clearly numbered UI
   stage, or explicitly requests synchronization in chat.
6. Kitch uses the native cart as the source of truth, excluding unselected and
   pantry-covered rows and applying known brand preferences.
7. Kitch searches only after establishing the selected address context,
   accepts only explicitly orderable matches, replaces the complete provider
   cart, and confirms exact identifiers and quantities in the
   resulting provider cart.
8. The main column shows the actual provider cart and unavailable items. The
   read-only rows show product images, mapped native items, unit prices,
   quantities, pack sizes, and line subtotals ordered from highest to lowest
   value. The right sidebar shows the financial summary without narrowing the
   cart list.
9. The sidebar shows provider-returned subtotal, fees, discounts, and payable
   total. A complete line-price sum may be shown only as `Item subtotal`, never
   as the final payable total when adjustments are unknown.
10. Returning later restores the provider/environment draft and automatically
   loads read-only saved addresses without refreshing the provider cart. After
   five minutes, Kitch marks the cart review stale and asks the user to refresh
   explicitly before payment or ordering.
11. Replacements and other material changes are highlighted and reset payment
    and approval. Unresolved selected items are prominently listed as omitted;
    the confirmed partial cart can proceed after review.
12. Kitch offers only fresh provider-returned payment methods. Instamart calls
    `get_payment_options`, passes the selected UPI app/QR flow unchanged, or
    offers explicit Cash only when UPI is absent.
13. The user acknowledges the exact provider, address, products, quantities,
    payable total, payment method, and any multi-store warning. Kitch then runs
    a final revalidation immediately before ordering.
14. Pending, partial, or ambiguous order state survives reload. A timeout is
    not blindly retried while duplicate-order risk remains.

For a combined explicit chat request, Kitch first applies the declared
standalone native change and then invokes the same provider synchronization
path with the resulting complete eligible native cart. It does not bypass
native intent, add another coordinator tool, or place an order.
If the provider is unavailable after the native transaction succeeds, Kitch keeps
the native change, says that the provider cart was not synchronized, and offers
the existing sync flow for retry; it never collapses that partial outcome into
provider success.

### Functional UX Requirements

- The experience must not imply that an actual order was placed.
- Native-only chat mutations must not claim that a provider cart changed.
- Explicit chat provider sync and UI provider sync must both use the same
  backend service, operation lease, Instamart agent, and confirmation rules.
- The experience may indicate that a provider cart changed only after sync and read-back reconciliation succeed.
- The user should see enough information to trust the actual provider cart
  contents and total. Kitch must never derive a final total when a provider reports
  a fee, tax, discount, or other adjustment without its own final total.
- The native cart starts as a compact summary and can be expanded for row-level
  editing without breaking the checkout chronology.
- Brand substitutions should be visible.
- Order placement must require explicit user approval.
- Connection, payment, address, capability, and provider failures should surface as safe, provider-scoped states.
- Editing a native row or selection, changing provider, or changing address
  invalidates the review and locks order placement until a fresh sync.
- Explicit cart refresh uses the blocking progress dialog and locks checkout
  editing until reconciliation finishes. Page entry and provider switching may
  read saved addresses, but never search products, mutate a cart, or revalidate
  it; browser focus starts no provider operation.
- If final revalidation changes the cart, no order is placed and the user is
  returned to the updated provider cart review.

### Current Product Boundary

Zepto and Instamart implement one backend contract. Instamart is limited to the
Swiggy `/im` MCP surface; Food and Dineout are inaccessible. Production Instamart
remains gated until Swiggy approval and a successful staging soak. Blinkit live
cart insertion is not implemented.

---

## 11. Flow: Save Brand and Shopping Preferences

### User Intent

The user wants Kitch to remember shopping preferences.

Example prompts:

- "Always buy Baker's Dozen whole wheat bread."
- "For butter, prefer Amul."
- "Don't add cereals to our grocery list."
- "Only buy organic eggs."

### Expected Experience

1. User states a preference naturally.
2. Kitch identifies the target item or category.
3. The relevant specialist submits the complete natural-language statement to
   persistent household memory when it represents durable context.
4. Kitch confirms the update only after Memory Bank completes extraction and
   consolidation. If memory is unavailable, it says the context was not saved
   while leaving unrelated planning and grocery functions usable.
5. Future grocery preparation uses the preference.

### Functional UX Requirements

- Brand preferences are household-level unless the user explicitly says they are personal.
- Kitch should confirm what it remembered.
- If a preference is ambiguous, Kitch should ask what item or category it applies to.
- Users should be able to overwrite or remove old preferences.
- Preferences should influence grocery preparation without requiring strict form entry.
- Corrections and requests to forget should replace or remove conflicting
  context instead of accumulating prefix-tagged facts.

---

## 12. Flow: Log Personal Food Intake

### User Intent

The user wants to track what they personally ate.

Example prompts:

- "I ate two rotis and dal."
- "Log my lunch."
- "I had a banana smoothie."
- "Scan this plate."

### Expected Experience

1. User describes food or provides a plate photo.
2. Kitch estimates calories and macros.
3. Kitch preserves an explicitly named meal/date/time. Otherwise, it assigns
   the entry to Breakfast, Lunch, Snack, or Dinner from the request receipt time
   in the household timezone.
4. Kitch logs the food and portion to the active member.
5. Kitch confirms the estimated nutrition.
6. The active member's dated daily and weekly nutrition state updates.

### Functional UX Requirements

- Food logs are individual, not household-wide.
- The active member context must be clear.
- Kitch should not log a meal for the wrong person.
- Users should be able to correct meal name, quantity, or estimated macros.
- Kitch should communicate uncertainty in estimates.
- Vision Scanner identifies food but does not guess the meal group.

### Important States

- No meals logged today.
- Meal logged successfully.
- Estimate needs confirmation.
- User corrected estimate.
- Log failed.

---

## 13. Flow: Review Personal Nutrition Progress

### User Intent

The user wants to understand their intake for the day.

Example prompts:

- "How many calories have I eaten today?"
- "How much protein did I get?"
- "Clear my logs for today."
- "What did I eat today?"

### Expected Experience

1. Kitch reads the active member's diary.
2. Kitch summarizes calories and macros.
3. Kitch compares intake to the member's targets.
4. The user can navigate dates and compare the selected week's intake.
5. The user can add, edit, delete, or clear dated food entries and edit goals.

### Functional UX Requirements

- Nutrition summaries should be personal to the active member.
- Switching members should change personal logs without changing household meal plan or pantry.
- Kitch should make clear whether it is answering for one person or the household.
- Clearing logs should affect only the active member.
- Daily totals remain derived from entries rather than becoming independently
  editable numbers.
- Food entries are grouped by Breakfast, Lunch, Snack, and Dinner. Explicit
  user context wins; otherwise household-local request time determines the
  group.

---

## 14. Flow: Switch Active Household Member

### User Intent

The user wants to act as another household member.

### Expected Experience

1. User changes active member context.
2. Personal nutrition data changes to that member.
3. Shared household plan, pantry, and grocery state remain the same.
4. Future personal logs apply to the new active member.

### Functional UX Requirements

- Active member state must be obvious before logging food.
- Switching active member should not reset shared household state.
- The user should understand which data is personal and which data is shared.

---

## 15. Flow: Handle Ambiguity and Corrections

### Common Ambiguities

- "Tomorrow" when viewing a future meal plan.
- "Dinner" without specifying date.
- "Add milk" without quantity.
- "I ate rice" without portion size.
- "Make it healthier" without specific target.
- "Order this" while provider integration is not configured.

### Expected Experience

Kitch should:

- Infer safely when the likely intent is obvious.
- Ask a short clarification when the risk of doing the wrong thing is high.
- Confirm destructive or external-facing actions.
- Let users correct mistakes conversationally.

### Functional UX Requirements

- Corrections should update the underlying state, not only the chat transcript.
- Users should not need to understand agent/tool internals.
- If the app cannot complete an action, it should explain what was completed and what remains unresolved.

---

## 16. Cross-Flow State Rules

### Shared Household State

These should be shared across all members:

- Dated meal plan, shared across calendar weeks.
- Household timezone and the currently visible Monday-Sunday range.
- Pantry and fridge stock.
- Grocery requirements.
- Household brand preferences.
- Household size.
- Dietary planning preference.

### Personal State

These should be individual:

- Active conversation context.
- Daily macro diary.
- Personal calorie and macro progress.

### Deferred Future State

These are future product areas:

- Multi-household registration.
- Auth-backed household membership.
- Blinkit MCP cart insertion.
- Richer provider substitution review.

---

## 17. Designer Interaction Checklist

The UI/UX designer should define interactions for:

- Starting a new dated plan or weekly plan.
- Replacing an exact date range without affecting other weeks.
- Understanding the plan's date range.
- Navigating previous/next weeks and returning to Today.
- Distinguishing today, past, planned, and empty dates.
- Asking what is planned for a specific day or meal.
- Changing one meal.
- Replacing an ingredient or recipe across the plan.
- Updating pantry from text, manual input, or photo.
- Reviewing uncertain scanned pantry results.
- Compiling groceries from plan and pantry.
- Reviewing grocery items before provider preparation.
- Seeing brand substitutions during provider preparation.
- Saving, changing, and deleting brand preferences.
- Logging food by text or photo.
- Correcting nutrition estimates.
- Switching active member context.
- Understanding shared versus personal data.
- Handling failed agent actions or failed saves.

---

## 18. UX Tone

Kitch should feel:

- Practical rather than decorative.
- Conversational but not verbose.
- Helpful without hiding important uncertainty.
- Household-aware.
- Trustworthy around saved state and external actions.
- Quick enough for everyday kitchen use.

Users should come away knowing:

- What Kitch understood.
- What Kitch changed.
- What Kitch saved.
- What still needs review.
- Whether an action affected the household or only one person.
