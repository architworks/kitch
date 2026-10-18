-- Owner removal of members, unique member names, and safe leaving for a
-- former owner.
--
-- 1. Member names are unique within a household (case-insensitive), enforced
--    by the database as well as the app, so two members' nutrition logs can
--    never be confused.
-- 2. The owner can remove any other member, for example someone who joined
--    through a leaked invite link. Their sign-in stops working at once and
--    their personal nutrition data is deleted; shared plans, pantry and lists
--    stay.
-- 3. The household's shared data is anchored to the original owner's profile
--    (household_accounts.owner_profile_id). After an ownership transfer that
--    person is a member; when they leave or are removed, their sign-in and
--    personal nutrition data are deleted but the anchor profile stays, so the
--    household's shared data is never touched. (Previously their leaving
--    failed on a foreign-key restriction.)

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS profiles_household_name_unique
    ON public.profiles(household_id, lower(btrim(full_name)));

-- Remove one member's personal data, keeping the household anchor profile.
CREATE OR REPLACE FUNCTION public.remove_member_profile(p_profile_id UUID, p_anchor_profile_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF p_profile_id = p_anchor_profile_id THEN
        DELETE FROM public.macro_diary WHERE profile_id = p_profile_id;
        DELETE FROM public.nutrition_targets WHERE profile_id = p_profile_id;
        INSERT INTO public.nutrition_targets(profile_id) VALUES (p_profile_id);
        RETURN FALSE;
    END IF;
    DELETE FROM public.profiles WHERE id = p_profile_id;
    RETURN TRUE;
END;
$$;

-- Owners delete the whole household; members delete their own login and
-- personal data.
CREATE OR REPLACE FUNCTION public.delete_household_account(p_google_subject TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    account public.household_accounts%ROWTYPE;
BEGIN
    SELECT * INTO account FROM public.household_accounts WHERE google_subject = p_google_subject;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    IF account.role = 'owner' THEN
        DELETE FROM public.household_accounts WHERE household_id = account.household_id;
        DELETE FROM public.households WHERE id = account.household_id;
    ELSE
        DELETE FROM public.household_accounts WHERE google_subject = p_google_subject;
        PERFORM public.remove_member_profile(account.profile_id, account.owner_profile_id);
    END IF;
    RETURN TRUE;
END;
$$;

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

    RETURN jsonb_build_object(
        'removed_profile_id', p_profile_id,
        'had_account', v_has_account,
        'profile_removed', v_profile_removed,
        'household', public.household_account_context(p_google_subject)
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.join_household_with_invite(
    p_google_subject TEXT,
    p_email TEXT,
    p_display_name TEXT,
    p_invite_token_hash TEXT,
    p_profile_id UUID DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    existing public.household_accounts%ROWTYPE;
    v_household_id UUID;
    v_anchor_profile_id UUID;
    v_profile_id UUID;
    v_timezone TEXT;
    v_name TEXT;
    v_order INTEGER;
    v_base TEXT;
    v_suffix INTEGER;
BEGIN
    IF NULLIF(btrim(p_google_subject), '') IS NULL OR NULLIF(btrim(p_email), '') IS NULL THEN
        RAISE EXCEPTION 'verified Google subject and email are required' USING ERRCODE = '22023';
    END IF;

    SELECT h.id, h.timezone_name INTO v_household_id, v_timezone
    FROM public.households h
    WHERE h.invite_token_hash = p_invite_token_hash AND h.invite_expires_at > now()
    FOR UPDATE;
    IF v_household_id IS NULL THEN
        RAISE EXCEPTION 'invite_invalid' USING ERRCODE = 'P0002';
    END IF;

    SELECT * INTO existing FROM public.household_accounts WHERE google_subject = p_google_subject;
    IF FOUND THEN
        IF existing.household_id = v_household_id THEN
            RETURN public.household_account_context(p_google_subject);
        END IF;
        RAISE EXCEPTION 'already_in_household' USING ERRCODE = '23505';
    END IF;

    SELECT a.owner_profile_id INTO v_anchor_profile_id
    FROM public.household_accounts a
    WHERE a.household_id = v_household_id AND a.role = 'owner';

    IF p_profile_id IS NOT NULL THEN
        SELECT p.id INTO v_profile_id
        FROM public.profiles p
        WHERE p.id = p_profile_id AND p.household_id = v_household_id
          AND NOT EXISTS (SELECT 1 FROM public.household_accounts a WHERE a.profile_id = p.id)
        FOR UPDATE;
        IF v_profile_id IS NULL THEN
            RAISE EXCEPTION 'profile_unavailable' USING ERRCODE = '23505';
        END IF;
    ELSE
        v_name := COALESCE(NULLIF(btrim(p_display_name), ''), split_part(p_email, '@', 1));
        -- Names stay unique within a household, so nobody's nutrition log is
        -- ever confused with another member's: add the email name, then a number.
        v_base := v_name;
        v_suffix := 0;
        WHILE EXISTS (
            SELECT 1 FROM public.profiles p
            WHERE p.household_id = v_household_id AND lower(btrim(p.full_name)) = lower(btrim(v_name))
        ) LOOP
            v_suffix := v_suffix + 1;
            v_name := v_base || ' (' || split_part(p_email, '@', 1)
                || CASE WHEN v_suffix > 1 THEN ' ' || v_suffix ELSE '' END || ')';
        END LOOP;
        SELECT COALESCE(max(p.member_order), 0) + 1 INTO v_order
        FROM public.profiles p WHERE p.household_id = v_household_id;
        INSERT INTO public.profiles(
            id, household_id, full_name, household_size, timezone_name,
            member_order, created_at, updated_at
        ) VALUES (
            gen_random_uuid(), v_household_id, v_name, 1, COALESCE(v_timezone, 'UTC'),
            v_order, now(), now()
        ) RETURNING id INTO v_profile_id;
        INSERT INTO public.nutrition_targets(profile_id) VALUES (v_profile_id);
    END IF;

    INSERT INTO public.household_accounts(
        google_subject, household_id, owner_profile_id, profile_id, role, email
    ) VALUES (
        p_google_subject, v_household_id, v_anchor_profile_id, v_profile_id, 'member', p_email
    );

    RETURN public.household_account_context(p_google_subject);
END;
$$;

REVOKE ALL ON FUNCTION public.remove_member_profile(UUID, UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.remove_member_profile(UUID, UUID) TO service_role;
REVOKE ALL ON FUNCTION public.delete_household_account(TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.delete_household_account(TEXT) TO service_role;
REVOKE ALL ON FUNCTION public.remove_household_member(TEXT, UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.remove_household_member(TEXT, UUID) TO service_role;
REVOKE ALL ON FUNCTION public.join_household_with_invite(TEXT, TEXT, TEXT, TEXT, UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.join_household_with_invite(TEXT, TEXT, TEXT, TEXT, UUID) TO service_role;

NOTIFY pgrst, 'reload schema';

COMMIT;
