# Kitch local household bootstrap configuration.
#
# Multi-household registration is intentionally deferred. Until then, this file
# is the single place where the prototype household and its seeded members live.

HOUSEHOLD_NAME = "Kitch Household"
HOUSEHOLD_MEMBERS = ("Archit", "Anubhav", "Naman")
DEFAULT_ACTIVE_USER = HOUSEHOLD_MEMBERS[0]
DEFAULT_HOUSEHOLD_SIZE = len(HOUSEHOLD_MEMBERS)

USER_ALIASES = {
    "Archit(me)": "Archit",
    "Archit (me)": "Archit",
}

USER_ID_MAP = {
    "Archit": "00000000-0000-0000-0000-000000000000",
    "Anubhav": "11111111-1111-1111-1111-111111111111",
    "Naman": "22222222-2222-2222-2222-222222222222",
}

# Shared household tables currently reuse one configured profile id until a
# first-class household table is introduced.
HOUSEHOLD_OWNER_NAME = DEFAULT_ACTIVE_USER


def canonical_user_name(user_name: str | None) -> str:
    """Return a configured household member name, falling back to the default."""
    if not user_name:
        return DEFAULT_ACTIVE_USER

    cleaned = user_name.strip()
    cleaned = USER_ALIASES.get(cleaned, cleaned)
    return cleaned if cleaned in USER_ID_MAP else DEFAULT_ACTIVE_USER


def get_user_id(user_name: str | None) -> str:
    """Return the configured prototype UUID for a household member."""
    return USER_ID_MAP[canonical_user_name(user_name)]


def get_household_profile_id() -> str:
    """Return the profile id used for shared household resources."""
    return USER_ID_MAP[HOUSEHOLD_OWNER_NAME]


def household_members_text() -> str:
    """Return a prompt-friendly household member list."""
    return ", ".join(HOUSEHOLD_MEMBERS)
