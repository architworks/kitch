# ADR 0002: What triggers memory generation

- **Status:** Accepted
- **Date:** 2026-10-04
- **Implementation:** Implemented with deliberate event-based Memory Bank writes

## Context

Kitch currently updates preference memory only when a specialist agent decides
that the user's statement expresses a durable preference and calls an explicit
memory-update tool. The tool submits a small preference event to the configured
ADK memory service.

Memory Bank can also derive memories from complete conversations or arbitrary
event batches. That capability does not mean it observes conversations by
itself: Kitch must explicitly submit the events or session.

Automatically submitting every turn would create a second, broad ingestion
path alongside the deliberate agent tools. Automatically submitting complete
sessions would still require a reliable definition of when a session ends.

## Decision

Preserve the current memory trigger model:

1. The relevant specialist agent interprets the user's request.
2. If it identifies durable household kitchen context, a correction, or a
   request to forget, it calls the shared natural-language memory-update tool.
3. The tool submits an explicit preference event to the memory service.
4. The memory service extracts and maintains the resulting memory.

The agent chooses **what and when** to remember. Memory Bank chooses **how** the
submitted information relates to existing memory, including whether to create,
update, merge, or delete a memory.

There will be no callback that submits every conversational turn and no
automatic full-session ingestion in the initial Memory Bank migration.

Memory retrieval remains tool-mediated. Agents search preference memory when
it is relevant to meal planning, recipes, groceries, or provider matching; the
entire memory corpus is not injected into every prompt.

The shared update tool accepts one self-contained natural-language statement.
It does not translate the statement into enums, prefixes, or rigid preference
categories. The initial Memory Bank uses its default broad preference and
explicit-instruction behavior; custom topics and few-shot extraction rules are
deferred until observed failures justify them.

## Consolidation semantics

The Kitch write path uses `add_events_to_memory`. With
`VertexAiMemoryBankService`, event and session ingestion already use Memory
Bank generation and consolidation by default. Kitch must not set
`disable_consolidation=True`.

Explicit writes add `wait_for_completion=True`, which selects the Generate
Memories path and prevents a Vercel request from depending on a process-local
background task after it returns.

`enable_consolidation=True` applies specifically to the separate `add_memory`
API, whose default behavior is direct creation of independent memory entries.
Because Kitch is retaining event-based writes, it does not need to set
`enable_consolidation`.

If Kitch deliberately adopts direct `add_memory` writes in the future, those
writes must enable consolidation unless an ADR explicitly establishes a need
for immutable, independent memory entries.

## Consequences

- Memory updates remain legible agent actions rather than an invisible side
  effect of every conversation.
- Memory Bank can still resolve redundancy and contradictions among submitted
  preferences.
- If an agent fails to recognize a preference and does not call the tool, that
  statement is not remembered. This is an accepted trade-off and should be
  tested as agent behavior rather than hidden behind broad automatic ingestion.
- Explicit memory tools and Memory Bank are not disconnected extraction
  systems. The tool selects the input; Memory Bank performs the extraction and
  consolidation after receiving it.

## Rejected alternatives

### Submit every turn after the agent responds

Rejected as unnecessarily frequent and too broad. It would make memory updates
occur independently of the deliberate agent behavior Kitch is designed to
exercise.

### Automatically ingest every full session

Rejected for the initial migration. Full-session ingestion still needs a
reliable session-completion trigger, can repeatedly process the same events,
and can duplicate information already submitted by explicit tools.

### Convert explicit preference events to direct memories immediately

Rejected for this migration because it changes a working update contract
without a demonstrated product need. Event ingestion already receives
Memory Bank extraction and consolidation.

## Possible future use of session ingestion

`add_session_to_memory` may be reconsidered if Kitch later introduces an
explicit, reliable conversation lifecycle such as “Finish conversation” or
“Start new conversation.” It must then preserve household memory scope and
must not become an implicit write after every turn.
