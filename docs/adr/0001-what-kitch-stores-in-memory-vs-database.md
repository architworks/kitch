# ADR 0001: What Kitch stores in memory versus the database

- **Status:** Accepted
- **Date:** 2026-10-04
- **Implementation:** Implemented with shared Memory Bank tools

## Context

Kitch needs to remember flexible, evolving statements such as food dislikes,
allergies, planning style, preferred brands, and preferred product variants.
These statements are messy natural language and should remain available to the
agents that plan meals, generate recipes, manage groceries, and match provider
products.

Kitch also manages deterministic records that the application must render and
edit precisely: household membership and size, pantry inventory, dated meal
plans, recipes, native-cart rows, nutrition logs and goals, provider drafts,
payments, and orders.

## Decision

Natural-language food, dietary, allergy, planning-style, brand, pack, and
ordering preferences belong to the ADK memory service. Chef Planner,
Recipe/Grocery Planner, and Instamart Cart Agent access it through the shared
`search_household_memory_tool` and `update_household_memory_tool` capabilities.

Deterministic application state belongs to the selected structured database:
SQLite for a local single-household installation or Supabase for hosted Kitch.
Profile rows must not be used as a second preference store or as a temporary
persistence substitute for agent memory.

Memory may influence an agent's reasoning, but it is not authoritative for
pantry quantities, plans, carts, nutrition records, payment, or orders.

## Consequences

- Preferences can remain expressive instead of being constrained to enums or a
  catalogue-shaped schema.
- Preference retrieval is semantic and advisory; agents interpret it in the
  context of the current task.
- Product state remains reviewable and reliably renderable by the UI.
- Failure of the memory service must not be hidden by writing preferences into
  profile columns.
- Household preference memory must use a stable, unique household scope.
  A global literal such as `shared_household` is not a safe production scope
  when more than one household can use the deployment.
- Personal records such as nutrition remain scoped to the active user even
  though household kitchen preferences are shared.

## Rejected alternatives

### Structured preference columns or tables

Rejected because real-world preferences and product descriptions do not fit a
stable enum or relational catalogue without introducing brittle deterministic
rules.

### Storing preferences in the household profile until memory is durable

Rejected because it creates two sources of truth and turns a temporary
deployment limitation into product architecture.

### Storing deterministic product records only in agent memory

Rejected because application state must be exact, transactional, inspectable,
and independently renderable by the UI.
