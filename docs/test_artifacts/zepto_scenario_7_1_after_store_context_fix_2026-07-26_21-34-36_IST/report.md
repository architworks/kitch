# Functional Test Report — Zepto Scenario 7.1 After Store-Context Fix

- Test date and time: 2026-07-26 21:34:36 IST
- Environment: local Next.js frontend at `http://127.0.0.1:3000` and local
  FastAPI backend at `http://localhost:8000`
- Scenario source: `test/functional_testing_blueprint.md`, Scenario 7.1
- Overall result: **FAIL**
- Order placement: **Not attempted**

## Purpose

Rerun Scenario 7.1 after changing the Zepto handoff so that Kitch requires a
saved delivery address and establishes the corresponding Zepto store context
before searching products or updating the Zepto cart.

## Prompt / User Action

No chat prompt was used. The functional action was:

1. Open **Groceries**.
2. Confirm that the native cart has selected, eligible rows.
3. Wait for Zepto saved addresses to load.
4. Select the saved **home** address.
5. Click **Move to Zepto cart**.
6. Review the Zepto cart result without acknowledging or confirming an order.

The backend request contained all 32 selected native row IDs and the selected
saved-address ID.

## Expected Result

- Saved Zepto addresses load and can be selected before sync.
- Kitch establishes a serviceable Zepto store context for the selected address
  before product searches begin.
- Selected eligible native rows are represented by accurate Zepto products or
  are clearly marked unavailable.
- The Zepto cart review is visible.
- The durable native cart is unchanged.
- No order is placed.

## Observations

### Address and store readiness

- `GET /api/grocery/zepto/addresses` returned HTTP 200.
- Nine saved addresses were displayed in the frontend.
- The **Move to Zepto cart** button remained disabled until an address was
  selected.
- Selecting **home** enabled the sync action.
- `POST /api/grocery/zepto/sync-cart` returned HTTP 200.
- The frontend changed from **Zepto connected** to **Zepto store ready** and
  displayed: “Products were resolved for the selected delivery address.”
- The review locked availability to the selected **home** address and instructed
  the user to resync if a different address was needed.

This confirms that the original missing-store-context failure is fixed. Product
search no longer runs without an address-derived store context.

### Zepto cart result

- The direct Zepto cart was empty before sync.
- The frontend reported **17 in cart** and **15 unavailable** after sync.
- A direct Zepto `view_cart` call confirmed a non-empty cart containing 17 cart
  rows and a summed quantity of 40.
- The frontend showed the resolved products, prices, quantities, pack sizes,
  native source rows, unavailable rows, selected address, and checkout state.
- Zepto payment methods were not available, so **Confirm Order** remained
  disabled.

### Product-resolution accuracy

Several mappings were accurate, including:

- Butter → Milky Mist Cooking Butter Unsalted
- Eggs → Abhi Vitamin D3 White Eggs
- Chia Seeds → Nutraj Raw Chia Seeds
- Coconut Milk → Dabur Hommade Organic Coconut Milk
- Tamari / Soy Sauce → Ching's Secret Dark Soy Sauce
- Tofu (Firm) → Milky Mist Briyas Tofu

However, the adapter currently accepts the first available Zepto search result
without a sufficient relevance check. This produced materially incorrect
substitutions:

- Milk / Almond Milk → Britannia almond-and-oats milk biscuits
- Green Beans → Ash Gourd
- Sugar-Free Syrup → TusQ-DX cough syrup
- Blue Cheese and Halloumi Cheese → the same feta product
- Cheddar Cheese → mozzarella

The same feta product also appeared as separate cart rows for multiple native
ingredients. These are not safe or accurate grocery substitutions.

### Native state and order safety

- The frontend still displayed **My List 32** after sync.
- A fresh `GET /api/state/Archit` returned HTTP 200 with exactly 32
  `grocery_cart` rows.
- No native row was deleted or checked off.
- The order-review acknowledgement was left unchecked.
- **Confirm Order** was disabled and was not clicked.
- No order-placement request was made.

## Result and Diagnosis

Scenario 7.1 remains **failed** under its full acceptance criteria because
unrelated products were added to the Zepto cart. The original infrastructure /
store-context blocker is resolved; the remaining failure is application-level
product matching in the Zepto provider adapter.

The next fix should rank or validate candidate products against the normalized
native grocery item, reject low-confidence matches as unavailable, and prevent
multiple distinct native ingredients from silently resolving to the same SKU
unless the equivalence is intentional. Quantities also need pack-aware
conversion before this path is safe for final approval.

