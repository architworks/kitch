# Zepto Integration Functional Test — Scenario 7.1

- Started: `2026-07-26T19:03:55+05:30`
- Finished: `2026-07-26T19:04:36+05:30`
- Timezone: `Asia/Kolkata`
- Environment: local Next.js frontend, local FastAPI backend, Supabase, and live Zepto MCP connection
- Scope: Scenario 7.1 only
- Safety boundary: Zepto cart sync and review only; no order-placement action was taken

## Overall Outcome

**Scenario 7.1: FAIL**

Kitch submitted all 32 selected native grocery rows through the browser, but
Zepto resolved no products and added nothing to its cart. The review correctly
reported 0 in cart and 32 unavailable, so the functional requirement that
selected native items reach a usable Zepto cart review was not met.

The failure was presented safely: the native cart remained intact, the UI did
not claim a successful sync, and **Confirm Order** remained disabled.

## Preconditions

### Native Kitch Cart

- Native cart rows: `32`
- Rows selected for Zepto: `32`
- Pantry-covered rows in this cart: `0`
- Categories shown: `3`
- Example selected rows:
  - Blue Cheese
  - Butter
  - Eggs
  - Paneer / Block Cheese
  - Chia Seeds
  - Avocado
  - Broccoli
  - Tomatoes
  - Zucchini

### Zepto State

- Direct Zepto cart before sync: empty
- Zepto status endpoint:
  - `enabled: true`
  - `state: oauth_bridge_ready`
  - `transport: stdio_remote`
  - `auth_mode: browser_oauth`
- Browser UI showed:
  - `Signed in to Zepto`
  - `Ready to move selected items into your Zepto cart.`
  - Enabled **Move to Zepto cart** button

## Scenario 7.1 — Move Selected Native Cart Items to Zepto — FAIL

### Prompt/Action

1. Opened the local app in Chrome.
2. Opened **Groceries**.
3. Confirmed 32 native rows were selected.
4. Clicked **Move to Zepto cart**.
5. Inspected the resulting Zepto review.
6. Queried the Zepto cart directly.
7. Confirmed the durable native cart after the attempt.
8. Did not acknowledge the order review or press **Confirm Order**.

### Expected Behavior

- Selected eligible native rows should be resolved to Zepto products.
- Successfully resolved products should be added to the Zepto cart.
- The frontend should show a review with products, quantities, substitutions,
  and any genuinely unavailable items.
- The native Kitch cart should remain unchanged.
- No real order should be placed.

### Browser Observation

The frontend submitted:

```text
POST /api/grocery/zepto/sync-cart
```

with all 32 selected native cart IDs.

The HTTP response status was `200`, but the application-level response was:

```text
status: error
message: No Zepto products could be added to the cart.
items: 0
unavailable_items: 32
```

The visible review showed:

- `Sync needs attention`
- `No Zepto products could be added to the cart.`
- `0 IN CART`
- `32 UNAVAILABLE`
- `No Zepto cart items were added yet.`

Every submitted item was listed under **Unavailable or unresolved** with:

```text
No available Zepto product was returned.
```

This included common products such as butter, eggs, milk, avocado, broccoli,
tomatoes, cucumber, spinach, and zucchini, so this does not look like normal
individual-product unavailability.

### Direct Zepto Cart Observation

The Zepto connector reported:

```json
{
  "items": [],
  "isEmpty": true,
  "totalItems": 0
}
```

No product reached the Zepto cart.

### Native-Cart Safety Observation

After the failed sync, `GET /api/grocery/cart` still returned all 32 original
row IDs:

```text
137, 132, 133, 134, 130, 135, 136, 131,
115, 138, 141, 143, 145, 142, 144, 146,
123, 124, 116, 117, 139, 126, 122, 128,
127, 129, 121, 119, 118, 140, 125, 120
```

The browser also continued to show:

- `My List 32`
- `32 items`
- `32 selected for Zepto`

Result: the external failure did not corrupt or clear the durable Kitch cart.

### Order-Safety Observation

- **Confirm Order** was disabled.
- The review displayed `Order blocked`.
- The reason shown was:
  `Zepto cart sync must succeed with at least one Zepto cart item.`
- No final acknowledgement was selected.
- No order-placement endpoint was called.

### Browser Network and Console Evidence

- `GET /api/state/Archit`: HTTP `200`
- `GET /api/recipe-grocery/plans/latest`: HTTP `200`
- `GET /api/grocery/zepto/status`: HTTP `200`
- `POST /api/grocery/zepto/sync-cart`: HTTP `200`, application status `error`
- Follow-up `GET /api/grocery/zepto/status`: HTTP `200`
- Application console errors: none
- Non-blocking Chrome accessibility issue: 68 form fields lack an `id` or
  `name` attribute

## Diagnosis

The strongest evidence points to missing Zepto location/store context rather
than unavailable groceries:

- The Zepto response included:
  `Store context missing. Please run get_location_serviceability or select_store first.`
- The backend reports the OAuth bridge as ready, but readiness currently proves
  only that the MCP bridge is configured.
- The adapter retrieves saved addresses and then immediately searches products.
  It does not establish location serviceability or select a Zepto store before
  calling `search_products`.
- With no active store context, every product search returned no usable
  product—including common items that should not all be unavailable together.

Therefore, the integration is authenticated enough to list saved addresses,
but it is not functionally ready for catalog search or cart population.

## Result Rationale

**FAIL** because Scenario 7.1 requires selected native items to appear in a
usable Zepto review. Zero of 32 items were resolved or added.

The failure handling and order-safety behavior worked correctly, but those
protections do not turn the cart-sync outcome into a pass.

Structured evidence is recorded in `results.json`.
