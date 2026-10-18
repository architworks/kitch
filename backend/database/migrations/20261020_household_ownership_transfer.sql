-- Household ownership transfer, and each member's role in the account context.
--
-- The owner is the one person who connects the household's grocery app and
-- places orders. Ownership can move to another member who has joined with
-- their own Google account. household_accounts.owner_profile_id stays the
-- household's shared-data anchor, so plans, pantry, carts and memory do not
-- move. The previous owner's grocery-app connection and checkout state are
-- removed so they never pass to the new owner.

BEGIN;

CREATE OR REPLACE FUNCTION public.household_account_context(p_google_subject TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    account public.household_accounts%ROWTYPE;
    members JSONB;
    v_setup_completed BOOLEAN;
BEGIN
    SELECT * INTO account FROM public.household_accounts WHERE google_subject = p_google_subject;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    -- role is 'owner' or 'member' for people who signed in, and null for
    -- members who have not joined with their own Google account.
    SELECT COALESCE(jsonb_agg(
        jsonb_build_object('id', p.id, 'name', p.full_name, 'role', a.role)
        ORDER BY p.member_order, p.created_at
    ), '[]'::jsonb)
    INTO members
    FROM public.profiles p
    LEFT JOIN public.household_accounts a ON a.profile_id = p.id
    WHERE p.household_id = account.household_id;
    SELECT h.setup_completed_at IS NOT NULL INTO v_setup_completed
    FROM public.households h WHERE h.id = account.household_id;
    RETURN jsonb_build_object(
        'google_subject', account.google_subject,
        'email', account.email,
        'household_id', account.household_id,
        'owner_profile_id', account.owner_profile_id,
        'profile_id', account.profile_id,
        'role', account.role,
        'setup_completed', v_setup_completed,
        'members', members
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.transfer_household_ownership(
    p_google_subject TEXT,
    p_new_owner_profile_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    account public.household_accounts%ROWTYPE;
    target public.household_accounts%ROWTYPE;
BEGIN
    SELECT * INTO account FROM public.household_accounts
    WHERE google_subject = p_google_subject FOR UPDATE;
    IF NOT FOUND OR account.role <> 'owner' THEN
        RAISE EXCEPTION 'owner_required' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO target FROM public.household_accounts
    WHERE profile_id = p_new_owner_profile_id
      AND household_id = account.household_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'new_owner_needs_account' USING ERRCODE = '22023';
    END IF;
    IF target.google_subject = account.google_subject THEN
        RAISE EXCEPTION 'already_owner' USING ERRCODE = '22023';
    END IF;

    -- Demote first: one owner per household is enforced by a unique index.
    UPDATE public.household_accounts SET role = 'member'
    WHERE google_subject = account.google_subject;
    UPDATE public.household_accounts SET role = 'owner'
    WHERE google_subject = target.google_subject;

    -- The previous owner's grocery-app sign-in and checkout never pass on.
    DELETE FROM public.provider_connections WHERE profile_id = account.owner_profile_id;
    DELETE FROM public.provider_oauth_flows WHERE profile_id = account.owner_profile_id;
    DELETE FROM public.provider_checkout_drafts WHERE profile_id = account.owner_profile_id;

    RETURN public.household_account_context(p_google_subject);
END;
$$;

REVOKE ALL ON FUNCTION public.household_account_context(TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.household_account_context(TEXT) TO service_role;
REVOKE ALL ON FUNCTION public.transfer_household_ownership(TEXT, UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.transfer_household_ownership(TEXT, UUID) TO service_role;

NOTIFY pgrst, 'reload schema';

COMMIT;
