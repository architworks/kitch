# Make Everyday Cart Actions Instant and Idempotent

**Status:** Accepted (6 November 2026)

## Decision

Native shopping-list actions update the screen before the server answers, and
the server tolerates repeats:

- **Delete** removes the row immediately. A second delete of the same row is
  ignored while the first is in flight. On the server, deleting a row that is
  already gone returns `200` with `status: "already_removed"`, not an error.
- **Rename** applies the new name and closes the edit box immediately. If the
  save fails, the box reopens with the typed name.
- **Add** shows a pending row (temporary id `pending-…`) and clears the form
  immediately. The server's cart replaces the pending row; on failure the row is
  removed and the form is refilled.
- **Quantity and selection** were already optimistic and are unchanged.

Every optimistic change rolls back to the last cart the server confirmed
(`confirmedGroceryItemsRef`) when its request fails. Pending rows cannot be
edited or deleted until they have a real id.

## Context

Before the change, the UI waited for each request to finish before showing the
result. With the backend on another continent from the database (see
[ADR 0006](0006-run-the-backend-next-to-the-database.md)), that wait was about
a second. People clicked delete again. The second request deleted zero rows,
and the persistence layer treated "zero rows" as a storage failure, so the user
saw "Kitch couldn't save this change because durable storage is unavailable."

Two separate problems produced one bad experience:

1. The UI gave no feedback while the request was in flight.
2. The server treated a harmless repeat as a failure.

## Why both, not one

Fixing only the UI would hide the problem for one tab, but a repeat could still
reach the server from another tab, a retry or a slow network. Fixing only the
server would remove the error, but the action would still feel slow. Idempotent
endpoints and optimistic UI each cover the other's gap.

## Rejected alternatives

- **Disable the button while saving.** This prevents double clicks but keeps
  the action feeling slow and adds a flash of disabled state on every click.
- **Debounce clicks.** This guesses at timing. It doesn't help when a request
  takes longer than the debounce window, and it adds delay to every click.

## Consequences

- Production checks on 7 November 2026: a new item shows within 50 ms, a rename
  within 60 ms, and a double-clicked delete removes the row within 60 ms with
  no error. The server cart matched afterwards.
- The server remains the source of truth: each successful response replaces
  the local cart with the server's.
- Tests: `test/test_grocery_cart_delete.py`.
