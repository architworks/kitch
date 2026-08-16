# Functional Test Report — Sections 7 and 8

- Run: `2026-08-16 17:48–18:05 IST`
- Environment: local frontend/backend, live Supabase and Swiggy Instamart
- Safety: provider cart changed; **no order placed**
- Browser: Chrome DevTools MCP, desktop and narrow viewport

## Summary

**2 PASS · 3 FAIL · 2 PARTIAL**

| Scenario | Result | One-line outcome |
| :--- | :---: | :--- |
| 7.1 Provider, connection, address | **PARTIAL** | Chrome confirmed provider cards, connection, and automatic address selection; a fresh OAuth/reconnect cycle was not run. |
| 7.2 Cart synchronization | **FAIL** | A valid 12-piece egg result was rejected, chat sync did not sync Instamart, and search-candidate prices were mis-scaled. |
| 7.3 Revalidation and drift | **FAIL** | Removing the selected native item reset approval but left its provider draft `ready` and `can_place_order: true`. |
| 7.4 Payment and checkout safety | **PARTIAL** | Payment validation, browser locking, and chat checkout denial worked; live order preflight was intentionally not exercised. |
| 8.1 Bread preference | **PASS** | The preference was recalled and selected The Baker's Dozen bread in the confirmed Instamart cart. |
| 8.2 Category exclusions | **PASS** | Milk, apples, and carrots were included; cereal and cookies were excluded. |
| 8.3 Butter preference | **FAIL** | Recall said Amul, but the cart agent applied the bread preference to butter and searched Baker's Dozen products. |

## Immediate defects

1. **Instamart preference lookup leaks across items.** Butter received the bread preference as its `search_name`.
2. **The egg matcher still rejects reasonable ambiguity.** Swiggy returned an orderable `12 Pieces` variant, but the agent left eggs unresolved.
3. **Native-cart drift does not make the draft non-orderable.** The deleted bread row remained in a `ready` provider draft with no blockers.
4. **Explicit chat sync is misrouted.** “Move my grocery list to Instamart” returned a native/recipe-grocery success message and `UPDATE_RECIPE_GROCERY`, not `UPDATE_PROVIDER_CART`.
5. **Candidate price normalization is broken.** Search candidates contained values such as `145110920` minor units, while the confirmed bread line correctly normalized to `7000` minor units.
6. **The narrow layout overflows horizontally.** Chrome reported a document width larger than the viewport around the provider cart table.

## Scenario evidence

### 7.1 — Provider Selection, Connection, and Address — PARTIAL

- Action: Read `/api/grocery/providers` and Instamart addresses.
- Observed: Instamart was enabled, `connected`, and `local`; Zepto was disabled; Blinkit was disabled with `coming_soon`. Fourteen saved addresses had opaque IDs and human-readable labels.
- Chrome: Swiggy Instamart was selected, Zepto was visibly disabled, Blinkit was disabled with **Coming soon**, the address list loaded without another button, and the first saved address was selected automatically.
- Missing: the already-connected account was reused, so a fresh OAuth, reconnect, and disconnect cycle was not performed.

### 7.2 — Provider Cart Synchronization and Reconciliation — FAIL

- UI-equivalent action: synchronized native row `eggs — 12 pieces` with the instruction: “Add the best reasonable match for 12 eggs… do not add 12 packs.”
- Observed: Swiggy returned orderable 6-, 10-, 12-, 24-, and 30-piece variants, including an available `12 Pieces` pack. Kitch returned HTTP 200 with a blocked draft and zero confirmed items.
- Preference control: a temporary `whole wheat bread — 1 loaf` row synchronized successfully to **The Baker's Dozen Zero Maida Whole Wheat Bread**, with image, 400 g pack, ₹70 line value, provider fees, ₹141 payable total, and seven UPI options.
- Chat action: `Move my grocery list to Instamart.`
- Observed: chat claimed the native cart was updated and returned `UPDATE_RECIPE_GROCERY`; it did not invoke the provider-cart workflow or return `UPDATE_PROVIDER_CART`.
- Chrome: the bread review showed its exact product name, image, requested native row, ₹70 price/subtotal, quantity 1, 400 g pack, provider fees, and ₹141 provider total.
- Responsive issue: the provider-cart layout overflowed horizontally in the narrow viewport.
- Frontend static checks: lint and production build passed.

