# Known Issues and Optimisations

This register contains only currently open, reproducible defects, operational
blockers, and deliberately deferred engineering work. Resolved issues are
removed instead of retained as historical compatibility notes. Architectural
decisions—including rejected agent topologies—belong in
`ai_agent_topology.md`.

The most recent full functional run is
[`functional_blueprint_2026-10-02_16-23-46_IST`](./test_artifacts/functional_blueprint_2026-10-02_16-23-46_IST/report.md).
Its application failures were fixed and targeted retests passed on 2026-10-02.
Provider scenarios remained blocked by external authentication state and were
not represented as product failures.

## Open issue summary

| ID | Severity | Status | Immediate problem |
| --- | --- | --- | --- |
| KI-001 | High | Open | Instamart may omit valid variants or apply a preference belonging to another item. |
| KI-002 | Medium | Open | Instamart search-candidate prices can contain corrupted minor-unit values. |
| KI-003 | High | Open | Native-cart drift can be overwritten and a stale provider draft can become `ready` again. |

## KI-001: Instamart matching and preference leakage

- **Area:** Instamart cart agent, preference retrieval, catalogue matching
- **First reproduced:** 2026-08-16
- **Last live status:** Not revalidated because the provider connection later
  required authentication

### Observed behavior

- For `eggs — 12 pieces`, Swiggy returned a suitable 12-piece product but
  Kitch left the item unresolved because multiple variants existed.
- A stored Baker's Dozen bread preference was retrieved while matching butter,
  even though an Amul butter preference also existed. The agent searched for
  bread and omitted butter.

Multiple brands and pack sizes are normal catalogue behavior and are not, on
their own, a reason to reject a product.

### Probable cause

- Semantic memory retrieval returns relevant-looking text without proving that
  its subject is the native item currently being matched.
- The cart agent over-penalizes ordinary catalogue ambiguity instead of
  selecting the best reasonable orderable result.
- Match reasoning does not explain why a clearly valid higher-ranked candidate
  was rejected.

### Required fix

- Preserve flexible natural-language preference memory; do not replace it with
  a deterministic preference table.
- Provide the agent enough original memory context to decide whether a
  retrieved preference applies to the current item.
- Treat equivalent real-world pack descriptions semantically and select the
  best candidate that covers the requested quantity.
- Record why any apparently valid higher-ranked candidate was rejected.
- Retest eggs, bread, butter, unrelated-preference isolation, multiple brands,
  and multiple pack sizes against a live connected provider.

## KI-002: Corrupted candidate-level price metadata

- **Area:** Instamart search normalization and agent match records
- **First reproduced:** 2026-08-16

### Observed behavior

Candidate `price_minor` values were orders of magnitude larger than the real
price. A bread ultimately confirmed at ₹70 correctly appeared as `7000` minor
units in the provider cart, while earlier candidate metadata contained
`70701751`. The confirmed provider bill and payable total were correct.

### Probable cause

Loosely structured MCP search output is being copied into the match record
without an explicit money field and scale. A display string or multiple numeric
fragments may be interpreted as one amount.

### Required fix

- Read candidate price only from an explicit provider money field with known
  currency and scale.
- Store missing or ambiguous candidate prices as unavailable; never guess.
- Compare the selected candidate's price with the confirmed cart result while
  allowing a genuine provider-authorized price change.
- Keep provider-returned subtotal, fees, discounts, taxes, and payable total
  authoritative.

## KI-003: Native-cart drift can revive a stale provider draft

- **Area:** Durable checkout draft and order safety
- **First reproduced:** 2026-08-16

### Observed behavior

After synchronizing and approving a provider cart, deleting its native cart row
cleared payment and acknowledgement. A later draft read nevertheless returned
the stale provider draft with `status="ready"`, `can_place_order=true`, and no
blockers. The frontend separately noticed the mismatch and kept checkout
disabled, but the backend representation was unsafe.

### Probable cause

`invalidate_draft_for_native_drift()` marks the draft blocked, after which
`refresh_checkout_eligibility()` recomputes readiness from the old stored native
snapshot and provider result. The generic refresh can remove the drift blocker.

### Required fix

- Make native-drift invalidation durable and non-overridable by generic
  eligibility refresh.
- A stale draft must never expose `can_place_order=true`, a confirmation token,
  or an empty blocker list.
- Require synchronization from the current native selection before payment and
  acknowledgement can be restored.
- Add a backend regression test that performs invalidation followed by the same
  read/refresh path used by the API.

## Operational blockers

### OP-001: Live provider testing requires valid external authentication

Zepto can be disabled and Swiggy tokens expire or return 401. In that state the
provider UI should show disabled or `reconnect_required`, and live Section 7
tests cannot exercise address, cart, payment, or revalidation behavior. This is
an external prerequisite, not a core-readiness failure and not evidence of a
provider-workflow defect.

## Deferred optimisations

### OPT-001: Provider-registered cart executors

`GroceryCheckoutService` currently contains an Instamart-specific execution
branch and owns `InstamartCartAgentService`. This is acceptable with one
agent-driven provider. When a second agent-driven provider is actually added,
introduce a provider-registered executor contract instead of adding more
provider-ID branching.

Do not pre-emptively add a conversational `grocery_ordering_agent`, provider
sub-agent hierarchy, or plugin framework. The rejected topology and the reason
for rejecting it are documented in `ai_agent_topology.md`.

### OPT-002: Durable ADK sessions and preference memory

The current `InMemorySessionService` and `InMemoryMemoryService` lose
conversation and natural-language household preferences on backend restart.
Migrate to Vertex AI session and memory services before treating the deployment
as production-durable. Preserve the flexible text-memory model; durability does
not imply converting preferences into rigid relational rules.

### OPT-003: Auth-backed households

The current prototype member IDs are configured in code while factual member
names are persisted in `profiles` and returned by the backend.
Introduce authentication, household membership, and per-household ownership
before supporting unrelated households in one deployment. This change must
also introduce membership-aware RLS policies if clients ever access Supabase
directly.
