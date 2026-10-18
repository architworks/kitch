# Kitch household identity configuration.
#
# SQLite resolves these values from the locally bootstrapped household. Hosted
# requests resolve them from the verified Google account's household context.

HOUSEHOLD_MEMBERS = ("Archit", "Anubhav", "Naman")
DEFAULT_ACTIVE_USER = HOUSEHOLD_MEMBERS[0]
DEFAULT_HOUSEHOLD_SIZE = len(HOUSEHOLD_MEMBERS)

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


class AmbiguousMemberNameError(ValueError):
    """A shorthand name matches multiple profiles; an exact name is needed."""


def _matching_member(members, user_name: str | None):
    """Prefer the actual stored name; never guess between folded names.

    Postgres lower() uniqueness does not imply Python casefold() uniqueness
    (for example Straße and Strasse). The UI sends the actual member name.
    """
    raw = str(user_name or "")
    exact = [member for member in members if member["name"] == raw]
    matches = exact or [
        member for member in members
        if member["name"].strip().casefold() == raw.strip().casefold()
    ]
    if len(matches) > 1:
        raise AmbiguousMemberNameError("Member name is ambiguous. Use the exact name shown in the household.")
    return matches[0] if matches else None


def canonical_user_name(user_name: str | None) -> str:
    """Return a configured household member name, falling back to the default."""
    local = _local_client()
    if local is not None:
        return local.canonical_name(user_name)
    from app.auth import current_identity
    identity = current_identity()
    if identity is not None:
        member = _matching_member(identity.members, user_name)
        if member is not None:
            return member["name"]
        owner = next(
            (member for member in identity.members if member["id"] == identity.owner_profile_id),
            identity.members[0],
        )
        return owner["name"]
    if not user_name:
        return DEFAULT_ACTIVE_USER

    cleaned = user_name.strip()
    return cleaned if cleaned in USER_ID_MAP else DEFAULT_ACTIVE_USER


def get_user_id(user_name: str | None) -> str:
    """Return the configured prototype UUID for a household member."""
    local = _local_client()
    if local is not None:
        return local.user_id(user_name)
    from app.auth import current_identity
    identity = current_identity()
    if identity is not None:
        member = _matching_member(identity.members, user_name)
        if member is not None:
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
