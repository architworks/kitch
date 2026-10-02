# Known Issues and Optimizations

This document contains currently reproducible product and system issues,
deliberately deferred optimizations, and architectural decisions that must not
be accidentally reversed. Resolved, obsolete, and unverified historical
entries are removed rather than kept as compatibility history.

Latest verification source:
[Sections 7–8 functional test report](./test_artifacts/sections_7_8_agent_driven_instamart_2026-08-16_17-48-36_IST/report.md).

## Decisions to preserve

### AD-001: Household preference memory remains flexible text memory

- **Status:** Intentional
- **Applies to:** Food preferences, allergies, exclusions, brand preferences,
  pack preferences, and similar household guidance

Kitch intentionally stores these memories as flexible natural-language ADK
memory rather than converting them into deterministic product-catalogue rules
or a rigid preference table. Real catalogues express equivalent products,
brands, packs, quantities, and substitutions inconsistently; an agent must be
able to interpret the preference in the context of live search results.

The current local implementation uses the shared process-local
`InMemoryMemoryService` under `app_name="kitch"` and
`user_id="shared_household"`. Entries are text events with lightweight source
tags such as `food_preference:` and `ordering_preference:`. The planned Vertex
AI memory migration should make this memory durable without changing it into a
relational product-rule system.

Retrieval relevance and agent reasoning may be improved, but a fix must not
replace flexible memory with deterministic catalogue matching.

### AD-002: Do not add a grocery-ordering agent hierarchy prematurely

- **Status:** Intentional for the current provider scope

Kitch does not currently need an additional `grocery_ordering_agent`, a tree of
provider sub-agents, or more provider-mutation tools on `kitch_coordinator`.
Chat-native grocery changes belong to the existing grocery specialist. Provider
cart projection belongs to the provider agent invoked by the Groceries UI sync
workflow.

Reconsider that conversational hierarchy only when there is demonstrated
routing complexity from multiple active providers. It must not replace the
deterministic service boundary for leases, durable drafts, approval, payment,
or UI-only checkout.

### AD-003: UI and explicit chat may invoke the same provider-cart workflow

- **Status:** Intentional for the current product flow

Chat may add, update, or remove native Kitch cart intent through the existing
grocery specialist without synchronizing a provider. The Groceries UI sync
action passes the complete selected native-cart intent to the operation-scoped
Instamart agent. An explicit chat request to move, sync, refresh, or modify the
Instamart cart may invoke that same agent through the existing
`sync_instamart_cart_tool` bridge.

This makes the native cart a conduit between recipes, direct chat changes, and
provider ordering without making its UI a mandatory intermediate screen. The
single coordinator sync bridge is retained; additional edge-case commerce tools
are rejected. Final review and checkout remain UI-only.

## Known issues

## KI-001: Provider-cart wording is routed and reported inconsistently

- **Status:** Routing fix implemented; functional verification pending
- **Area:** Coordinator routing / agent orchestration
- **Reported:** 2026-08-16
- **Severity:** High

### Summary

The coordinator does not reliably distinguish native-cart mutation from the
UI-only provider synchronization boundary.

### Reproduction

Ask Kitch:

```text
Move my grocery list to Instamart.
```

### Previously observed behavior

Kitch claimed that the native grocery list was updated and returned an
`UPDATE_RECIPE_GROCERY` action. It did not synchronize the Instamart cart or
return `UPDATE_PROVIDER_CART`.

### Expected behavior

- A request to add, update, or remove a grocery item should route to the
  existing grocery specialist and change only the native cart.
- A request to move or synchronize the complete native cart to Instamart
  should call the existing `sync_instamart_cart_tool` and reach the Instamart
  agent.
- A combined request should apply the standalone native change and then use the
  same sync bridge; it must not require another coordinator tool.

### Impact

- Explicit user intent is sent to the wrong domain specialist.
- The response can claim success for an operation that did not occur.
- The frontend refreshes the wrong product state.

### Resolution criteria

- Standalone item mutations route to the existing native grocery specialist.
- The coordinator retains one explicit Instamart synchronization bridge and
  does not accumulate additional provider-specific edge-case tools.
- Provider success text and `UPDATE_PROVIDER_CART` are emitted only after a
  confirmed provider-cart result, whether synchronization originated in chat
  or the UI.
