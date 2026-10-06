# How Google Sign-In Owns a Household

**Status:** Accepted

## Decision

Hosted Kitch uses one verified Google account as the owner of exactly one
Kitch household. Signing in creates or loads that household. The household may
contain multiple member profiles, but those profiles are not separate login
accounts.

The Google `sub` claim is the stable external identity. Kitch stores its
mapping in `household_accounts`, while `profiles.id` remains the stable internal
identity used by nutrition history and other member-linked records. Renaming a
member updates only `profiles.full_name`.

Local SQLite installations do not require Google Sign-In. Their first-run
onboarding creates the household and member profiles directly.

## Why

Kitch currently has one household-owned provider connection and one explicit
checkout authority. Allowing unrelated Google accounts to join the same
household would require invitations, roles, account recovery, conflict rules,
and a clear decision about who may use the connected Swiggy account. That is a
different product and security model.

The chosen model gives the hosted app a clear security boundary now:

- one authenticated owner controls the household;
- members remain useful personal contexts for nutrition without becoming
  security principals;
- provider OAuth state and checkout authority resolve to the same owner;
- stable member IDs allow names to change without losing history.

## Rejected alternative

We considered registered households that multiple independently authenticated
Google users could join. We rejected it for the current product because it
introduces membership administration and ambiguous provider-checkout authority
before Kitch has a defined multi-owner policy.

If multi-account households are introduced later, they require a new ADR and a
new membership/role model. They must not be added by treating member profiles
as authenticated users.
