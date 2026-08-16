-- Instamart drafts created by the deterministic matcher cannot be reviewed
-- under the agent-driven matching contract. Native grocery intent is retained.
BEGIN;

DELETE FROM public.provider_checkout_drafts
WHERE provider = 'swiggy_instamart';

COMMIT;
