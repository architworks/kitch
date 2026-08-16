# Swiggy Instamart Functional Test — Section 7

- Tested: `2026-08-16`, Asia/Kolkata
- Environment: local frontend/backend, live Swiggy OAuth and cart, Supabase
- Model: `gemini-3.5-flash-lite`
- Safety: Instamart cart replacement approved; **no order placed**
- Browser automation: Chrome DevTools MCP, desktop and narrow viewport

## Outcome

**0 PASS, 2 FAIL, 2 PARTIAL**

| Scenario | Status | What worked | What was unsuccessful |
| :--- | :---: | :--- | :--- |
| 7.1 Provider, connection, address | **FAIL** | Swiggy was selected and connected; Zepto/Blinkit stayed disabled; no Zepto auth tab opened | OAuth callback query data is logged by default, and all 10 addresses render as indistinguishable “Saved address” options |
| 7.2 Cart sync and reconciliation | **PARTIAL** | Live sync/revalidation, safe unresolved-item handling, provider fees/total, images, and durable draft worked | Confirmed line still renders as generic “Instamart product” with no line price |
| 7.3 Revalidation, repair, switching | **FAIL** | Stale entry revalidated automatically, replaced coconut milk, showed changes/last checked, and reset approval | After reload the UI said 32 items selected while the restored draft contained only 2 native item IDs; provider switching was unavailable with alternatives disabled |
| 7.4 Payment and checkout safety | **PARTIAL** | Only returned UPI methods appeared; payment/acknowledgement could be set; blocked order stayed disabled; reload reset approval; no order was placed | The approval does not enumerate the exact address, products, quantities, total, and chosen payment; order-time browser recovery could not be exercised from the blocked draft |

## Immediate Findings

| Priority | Finding | Impact |
| :---: | :--- | :--- |
| **High** | OAuth callback query parameters appear in default access logs | Authorization codes and state should not be logged |
| **High** | Reloaded native selection says 32 selected while the durable draft contains 2 selected IDs | The visible native intent and provider projection disagree |
| **High** | Confirmed Instamart lines normalize to `Instamart product` and omit cart-line pack/price | The user cannot review the exact products being approved |
| **Medium** | Saved addresses render with the same generic label | Users cannot identify which delivery address they are approving |
| **Medium** | Narrow viewport has horizontal overflow and two-column sidebar cards | Mobile checkout requires horizontal scrolling |

## 7.1 — Provider Selection, Connection, and Address — FAIL

**Unsuccessful:** The connection works, but the OAuth callback logging violates the credential-safety requirement.

- Action: Loaded provider registry, connected the household Swiggy account,
  completed PKCE OAuth, loaded addresses, tested preference persistence, sent an
  invalid OAuth state, and checked disabled Blinkit behavior.
- Observed:
  - Instamart changed from `not_connected` to `connected`.
  - Ten saved addresses loaded with a capability version.
  - Connection and address access survived a FastAPI restart.
  - Invalid/replayed state returned HTTP `403` with `oauth_state_invalid`.
  - Blinkit remained unavailable and returned `provider_not_available`.
  - Access token and PKCE verifiers are stored as Fernet ciphertext.
  - Dynamic-registration storage contains no client secret, access token, or
    refresh token.
- Failure: Default Uvicorn access logs include the callback query string. The
  backend was restarted with `--no-access-log` only as a temporary test-time
  mitigation.
- Chrome MCP confirmed Swiggy selected, connected, and store-ready. Zepto was
  disabled, Blinkit was disabled/Coming soon, and only the Kitch page remained
  open—no Zepto authentication tab appeared.
- UI failure: all ten address options display only `Saved address`, so the
  selected destination cannot be distinguished in the workflow.

## 7.2 — Cart Synchronization and Reconciliation — PARTIAL

**Unsuccessful:** The synchronization behavior is acceptable, but the confirmed cart line still lacks an exact product name and line price.

- Action: Selected Chia Seeds, Coconut Milk, and Eggs. Eggs was temporarily
  marked pantry-covered. With explicit approval, synchronized using the first
  saved Swiggy address and read the confirmed Instamart cart back.

| Live result | Value |
| :--- | :---: |
| Native rows selected | 3 |
| Pantry-covered rows excluded | 1 — Eggs |
| Rows exported | 2 |
| Reconciled native rows | 1 — Coconut Milk |
| Unresolved native rows | 1 — Chia Seeds |
| Confirmed provider-cart lines | 2 — Coconut Milk + Swiggy freebie |
| Provider total | **₹143** |
| Payment options returned | 7 |
| Can place order | **No** |

