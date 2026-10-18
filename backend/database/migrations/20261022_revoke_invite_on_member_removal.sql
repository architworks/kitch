-- Removing a signed-in member also turns off the household's current invite
-- link, in the same transaction, so the removed person cannot rejoin with the
-- link they used. The owner can create a fresh link to invite anyone again.
-- Removal locks the household before the profile, the same order as joining.
BEGIN;

CREATE OR REPLACE FUNCTION public.remove_household_member(
    p_google_subject TEXT,
    p_profile_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    account public.household_accounts%ROWTYPE;
    v_has_account BOOLEAN;
    v_profile_removed BOOLEAN;
BEGIN
    SELECT * INTO account FROM public.household_accounts
    WHERE google_subject = p_google_subject FOR UPDATE;
    IF NOT FOUND OR account.role <> 'owner' THEN
        RAISE EXCEPTION 'owner_required' USING ERRCODE = '42501';
    END IF;
    IF p_profile_id = account.profile_id THEN
        RAISE EXCEPTION 'cannot_remove_self' USING ERRCODE = '22023';
    END IF;
    -- Join locks the household before a profile. Use the same order so a
    -- concurrent claim cannot race the account check or invite revocation.
    PERFORM 1 FROM public.households WHERE id = account.household_id FOR UPDATE;
    PERFORM 1 FROM public.profiles
    WHERE id = p_profile_id AND household_id = account.household_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'member_not_found' USING ERRCODE = 'P0002';
    END IF;
    SELECT EXISTS (SELECT 1 FROM public.household_accounts WHERE profile_id = p_profile_id)
    INTO v_has_account;
    IF p_profile_id = account.owner_profile_id AND NOT v_has_account THEN
        -- The anchor holds the household's shared data and has nobody signed in.
        RAISE EXCEPTION 'household_anchor' USING ERRCODE = '22023';
    END IF;

    DELETE FROM public.household_accounts
    WHERE profile_id = p_profile_id AND household_id = account.household_id;
    v_profile_removed := public.remove_member_profile(p_profile_id, account.owner_profile_id);

    IF v_has_account THEN
        -- An old shared invite must not restore the removed account's access.
        -- A fresh owner-issued invitation can still deliberately let them back.
        UPDATE public.households
        SET invite_token_hash = NULL, invite_expires_at = NULL, updated_at = now()
        WHERE id = account.household_id;
    END IF;

    RETURN jsonb_build_object(
        'removed_profile_id', p_profile_id,
        'had_account', v_has_account,
        'profile_removed', v_profile_removed,
        'household', public.household_account_context(p_google_subject)
    );
END;
$$;

REVOKE ALL ON FUNCTION public.remove_household_member(TEXT, UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.remove_household_member(TEXT, UUID) TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
