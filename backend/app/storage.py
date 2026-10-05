"""Backend-neutral Kitch persistence facade.

Domain services import this module rather than a provider-specific client.  The
configured adapter is selected inside ``supabase_client`` while its public
function contract is retained during the persistence refactor.
"""

from app.supabase_client import *  # noqa: F401,F403

