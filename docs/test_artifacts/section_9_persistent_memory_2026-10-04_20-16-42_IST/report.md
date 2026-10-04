# Section 9 — Persistent Household Memory

**PASS: 3 · FAIL: 1 · PARTIAL: 1 · NOT RUN: 1**

| Scenario | Status | What worked | What was unsuccessful |
| --- | --- | --- | --- |
| 9.1 Bread preference | PASS | Baker's Dozen whole wheat was saved and recalled after restart. | — |
| 9.2 Category exclusion | FAIL | The preference was initially acknowledged. | After restart, Kitch included cereal and cookies instead of excluding them; the first grocery write also returned 503 because quantities were missing. |
| 9.3 Amul butter | PASS | Amul was saved and recalled after restart. | — |
| 9.4 Preference correction | PASS | Nutralite replaced Amul and remained authoritative after restart. | — |
| 9.5 Forget and isolation | PARTIAL | Bread was forgotten while Nandini milk and Nutralite butter remained independently recallable after restart. | Kitch falsely said the milk preference could not be saved, although it was subsequently recalled. |
| 9.6 Memory outage | NOT RUN | — | Excluded because this run was restricted to product functionality, not credential/failure-injection scaffolding. |

## Key failure

**9.2:** Saved grocery-category exclusions are not reliably consulted or applied. Kitch subsequently described cereal and cookies as included, directly contradicting the saved preference.

## Test conditions

- Local frontend exercised through Chrome at `http://127.0.0.1:3000`.
- Real Vertex AI Memory Bank used.
- FastAPI was restarted before every recall/correction verification.
- No authentication or deployment-scaffolding tests were performed.
- No provider order was placed.

## Functional evidence

- **9.1:** After restart: “I've added Baker's Dozen whole wheat bread ... based on your household's preferences.”
- **9.2:** After restart, the grocery operation returned 503 (`add requires name and positive amount`). A non-mutating retry then claimed a list containing cereal and cookies despite the stored exclusion.
- **9.3:** After restart: “Amul butter is the preferred brand.”
- **9.4:** After restart: “Currently preferred ... Nutralite”; “Previous ... Amul ... no longer active.”
- **9.5:** After restart: bread had no saved preference, milk was Nandini toned milk, and butter was Nutralite.

