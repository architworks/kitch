# Section 8 — Ordering App Integration and Hosted Smoke Test

**SECTION 8: PASS 0 · FAIL 0 · PARTIAL 4**  
**HOSTED APP: FAIL — the UI renders, but every backend request returns HTTP 500.**

| Scenario | Status | What worked | What was unsuccessful |
| --- | --- | --- | --- |
| 8.1 Provider, connection, address | PARTIAL | Registry-driven cards rendered; Instamart was connected; 14 saved addresses loaded automatically; default address was selected; Blinkit stayed disabled; page entry made read-only requests only. | Zepto was intentionally disabled, so switching and fresh OAuth/reconnect flows were not exercised. |
| 8.2 Sync and reconciliation | PARTIAL | UI sync and explicit chat sync both reached the Instamart agent, replaced/read back the cart, showed confirmed products, prices, fees and totals, allowed a partial cart, and placed no order. Natural `Instamart` routing now works. | Two unique unresolved items were counted/rendered as four after refresh; some pack choices materially over-fulfilled small recipe quantities. |
| 8.3 Revalidation and durability | PARTIAL | Draft survived reload; reload/refocus performed only registry, checkout-draft and address reads; explicit Refresh invoked revalidation; changed total produced `status=changed`; acknowledgement stayed reset. | Provider switching could not be exercised because Zepto was disabled. |
| 8.4 Payment and checkout safety | PARTIAL | Only provider-returned UPI methods appeared; selecting Google Pay still left Place Order disabled until acknowledgement; reload required fresh acknowledgement; chat refused to order; authority-policy tests passed. | Asking chat to place an order unexpectedly deleted the existing reviewed draft. Mocked 409, pending and ambiguous-order recovery were covered by automated policy tests rather than a browser order attempt. |
| Hosted production smoke | FAIL | Static pages and navigation rendered for Household, Recipes, Groceries, Nutrition and About. | `/backend/api/health/live`, `/ready`, state and chat all returned 500 `FUNCTION_INVOCATION_FAILED`; live state stayed loading and chat returned “Request failed with status 500.” |

## Routing fix verification

- `kitch_coordinator` now routes provider-cart questions to `recipe_grocery_planner` and has no provider read/sync tools.
- Recipe/Grocery Planner owns provider listing, live cart reads and explicit synchronization.
- `Instamart`, `Swiggy` and `swiggy_instamart` resolve to the same canonical provider.
- Browser prompt “What items do we have in my Swiggy Instamart cart and what's the order value?” returned 14 live items and ₹1,048.00 instead of “provider unavailable.”

## Automated evidence

- 55 focused backend tests passed across agent grocery tools, provider checkout API, commerce policy, Instamart, provider OAuth and Zepto.
- Local `/api/health/live`: `alive`.
- Local `/api/health/ready`: `ready`; Supabase, Vertex Memory Bank and Instamart were ready. Zepto was disabled and Blinkit was coming soon.
- Local browser console: no warnings or errors.
- No order was placed.

## Open defects found

1. Unresolved Instamart rows are merged twice: agent omissions plus confirmed-cart reconciliation produce duplicate names and an incorrect “not found” count.
2. A chat checkout request is correctly refused but can still erase the saved provider review; refusal must be read-only.
3. Hosted Vercel backend function fails during invocation, so the deployed app is not operational even though static UI navigation renders.

