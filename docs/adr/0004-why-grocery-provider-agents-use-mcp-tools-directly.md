# ADR 0004: Why grocery provider agents use MCP tools directly

- **Status:** Accepted
- **Date:** 2026-10-04
- **Implementation:** Implemented for Swiggy Instamart; Zepto migration is deliberately deferred

## Context

Kitch currently has two different ways of integrating with grocery-provider
MCP servers.

Swiggy Instamart uses a dedicated `instamart_cart_agent`. ADK exposes a small
allowlist of Instamart MCP tools directly to that agent, so Gemini can search,
reformulate queries, compare real-world products and packs, update the cart,
and inspect the confirmed cart.

Zepto was integrated earlier. Its MCP tools are invoked by
`ZeptoProviderAdapter`, and application code controls the search and cart
workflow. Gemini does not see or choose the Zepto MCP tools.

Grocery catalogues are semantically messy. Equivalent intent may be described
through brands, regional names, weights, volumes, pieces, multipacks, bundles,
or provider-specific product language. Encoding all matching decisions in an
adapter makes application code responsible for interpreting that changing
catalogue. This has already produced brittle matching rules and unnecessary
rejection gates.

At the same time, exposing provider credentials, authentication, payment,
checkout, cancellation, or unrestricted mutation to an agent would cross an
important safety boundary. Placing an order is consequential and must remain
an explicit UI-authorized backend operation.

## Decision

The Instamart approach is Kitch's preferred architecture for grocery-provider
MCP integrations.

- Give each supported MCP provider a dedicated cart agent when its catalogue
  requires semantic search and product selection.
- Expose that provider's reversible cart tools directly to its agent through
  ADK's MCP toolset. The model, rather than deterministic application matching
  code, chooses how to search and which reasonable product best satisfies the
  user's intent.
- Supply only an explicit allowlist of tools needed to read provider context,
  search products, update a cart, and confirm the resulting cart.
- Keep credentials and server-owned authority outside model-visible context.
  Backend middleware authorizes every MCP tool call and denies unknown or
  consequential mutations by default.
- Never expose checkout, payment authorization, cancellation, account changes,
  or address mutation to a provider cart agent. Checkout remains callable only
  by the backend after the user presses the final UI order button and all
  approval checks succeed.
- Keep `GroceryCheckoutService` as the provider-neutral workflow owner. It
  scopes the native-cart input, starts the appropriate integration, persists
  durable drafts, invalidates stale approval, and controls order preflight.
- Keep provider adapters, but make them infrastructure boundaries rather than
  product-matching brains. They may own OAuth, MCP connection details,
  capability discovery, confirmed-response translation, payment metadata, and
  UI-authorized checkout operations.
- Treat the provider's confirmed cart response as financial and cart truth.
  Agent reasoning may explain a match, but it cannot fabricate confirmed
  products, quantities, prices, or totals.
- Use this agent-driven pattern by default for future MCP grocery providers.
  Provider-specific agents may share reusable infrastructure, but must not be
  forced through Zepto-shaped matching logic.
- Retain the current adapter-driven Zepto integration until a separate,
  explicitly tested migration is undertaken. This ADR establishes direction;
  it does not claim that Zepto has already been converted.

## Preferred call path

```text
Recipe/Grocery Planner or Groceries UI
  -> GroceryCheckoutService
  -> provider-specific cart agent
  -> ADK MCP toolset with a strict reversible-cart allowlist
  -> provider MCP server
  -> confirmed provider cart
  -> provider adapter translation
  -> durable Kitch checkout draft
```

Payment and ordering follow a separate path:

```text
Final Place Order button
  -> backend approval and freshness checks
  -> UI-authorized checkout operation
  -> provider MCP checkout tool
```

No agent participates in the second path.

## Why this is preferred over the Zepto approach

- The agent can interpret catalogue language and packaging semantically instead
  of relying on an expanding collection of deterministic special cases.
- The agent can reformulate searches and compare several valid candidates
  without treating normal catalogue ambiguity as failure.
- Household brand and product preferences can inform the same reasoning loop
  that sees live provider results.
- The backend remains responsible for facts and authority: selected native
  items, selected address, allowed tools, confirmed cart state, approval, and
  ordering.
- New provider integrations can preserve their own MCP vocabulary rather than
  being distorted into another provider's tool or product model.

## Consequences

- Provider-cart agents are genuine MCP-using agents, not textual wrappers
  around deterministic adapter decisions.
- MCP tool schemas and returned catalogue data become part of the agent's
  runtime context and require prompt-injection-resistant handling.
- Recorded fixtures and browser tests must verify both semantic decisions and
  the exact confirmed provider cart.
- Provider-specific agents may behave differently at the reasoning level, but
  `GroceryCheckoutService` and durable checkout drafts preserve one product
  workflow for the frontend.
- Zepto remains an architectural exception and a candidate for later migration;
  it must not become the template for Blinkit or other future providers.

## Rejected alternatives

### Keep all provider matching inside deterministic adapters

Rejected as the preferred future pattern. Application code is well suited to
authority, persistence, reconciliation, and exact factual checks, but poorly
suited to exhaustively interpreting changing real-world product catalogues.

### Give every provider MCP tool directly to the Kitch coordinator

Rejected. The coordinator should route household requests, not accumulate
provider credentials and large, unrelated toolsets. Dedicated provider agents
keep product reasoning and provider context isolated.

### Add a generic grocery-ordering router agent now

Rejected for the current topology. `GroceryCheckoutService` can deterministically
select the already chosen provider and invoke its integration. Another agent
would add routing ambiguity without adding product reasoning. This can be
reconsidered only if future provider scale creates a demonstrated need.

### Let provider agents place orders

Rejected. Cart preparation is reversible; checkout is consequential and often
non-idempotent. Final ordering therefore remains an explicit UI-only backend
operation.

### Replace provider adapters entirely with agents

Rejected. Agents should reason about catalogue matches, while adapters and
services continue to own authentication, transport, normalized confirmed data,
durable state, and safe checkout execution.
