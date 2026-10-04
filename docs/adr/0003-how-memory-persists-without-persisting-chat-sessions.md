# ADR 0003: How memory persists without persisting chat sessions

- **Status:** Accepted
- **Date:** 2026-10-04
- **Implementation:** Implemented; production resource configuration remains an environment rollout step

## Context

Kitch uses `InMemorySessionService` for conversations and a configurable memory
service for household context. Deployed environments use Vertex AI Memory
Bank; tests and optional local development may explicitly use
`InMemoryMemoryService`. The application runs on Vercel rather than Google
Agent Runtime.

Kitch conversations are expected to be short and do not need to survive a
deployment or process restart. Preferences do need to survive and remain
searchable across conversations.

Google Agent Platform Memory Bank accepts events supplied directly by an
external application. The agent does not need to be deployed to Agent Runtime,
and an ADK session does not need to be stored in Agent Platform Sessions for
its events to be submitted to Memory Bank.

## Decision

- Retain `InMemorySessionService` for short-term conversational context.
- Replace `InMemoryMemoryService` with `VertexAiMemoryBankService` for durable,
  semantically searchable preference memory.
- Host the application runtime on Vercel; create only the Google Cloud Memory
  Bank resource and credentials needed to use it.
- Continue submitting explicit preference events from the existing agent tools
  rather than persisting or automatically ingesting entire sessions.
- Scope shared preference memory with the real stable household identifier,
  while keeping application and household boundaries in the Memory Bank scope.
- Await successful submission to the Google API before a Vercel request ends.
  Google may perform generation asynchronously, but Kitch must not rely on an
  unawaited process-local background task surviving after the response.
- Authenticate Memory Bank with a dedicated Vertex AI Express Mode API key,
  separate from the Google AI Studio key used for Gemini inference.
- If persistent memory is unavailable, return explicit memory-tool errors and
  degrade only the memory health component; never fall back silently.

## How data moves

```text
User request
  -> Vercel-hosted ADK runner and in-memory session
  -> specialist calls an explicit preference-memory tool
  -> Kitch submits the preference event with household scope
  -> Kitch awaits Google Memory Bank extraction and consolidation
  -> later agents retrieve relevant memories using semantic search
```

Memory Bank does not poll Vercel, inspect server memory, or read
`InMemorySessionService`. Kitch sends the selected content over the Memory Bank
API.

## Consequences

- Long-term preferences survive backend restarts without making conversation
  sessions durable.
- A Vercel cold start can still lose short-term conversational context. This is
  accepted for the current product because session continuity is not a durable
  requirement.
- Memory ingestion must be completed or durably handed off during the request;
  Vercel process lifetime cannot be treated as a background-job guarantee.
- Session-wide ingestion is not needed to make Memory Bank persistent.
- The migration changes the memory service, not the agent topology or the
  ownership boundary established in ADR 0001.

## Rejected alternatives

### Deploy Kitch to Google Agent Runtime

Rejected as unnecessary for obtaining Memory Bank. The runtime remains on
Vercel.

### Use Agent Platform Sessions

Rejected because durable conversation sessions are not a current product
requirement.

### Keep `InMemoryMemoryService` in production

Rejected because household preferences would disappear on process restart and
could not provide dependable cross-conversation personalization.

### Treat `add_session_to_memory` as Google-hosted session persistence

Rejected as a category error. Passing an ADK session to
`add_session_to_memory` sends its events to Memory Bank; it does not make the
session itself durable or allow Google to read Vercel memory later.
