# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

A shared household, typically two to six adults living together in India, who eat from one meal plan and one pantry but track nutrition individually. One person usually drives planning and grocery ordering; everyone checks what's being cooked and logs what they ate. In hosted use one Google account owns the household and members are editable profiles switched inside Kitch, not separate logins. Local installs are login-free and ask for member names on first run.

Typical moments: glancing at tonight's dinner, asking for next week's plan, telling Kitch what's in the fridge (often with a photo), preparing a Swiggy Instamart or Zepto cart, and logging a plate after eating. Sessions are short and recurring, on a laptop or a phone in the kitchen.

## Product Purpose

Kitch reduces the everyday cognitive load of running a household kitchen: deciding what to cook, remembering what's in stock, turning dated meal plans into recipes and groceries, avoiding duplicate purchases, preparing a delivery cart without letting an agent place an order, and tracking personal macros without spreadsheets. Success is that conversational requests and the visible household state agree: when Kitch says it changed something, the user can see exactly what changed.

## Positioning

One conversational kitchen that connects dated household meal plans, pantry-aware recipes, a provider-neutral native grocery cart, reviewed delivery-provider carts, and individual nutrition diaries. The agent prepares; the human approves. Chat may plan, edit, and prepare a provider cart, but only an explicit UI action places an order.

## Operating Context

- Conversation (text, plate photo, fridge photo) is the primary control surface; structured pages show the resulting shared or personal state and allow direct edits.
- Surfaces: Household overview with the dated meal planner, Recipes (latest recipe + ingredients artifacts), Groceries (pantry, native cart, provider checkout stages), Nutrition (personal diary, goals, trends), About.
- Grocery checkout runs in fixed stages: native cart review → provider selection → connect/address → transfer → provider cart review → payment → explicit approval and order.
- Grocery providers: Swiggy Instamart (live), Zepto (adapter), Blinkit (coming soon).
- Dates, quantities, units, prices in INR, and macros (kcal, protein, carbs, fats) are the core data.

## Capabilities and Constraints

- Meal plans are date-specific (breakfast, lunch, dinner; no snacks) and shared by the household.
- Recipe-only requests never change the cart; grocery requests derive cart rows from the same recipe artifact; manual cart rows are allowed.
- The native cart is the source of truth; provider carts are reversible projections of it.
- Before provider sync the UI shows "not synced", never fake prices. Provider totals come from the provider.
- Later checkout stages remain visible but locked until prerequisites complete; any native-cart, selection, provider, or address change invalidates the review.
- Unresolved provider items are listed prominently as omitted; a partial cart may proceed.
- Chat cannot select payment or place orders.
- Persistence failures fail loudly; the UI keeps the last confirmed state and never shows optimistic success.
- Images are classified meal / pantry / ambiguous; ambiguous images persist nothing and offer an explicit override.
- Nutrition logs belong to the active member only.
- Frontend: Next.js 16 / React 19 calling a FastAPI backend; the browser never calls Gemini, ADK, Supabase, or provider MCP servers directly.

## Brand Commitments

- Product name: Kitch.
- The interface should feel practical, calm, trustworthy, and domestic: a kitchen companion, not a clinical health app, a gamified tracker, or a generic "AI" product.
- Existing chef-hat mark and kitchen illustrations are available but not binding; the owner asked for a from-scratch redesign that still clearly belongs to a household kitchen product.

## Evidence on Hand

- Requirements: `docs/vision_and_requirements.md`; UX flows: `docs/ux_user_flows.md`; architecture: `docs/system_architecture.md`.
- Provider logos in `frontend/public/` (Instamart, Swiggy, Zepto, Blinkit).
- No testimonials, user counts, benchmarks, or commercial claims exist; none may be fabricated.

## Product Principles

1. Shared household planning, personal nutrition: always clear which state is whose.
2. Clarity over magic: every agent change is visible, confirmed state, never prose alone.
3. Fast everyday use: common tasks take one sentence or one tap.
4. Review before external order: the human holds final authority over money.
5. Consistency across pages: one vocabulary of controls and states.

## Accessibility & Inclusion

Keyboard operable throughout, visible focus, labelled controls, zoom and reduced-motion support, comfortable touch targets, and full usability on phone, laptop, and desktop viewports.
