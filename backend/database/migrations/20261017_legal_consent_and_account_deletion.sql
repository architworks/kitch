-- Record which version of the Privacy Policy and Terms of Use each hosted
-- owner accepted, and let an owner delete their account and household data.

ALTER TABLE public.household_accounts
    ADD COLUMN IF NOT EXISTS terms_version TEXT,
    ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS age_confirmed_at TIMESTAMPTZ;

-- Deleting the account row first lets the household cascade remove every
-- profile and its plans, pantry, carts, diary, provider tokens and drafts
-- (household_accounts.owner_profile_id is ON DELETE RESTRICT).
CREATE OR REPLACE FUNCTION public.delete_household_account(p_google_subject TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_household_id UUID;
BEGIN
    DELETE FROM public.household_accounts
    WHERE google_subject = p_google_subject
    RETURNING household_id INTO v_household_id;
    IF v_household_id IS NULL THEN
        RETURN FALSE;
    END IF;
    DELETE FROM public.households WHERE id = v_household_id;
    RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION public.delete_household_account(TEXT)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.delete_household_account(TEXT) TO service_role;