- Native grocery planning and provider-cart synchronization remain distinct
  intents.

## KI-002: Instamart matching fails on valid variants and can apply an unrelated preference

- **Status:** Open
- **Area:** Instamart cart agent / preference retrieval / catalogue matching
- **Reported:** 2026-08-16
- **Severity:** High

### Summary

The Instamart agent does not reliably select the best reasonable product from
valid Swiggy search results. Preference retrieval can also return a preference
for the wrong native item and corrupt the subsequent search.

### Reproduction A: egg pack selection

Synchronize this native item:

```text
eggs — 12 pieces
```

Swiggy returned several orderable variants, including a directly suitable
`12 Pieces` product. Kitch still marked eggs unresolved with the reason that no
unambiguous variant was available.

### Reproduction B: preference leakage

Store these preferences during the same backend process:

```text
For bread, always get Baker's Dozen whole wheat.
I prefer Amul butter over any other brand.
```

Then synchronize:

```text
butter — 1 pack
```

The butter row received the bread preference as its search instruction. The
agent searched Baker's Dozen products instead of Amul butter and left butter
unresolved. Conversational recall still correctly reported that Amul was the
preferred butter brand.

### Suspected causes

- `search_ordering_preferences_tool` returns semantically retrieved memories
  without enforcing that a preference belongs to the requested native item.
- The agent treats normal catalogue ambiguity as a reason to omit an item even
  when one candidate clearly satisfies the requested quantity and unit.
- The structured agent report does not require a concrete explanation for why
  every higher-ranked valid candidate was rejected.

### Impact

- Orderable products are unnecessarily omitted from the provider cart.
- A preference for one product category can contaminate another category.
- Users cannot trust stated brand and pack-size preferences to be applied.

### Resolution criteria

- Household preferences remain flexible text memory. Retrieval must preserve
  the original preference text and enough context for the agent to decide
  whether it actually applies to the current native item.
- The agent must ignore a retrieved preference when its subject does not match
  the current product intent; retrieval similarity alone is not an instruction
  to apply it.
- `12 pieces`, `1 dozen`, `2 × 6`, and equivalent packs are evaluated by total
  fulfilled quantity rather than surface wording.
- Multiple search results are treated as normal; the best reasonable orderable
  candidate is selected unless a specific incompatibility exists.
- Tests cover eggs, bread, butter, unrelated preference isolation, multiple
  brands, and multiple pack sizes.

## KI-003: Instamart search-candidate price metadata contains corrupted minor-unit values

- **Status:** Open
- **Area:** Instamart search-result normalization / agent result schema
- **Reported:** 2026-08-16
- **Severity:** Medium

### Summary

Candidate-level `price_minor` values recorded during product search can be
orders of magnitude larger than the real product price.

Kitch represents INR in paise, so:

```text
₹70 = 7,000 minor units
₹145 = 14,500 minor units
```

For the confirmed Baker's Dozen bread, the final provider cart correctly
returned `price_minor: 7000`, while its earlier candidate metadata contained
`price_minor: 70701751`. Egg candidates contained similarly impossible values,
including `145110920`.

### Scope

- The confirmed provider cart, displayed ₹70 line price, fees, and ₹141 payable
  total were correct during the test.
- The defect is currently isolated to search-candidate metadata.
- It is not evidence that Swiggy returned an incorrect final cart total.

### Suspected cause

Candidate pricing is being copied or interpreted from loosely structured MCP
search output without a strict money schema. The agent-generated unresolved-item
report can preserve malformed values even though the confirmed-cart normalizer
later reads the correct provider price.

### Impact

- Price-based candidate ranking may become unreliable if it consumes this
  metadata.
- Debug output and replacement reasoning show nonsensical prices.
- Future UI use of candidate prices could expose incorrect amounts.

### Resolution criteria

- Candidate prices come from an explicit provider money field with known
  currency and scale, never a model-generated or multi-value display string.
- Invalid or ambiguous candidate prices are stored as unavailable rather than
  guessed.
- A selected SKU's candidate price is consistent with its confirmed cart price,
  allowing only provider-authorized price changes.
- Provider totals remain authoritative for fees, discounts, taxes, and payable
  amount.

