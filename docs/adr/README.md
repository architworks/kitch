# Architecture Decision Records

This directory records consequential Kitch architecture decisions, including
the alternatives considered and deliberately rejected. An accepted ADR
describes the intended architecture even when implementation is still pending.

## Status meanings

- **Proposed:** under active discussion.
- **Accepted:** the intended direction; implementation may still be pending.
- **Superseded:** replaced by a later ADR, which must be linked from the old one.

## Index

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-what-kitch-stores-in-memory-vs-database.md) | Accepted | What Kitch stores in agent memory and what it stores in the database. |
| [0002](0002-what-triggers-memory-generation.md) | Accepted | What causes Kitch to generate or update a memory. |
| [0003](0003-how-memory-persists-without-persisting-chat-sessions.md) | Accepted | How long-term memory persists while chat sessions remain temporary. |
| [0004](0004-why-grocery-provider-agents-use-mcp-tools-directly.md) | Accepted | Why provider cart agents use MCP tools directly instead of deterministic product-matching adapters. |
| [0005](0005-how-google-sign-in-owns-a-household.md) | Accepted | How one hosted Google account owns one household while household members remain editable profiles. |
| [0006](0006-run-the-backend-next-to-the-database.md) | Accepted | Why backend functions run in Tokyo next to the database, with before/after latency. |
| [0007](0007-make-everyday-cart-actions-instant-and-idempotent.md) | Accepted | Why cart actions update instantly and the server tolerates repeated requests. |
| [0008](0008-keep-ai-code-off-everyday-request-paths.md) | Accepted | Why non-AI requests never load agent or model code, and dashboard reads run in parallel. |