- Chia Seeds remained unresolved because Swiggy did not return one unambiguous
  orderable variant. This is acceptable: Kitch correctly refused to guess and
  kept the item visible as unresolved.
- Swiggy added a promotional `FREEBIE_…` line. Provider-added promotional items
  are acceptable and should remain visible without being treated as native
  grocery intent.
- Swiggy returned ₹12 handling, ₹20 small-cart, ₹30 delivery-partner, and ₹9
  GST/charges components. Kitch used Swiggy's ₹143 total and did not invent a
  subtotal.
- Images were present. Chrome showed the confirmed line as `Instamart product`,
  with quantity 1 and pack 400 ml, but price and subtotal as `Unavailable`.
- The checkout draft contains a snapshot hash, validation time, and blockers.
- Eggs was restored to its original native-cart state.
- Chrome showed provider-returned handling, delivery-partner, and GST charges
  plus the authoritative total. It did not fabricate a subtotal.

## 7.3 — Durable Revalidation, Repair, and Switching — FAIL

**Unsuccessful:** Reload restored a two-item checkout draft while the native-cart UI claimed 32 items were selected, so the authoritative intent and provider projection were inconsistent.

- Opening Groceries with the stale draft issued `GET /checkout` followed by
  `POST /checkout/revalidate`; revalidation returned HTTP 200.
- Revalidation replaced Dabur coconut milk with Real Thai coconut milk, changed
  the provider total from ₹143 to ₹218, displayed replacement/change details
  and **Last checked**, and reset payment and acknowledgement.
- Chia Seeds remained visible as unresolved and kept `can_place_order=false`.
- The repaired draft survived a full browser reload. A read-back confirmed 2
  selected native IDs, 1 provider-cart line, and 1 unresolved row.
- Failure: after that reload the native-cart header displayed **32 selected for
  Swiggy Instamart**, while the restored durable draft still contained only IDs
  `173` and `175`.
- Automated tests passed for native-cart drift invalidation, replacement/change
  handling, and provider/environment operation leases.
- Zepto and Blinkit were intentionally disabled, so cross-provider switching
  could not be exercised in this browser run.

## 7.4 — Payment Approval, Checkout Safety, and Recovery — PARTIAL

**Unsuccessful:** Payment safety is enforced, but the final acknowledgement does not spell out the exact address, line items, quantities, ₹218 total, and selected payment method.

- Recorded-provider tests confirmed:
  - UPI identifiers are passed through unchanged.
  - COD is used only when UPI is absent and COD is returned.
  - A changed cart stops before checkout.
  - Ambiguous checkout calls checkout once, checks order history, persists the
    possible provider order, marks the result unknown, and blocks retry.
  - Unchanged fixture order outcomes persist.
- Chrome exposed seven provider-returned UPI methods and no COD option. Selecting
  `gpay://upi/` and acknowledging produced two successful draft PATCH requests.
- The unresolved item kept **Place order with Swiggy Instamart** disabled before
  and after acknowledgement.
- A full reload issued a safety PATCH that cleared both payment and
  acknowledgement; the durable cart, blocker, fees, and ₹218 total remained.
- The acknowledgement label names Swiggy but only says `Saved address` and does
  not enumerate the exact products, quantities, total, or selected method.
- No checkout endpoint was called and no order was placed. The 409/order-recovery
  path remains fixture-tested only because the live draft was intentionally
  blocked.

## Automated Checks

| Suite | Result |
| :--- | :---: |
| Instamart adapter | **12/12 passed** |
| Provider OAuth security | **5/5 passed** |
| Checkout service safety | **3/3 passed** |
| Persistence and migration contract | **18/18 passed** |
| Frontend lint | **Passed** |
| Chrome MCP desktop/narrow checkout | **Completed; issues recorded above** |

The first test-launch attempt omitted `backend/.env.local` and failed at import
with `SUPABASE_URL is required`. Rerunning with the local environment loaded
passed all 38 assertions; this was a test-runner invocation issue, not a product
failure.

## State After Testing

- Real Instamart cart after stale repair: one Real Thai Coconut Milk product
- Durable checkout draft: present and blocked
- Native Eggs pantry flag: restored
- Zepto: temporarily disabled; no authentication tab opened
- Order placed: **No**
- Backend and frontend: running
- Structured evidence: [results.json](./results.json)