### 7.3 — Durable Revalidation, Repair, and Provider Switching — FAIL

- Action: explicitly revalidated the blocked egg draft.
- Observed: HTTP 200, `changed: false`, the same unresolved egg candidates, and no checkout attempt.
- Action: created a ready bread draft, selected a payment option, acknowledged it, then deleted the temporary native bread row.
- Observed: payment and acknowledgement reset, but the durable draft still selected deleted ID `181`, retained the bread provider line, reported `status: ready`, `can_place_order: true`, and no blockers.
- Chrome after reload: the native cart showed one egg row while the restored provider review showed the deleted bread line. The UI did at least mark the review stale, disable payment/acknowledgement/order controls, and require refresh. A later chat-state refresh removed the stale review from the page.
- Provider isolation: the disabled Zepto integration was not invoked. Cross-provider switching was unavailable because Zepto and Blinkit were disabled.

### 7.4 — Payment Approval, Checkout Safety, and Recovery — PARTIAL

- Invalid action: selected `invented-payment`.
- Observed: HTTP 422 with `payment_method_invalid`.
- Valid action: selected provider-returned `gpay://upi/` and acknowledged review.
- Observed: HTTP 200; selection and acknowledgement persisted.
- Chat action: `Place my Instamart order now.`
- Observed: Kitch refused to place the order and returned no mutation action.
- Chrome: a stale review kept the seven returned UPI methods, acknowledgement, and **Place order** control disabled. The page visibly stated that only the final button can place an external order.
- Automated safety checks: 5 commerce-policy, 12 draft, 4 checkout-API, and 7 Instamart-adapter tests passed.
- Missing: no live place-order request was made, so order-time 409/recovery behavior remains automated-test evidence only. **No order was placed.**

### 8.1 — Bread Preference — PASS

- Prompt: `For bread, always get Baker's Dozen whole wheat.`
- Recall: `What bread should you choose when shopping for our household?`
- Observed: chat recalled The Baker's Dozen whole wheat. Instamart then confirmed the matching Baker's Dozen product in its cart with 0.95 confidence.

### 8.2 — Category Exclusions — PASS

- Prompt: `Never add cereals or cookies to my grocery list - only dairy, fruits, and veggies.`
- Follow-up: `Without changing or saving the cart, tell me which of these you would put on our grocery list: milk, apples, carrots, cereal, and cookies.`
- Observed: milk, apples, and carrots were included; cereal and cookies were excluded. No cart mutation action was returned.

### 8.3 — Butter Preference — FAIL

- Prompt: `I prefer Amul butter over any other brand.`
- Recall: `Which butter brand do I prefer?`
- Observed: chat correctly recalled Amul butter, and Chrome displayed that reply in the frontend conversation.
- Provider application: temporary `butter — 1 pack` synchronization used `For bread, always get Baker's Dozen whole wheat.` as the butter search preference. Only Baker's Dozen candidates were returned, so butter remained unresolved.

## Checks and final state

| Check | Result |
| :--- | :---: |
| Backend health/readiness | **PASS** |
| Commerce/checkout automated assertions | **28/28 PASS** |
| Frontend lint | **PASS** |
| Frontend production build | **PASS** |
| Chrome MCP desktop/narrow | **COMPLETED — functional defects above** |
| Order placed | **NO** |
| Native cart cleanup | **PASS — original eggs row only** |
| External Instamart cleanup | **NOT PERFORMED — clearing a replace-only provider cart could remove unrelated user items** |

The external Instamart cart still contains the test Baker's Dozen bread line. The test did not clear it because Instamart exposes full-cart replacement rather than safe per-line removal, and clearing the whole cart was not performed without separate confirmation.

Structured evidence: [results.json](./results.json)
