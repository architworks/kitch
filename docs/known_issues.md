# Known Issues

This document contains only currently reproducible product and system issues.
Resolved, obsolete, and unverified historical entries are removed rather than
kept as compatibility history.

Latest verification source:
[Sections 7–8 functional test report](./test_artifacts/sections_7_8_agent_driven_instamart_2026-08-16_17-48-36_IST/report.md).

## KI-001: Explicit Instamart cart requests are routed to the wrong specialist

- **Status:** Open
- **Area:** Coordinator routing / agent orchestration
- **Reported:** 2026-08-16
- **Severity:** High

### Summary

The coordinator does not reliably route an explicit grocery-provider cart
request to `instamart_cart_agent`.

### Reproduction

Ask Kitch:

```text
Move my grocery list to Instamart.
```

### Observed behavior

Kitch claimed that the native grocery list was updated and returned an
`UPDATE_RECIPE_GROCERY` action. It did not synchronize the Instamart cart or
return `UPDATE_PROVIDER_CART`.

### Expected behavior

The coordinator should invoke the Instamart cart synchronization workflow,
wait for its confirmed `get_cart` result, and return `UPDATE_PROVIDER_CART`.
Ordinary grocery-planning requests should continue to affect only the native
Kitch cart.

### Impact

- Explicit user intent is sent to the wrong domain specialist.
- The response can claim success for an operation that did not occur.
- The frontend refreshes the wrong product state.

### Resolution criteria

- Explicit provider-sync requests route only to the selected provider cart
  agent.
- Provider success text and `UPDATE_PROVIDER_CART` are emitted only after a
  confirmed provider-cart result.
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

- Preferences are stored and retrieved using an exact normalized item key,
  with semantic memory used only as a secondary signal.
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
