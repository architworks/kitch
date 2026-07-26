# Kitch UX User Flows and Functional Experience Brief

This document is for UI/UX design planning. It describes what users need to accomplish with Kitch, how the experience should behave, and what interactions need to be designed.

It intentionally does not prescribe screens, page layouts, components, or visual treatments.

---

## 1. Product Idea

Kitch is an AI-powered household meal planning, nutrition logging, pantry tracking, and grocery preparation assistant.

The app is designed for a shared household where multiple people eat from the same meal plan and pantry, but still track their own personal nutrition. In the current prototype, the household is prefilled with three members: Archit, Anubhav, and Naman.

Kitch should feel like a practical kitchen companion:

- It helps the household decide what to eat.
- It creates a weekly plan for the coming week.
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

Provider cart sync and order placement are separate. If the user asks Kitch to add groceries to Zepto, Kitch may sync the native cart into Zepto. Placing the order still requires a final explicit UI approval.

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

- Shared weekly meal plan.
- Shared pantry and fridge stock.
- Shared grocery preparation.
- Shared brand and shopping preferences.
- Household size for scaling planned food.

---

## 4. Primary User Goals

Users should be able to:

1. Create a weekly meal plan for the household.
2. Understand what is planned for a specific day or meal.
3. Modify one meal without damaging the rest of the plan.
4. Update pantry stock manually, conversationally, or from a fridge photo.
5. Generate a grocery list from the current plan and pantry.
6. Sync eligible grocery rows to Zepto for review.
7. Save brand preferences for future grocery preparation.
8. Log personal food intake from text or a plate photo.
9. See personal daily nutrition progress.
10. Switch active member context without mixing personal logs.

---

## 5. Flow: Create a Weekly Household Meal Plan

### User Intent

The user wants Kitch to decide what the household should eat for the next week.

Example prompts:

- "Create a meal plan for next week."
- "Plan balanced meals for the three of us."
- "Make next week Indian and high protein."
- "Give us a keto meal plan for the coming week."

### Expected Experience

1. The user expresses the planning request naturally.
2. Kitch understands the current date and identifies the upcoming planning window.
3. Kitch generates a Monday-Sunday plan for the coming week.
4. Kitch accounts for household size, diet preference, and known preferences.
5. Kitch saves the plan as structured household state.
6. Kitch replies with a readable summary including exact dates.
7. The visible plan state updates to match what Kitch said.

### Functional UX Requirements

- The date range must be explicit.
- Each planned day should be associated with a date.
- The plan should be clearly household-wide, not personal to one member.
- If the user asks for "next week" on a weekend, the plan should start on the upcoming Monday.
- If the user gives vague constraints, Kitch should make reasonable choices rather than force a long setup.
- If the user gives incompatible constraints, Kitch should ask a clarifying question.

### Important States

- No plan exists yet.
- Plan generation is in progress.
- Plan successfully saved.
- Plan partially failed to save.
- Existing plan is being replaced.
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
- "Next Monday" should refer to the upcoming planning week when the user is discussing the generated plan.
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
- Multi-meal replacements should clearly list all affected days.
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

1. The user provides items through text, manual entry, or photo.
2. Kitch extracts item names, amounts, and units where possible.
3. Kitch updates the shared household pantry.
4. Kitch confirms what was added, updated, or removed.
5. Future grocery preparation subtracts available stock.

### Functional UX Requirements

- Pantry is shared across the household.
- Pantry updates should never be personal to only one member.
- Kitch should handle approximate quantities when exact amounts are unknown.
- When confidence is low, Kitch should ask for confirmation or mark the estimate clearly.
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

1. Kitch reads the current weekly meal plan.
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

The native grocery cart is structured backend state. The Groceries page supports item review, manual rows, quantity edits, row exclusion for Zepto sync, and provider review. Provider substitution review should continue to improve as Zepto/Blinkit integrations mature.

---

## 10. Flow: Sync Groceries to Zepto

### User Intent

The user wants to move the native Kitch grocery cart into Zepto.

Example prompts:

- "Add this to Zepto."
- "Put tomorrow's groceries in Zepto."
- "Plan grocery for the next two days and add it to Zepto."

### Expected Experience

1. User requests provider preparation.
2. Kitch uses the native cart as the source of truth.
3. Kitch excludes rows the user has removed from Zepto sync and rows covered by pantry stock.
4. Kitch applies brand preferences where known.
5. Kitch clears/replaces the Zepto cart.
6. Kitch selects Zepto products and adds them to the Zepto cart.
7. The app shows the actual Zepto cart, unavailable items, and address/payment review state.
8. The user must click a final approval button before any order is placed.

### Functional UX Requirements

- The experience must not imply that an actual order was placed.
- The experience may indicate that the Zepto cart changed only after sync succeeds.
- The user should see enough information to trust the actual Zepto cart contents.
- Brand substitutions should be visible.
- Order placement must require explicit user approval.
- Auth, payment, address, and OTP issues should surface as recoverable states.

### Current Product Boundary

Zepto cart sync is implemented behind the MCP adapter, but it depends on external Zepto MCP auth. Blinkit live cart insertion is not implemented.

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
3. Kitch stores the preference in explicitly ephemeral household memory.
4. Kitch confirms the preference in plain language without implying that it
   survives a backend restart.
5. Future grocery preparation uses the preference.

### Functional UX Requirements

- Brand preferences are household-level unless the user explicitly says they are personal.
- Kitch should confirm what it remembered.
- If a preference is ambiguous, Kitch should ask what item or category it applies to.
- Users should be able to overwrite or remove old preferences.
- Preferences should influence grocery preparation without requiring strict form entry.

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
3. Kitch logs the meal to the active member.
4. Kitch confirms the estimated nutrition.
5. The active member's daily nutrition state updates.

### Functional UX Requirements

- Food logs are individual, not household-wide.
- The active member context must be clear.
- Kitch should not log a meal for the wrong person.
- Users should be able to correct meal name, quantity, or estimated macros.
- Kitch should communicate uncertainty in estimates.
- Fridge scans and plate scans must be clearly differentiated.

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
4. User can clear or correct logs when needed.

### Functional UX Requirements

- Nutrition summaries should be personal to the active member.
- Switching members should change personal logs without changing household meal plan or pantry.
- Kitch should make clear whether it is answering for one person or the household.
- Clearing logs should affect only the active member.

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

- Weekly meal plan.
- Planning week date range.
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
- Persistent Vertex AI memory.
- Blinkit MCP cart insertion.
- Richer provider substitution review.

---

## 17. Designer Interaction Checklist

The UI/UX designer should define interactions for:

- Starting a new weekly plan.
- Replacing an existing plan.
- Understanding the plan's date range.
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
