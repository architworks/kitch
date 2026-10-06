# Known Issues and Optimisations

This register contains only currently open, reproducible defects, operational
blockers, and deliberately deferred engineering work. Resolved issues are
removed instead of retained as historical compatibility notes. Architectural
decisions—including rejected agent topologies—belong in
`ai_agent_topology.md`.

The most recent provider run is
[`section_8_grocery_integration_and_hosted_smoke_2026-10-04_21-12-43_IST`](./test_artifacts/section_8_grocery_integration_and_hosted_smoke_2026-10-04_21-12-43_IST/report.md).

## Open issue summary

| ID | Severity | Status | Immediate problem |
| --- | --- | --- | --- |
| KI-001 | High | Open | Instamart may omit valid variants or apply a preference belonging to another item. |
| KI-004 | Medium | Open | Instamart unresolved items are duplicated and the displayed not-found count is wrong. |
| OP-002 | Critical | Open | The hosted Vercel backend function returns HTTP 500 for liveness, readiness, state, and chat. |
| SEC-001 | Medium | Monitoring | Next.js currently brings in a transitive `baseline-browser-mapping` advisory for which npm reports no available fix. |

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

## KI-004: Duplicate unresolved Instamart rows

- **Area:** Instamart reconciliation and provider review UI
- **First reproduced:** 2026-10-04

Two genuinely unresolved native items (`cauliflower` and `water (for dough)`)
were rendered twice and reported as four missing items. The persisted draft
contains both the agent's omission record and a second reconciliation failure
for the same native item.

Deduplicate unavailable results by stable native item ID after reconciliation,
preserving the most useful combined reasoning. Counts and acknowledgement text
must use unique unresolved native items.

## Operational blockers

### OP-001: Live provider testing requires valid external authentication

Zepto can be disabled and Swiggy tokens expire or return 401. In that state the
provider UI should show disabled or `reconnect_required`, and live Section 7
tests cannot exercise address, cart, payment, or revalidation behavior. This is
an external prerequisite, not a core-readiness failure and not evidence of a
provider-workflow defect.

### OP-002: Hosted Vercel backend invocation failure

On 2026-10-04 the hosted static UI rendered, but
`/backend/api/health/live`, `/backend/api/health/ready`, state loading, and chat
all returned HTTP 500 with `FUNCTION_INVOCATION_FAILED`. The deployed app is
not operational until the Vercel function startup failure is diagnosed from
deployment/runtime logs and both health endpoints succeed.

## Security dependency monitoring

### SEC-001: Transitive Next.js browser-data denial-of-service advisory

On 2026-10-06, `npm audit --omit=dev` reported two moderate findings for
`baseline-browser-mapping` through Next.js (`GHSA-w5vr-8v7q-w6rv`). The issue
terminates the build/runtime process only when that package is given malformed
mapping input; Kitch does not pass user-controlled input to it. npm currently
reports no fixed version. Keep Next.js current and remove this entry as soon as
the upstream dependency is patched. The Python requirements audit reported no
known vulnerabilities on the same date.

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

### OPT-002: Observe Memory Bank extraction and retrieval quality

Persistent household memory is implemented with Vertex AI Memory Bank while
conversation sessions intentionally remain in `InMemorySessionService`. The
Memory Bank resource, service account, and Vercel Workload Identity Federation
are configured for the production subject; the remaining rollout work is to
set the non-secret Vercel resource variables and run save/restart/recall,
correction, forget, and item-isolation tests. A preview deployment needs its own
explicit WIF subject binding before it can run the same tests. Observe real retrieval before
adding custom topics or few-shot extraction rules; do not pre-emptively replace
flexible memory with structured preference fields.