## KI-004: Native-cart drift can be reclassified as a ready provider draft

- **Status:** Open
- **Area:** Durable checkout draft / order safety
- **Reported:** 2026-08-16
- **Severity:** High

### Summary

Deleting a native item after it has been synchronized correctly resets payment
and acknowledgement, but a subsequent draft read can reclassify the stale
provider draft as `ready` and set `can_place_order: true`.

### Reproduction

1. Synchronize a native bread row to Instamart.
2. Select a returned payment method and acknowledge the review.
3. Delete the native bread row.
4. Read the durable Instamart checkout draft.

### Observed behavior

The draft retained the deleted native item ID and confirmed bread line. Payment
and acknowledgement were cleared, but the backend returned:

```json
{
  "status": "ready",
  "can_place_order": true,
  "order_blockers": []
}
```

Chrome initially rendered the stale bread review alongside the current native
egg cart. The frontend separately recognized that the review was stale and kept
payment, acknowledgement, and order controls disabled; a later state refresh
removed the review from the page.

### Suspected cause

`invalidate_draft_for_native_drift()` saves a blocked draft, but
`refresh_checkout_eligibility()` subsequently recomputes eligibility from the
old stored native snapshot and provider result. That recomputation removes the
native-drift blocker and restores the ready state.

### Impact

- Backend draft state contradicts the authoritative native cart.
- Frontend safety currently compensates for an unsafe backend representation.
- Another API consumer could incorrectly treat the stale provider projection as
  orderable.

### Resolution criteria

- Native-cart drift produces a durable invalidated state that generic
  eligibility refresh cannot overwrite.
- A stale draft never returns `can_place_order: true`, a confirmation token, or
  an empty blocker list.
- Resynchronization must use the current native selection before payment and
  acknowledgement can be restored.

## KI-005: Chat standalone native-cart mutation requires functional verification

- **Status:** Fix implemented; functional verification pending
- **Area:** Chat commerce intent / native-cart authority
- **Reported:** 2026-08-16
- **Severity:** Medium

### Summary

The grocery specialist previously required every cart row to come from a recipe
artifact. It now has a dedicated specialist-owned mutation capability for
standalone manual native-cart rows. The existing Instamart sync bridge also
accepts native changes for an explicit combined add/update/remove-and-sync
request.

### Reproduction

With no matching chocolate row in the native cart, ask Kitch:

```text
Add one Dairy Milk chocolate to my grocery cart so I can order it from Instamart.
```

### Implemented execution boundary

`recipe_grocery_planner` calls `modify_native_grocery_cart_tool` for standalone
native-only requests. `kitch_coordinator` keeps the existing
`sync_instamart_cart_tool`; for an explicit combined Instamart request, the same
tool applies the declared native changes before invoking
`GroceryCheckoutService` and the Instamart agent with the resulting complete
eligible native cart.

### Expected behavior

Native-only chat requests must report only the native change. Explicit
Instamart requests may report provider success only after the provider cart is
confirmed. Checkout remains unavailable from chat.

### Resolution criteria

- Functional chat tests confirm that the existing grocery specialist adds,
  updates, and removes standalone native rows without fabricating a recipe.
- Explicit and combined Instamart chat tests reliably use the existing sync
  bridge without adding another coordinator tool.
- Chat reports `UPDATE_GROCERY_CART` only after the native write succeeds and
  explicitly distinguishes native-only from provider synchronization results.
- Chat and UI synchronization emit `UPDATE_PROVIDER_CART` only after confirmed
  `update_cart` and `get_cart` results.

## Deferred optimizations

### OPT-001: Remove provider-ID branching when another agent-driven provider is added

- **Status:** Deferred until a second agent-driven provider is actively being
  implemented
- **Priority:** No current refactor

`GroceryCheckoutService` currently contains an Instamart-specific execution
branch and directly owns `InstamartCartAgentService`. This is acceptable for the
current implementation, but another agent-driven provider would otherwise add
more central branching.

When that concrete need arises, introduce a provider-registered cart executor
contract so the service selects an agentic or deterministic executor without
checking provider IDs. Do not add a speculative `grocery_ordering_agent`,
provider-agent hierarchy, or plugin framework before that need exists.
