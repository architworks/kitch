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
