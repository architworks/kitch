"""Versioned legal notice that every hosted household owner must accept.

Bump ``LEGAL_TERMS_VERSION`` whenever the Privacy Policy or Terms of Use change
materially; every owner is then asked to review and accept again.
"""

LEGAL_TERMS_VERSION = "2026-10-17"

# Requests a signed-in owner may make before accepting the current notice:
# reading the session, accepting, signing out, and deleting the account.
CONSENT_EXEMPT_PATHS = frozenset({
    "/api/auth/session",
    "/api/auth/logout",
    "/api/legal/consent",
    "/api/account",
    "/api/health/live",
    "/api/health/ready",
})


def valid_consent(payload: object) -> bool:
    """True only for an explicit, current acceptance that confirms age 18+."""
    if not isinstance(payload, dict):
        return False
    return (
        payload.get("version") == LEGAL_TERMS_VERSION
        and payload.get("accepted") is True
        and payload.get("age_confirmed") is True
    )
