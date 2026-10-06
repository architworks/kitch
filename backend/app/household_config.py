# Kitch household identity configuration.
#
# SQLite resolves these values from the locally bootstrapped household. Hosted
# requests resolve them from the verified Google account's household context.

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

# Local prototype defaults remain available before SQLite onboarding only.
HOUSEHOLD_OWNER_NAME = DEFAULT_ACTIVE_USER


def _local_client():
    import os

    if str(os.environ.get("KITCH_DATABASE_BACKEND", "supabase")).strip().lower() != "sqlite":
        return None
    from app.sqlite_supabase import create_sqlite_client

    return create_sqlite_client()


def canonical_user_name(user_name: str | None) -> str:
    """Return a configured household member name, falling back to the default."""
    local = _local_client()
    if local is not None:
        return local.canonical_name(user_name)
    from app.auth import current_identity
    identity = current_identity()
    if identity is not None:
        wanted = str(user_name or "").strip().casefold()
        for member in identity.members:
            if member["name"].casefold() == wanted:
                return member["name"]
        owner = next(
            (member for member in identity.members if member["id"] == identity.owner_profile_id),
            identity.members[0],
        )
        return owner["name"]
    if not user_name:
        return DEFAULT_ACTIVE_USER

    cleaned = user_name.strip()
    cleaned = USER_ALIASES.get(cleaned, cleaned)
    return cleaned if cleaned in USER_ID_MAP else DEFAULT_ACTIVE_USER


def get_user_id(user_name: str | None) -> str:
    """Return the configured prototype UUID for a household member."""
    local = _local_client()
    if local is not None:
        return local.user_id(user_name)
    from app.auth import current_identity
    identity = current_identity()
    if identity is not None:
        wanted = str(user_name or "").strip().casefold()
        for member in identity.members:
            if member["name"].casefold() == wanted:
                return member["id"]
        return identity.owner_profile_id
    return USER_ID_MAP[canonical_user_name(user_name)]


def get_household_profile_id() -> str:
    """Return the profile id used for shared household resources."""
    local = _local_client()
    if local is not None:
        return local.owner_id()
    from app.auth import current_identity
    identity = current_identity()
    if identity is not None:
        return identity.owner_profile_id
    return USER_ID_MAP[HOUSEHOLD_OWNER_NAME]


def household_members_text() -> str:
    """Return a prompt-friendly household member list."""
    local = _local_client()
    if local is not None:
        state = local.bootstrap_status()
        return ", ".join(member["name"] for member in state["members"])
    from app.auth import current_identity
    identity = current_identity()
    if identity is not None:
        return ", ".join(member["name"] for member in identity.members)
    return ", ".join(HOUSEHOLD_MEMBERS)
