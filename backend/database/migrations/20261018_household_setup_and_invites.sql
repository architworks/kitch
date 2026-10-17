-- Multi-account households: a first-time setup step for new owners, and
-- invite links that let other people join with their own Google account.
--
-- household_accounts.owner_profile_id stays the household's shared-data anchor
-- (meal plans, pantry, carts and memory are keyed by it) for every account in
-- the household. profile_id is the account's own member profile.

ALTER TABLE public.households
    ADD COLUMN IF NOT EXISTS setup_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invite_token_hash TEXT,
    ADD COLUMN IF NOT EXISTS invite_expires_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS households_invite_token_hash_unique
    ON public.households(invite_token_hash) WHERE invite_token_hash IS NOT NULL;

-- Households created before this migration are already set up.
UPDATE public.households SET setup_completed_at = now()
WHERE setup_completed_at IS NULL;

ALTER TABLE public.household_accounts
    ADD COLUMN IF NOT EXISTS profile_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'owner';

UPDATE public.household_accounts SET profile_id = owner_profile_id WHERE profile_id IS NULL;

ALTER TABLE public.household_accounts ALTER COLUMN profile_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'household_accounts_role_check'
    ) THEN
        ALTER TABLE public.household_accounts
            ADD CONSTRAINT household_accounts_role_check CHECK (role IN ('owner', 'member'));
    END IF;
END $$;

ALTER TABLE public.household_accounts DROP CONSTRAINT IF EXISTS household_accounts_household_id_key;
ALTER TABLE public.household_accounts DROP CONSTRAINT IF EXISTS household_accounts_owner_profile_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS household_accounts_profile_unique
    ON public.household_accounts(profile_id);
CREATE UNIQUE INDEX IF NOT EXISTS household_accounts_one_owner
    ON public.household_accounts(household_id) WHERE role = 'owner';

-- Shared result shape for sign-in, join and setup.
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
    SELECT COALESCE(jsonb_agg(
        jsonb_build_object('id', p.id, 'name', p.full_name)
        ORDER BY p.member_order, p.created_at
    ), '[]'::jsonb)
    INTO members
    FROM public.profiles p
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

CREATE OR REPLACE FUNCTION public.ensure_google_household(
    p_google_subject TEXT,
    p_email TEXT,
    p_display_name TEXT,
    p_timezone_name TEXT,
    p_claim_legacy BOOLEAN DEFAULT FALSE
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    account public.household_accounts%ROWTYPE;
    v_household_id UUID;
    v_owner_profile_id UUID;
    member_name TEXT;
BEGIN
    IF NULLIF(btrim(p_google_subject), '') IS NULL OR NULLIF(btrim(p_email), '') IS NULL THEN
        RAISE EXCEPTION 'verified Google subject and email are required' USING ERRCODE = '22023';
    END IF;

    SELECT * INTO account
    FROM public.household_accounts
    WHERE google_subject = p_google_subject
    FOR UPDATE;

    IF FOUND THEN
        UPDATE public.household_accounts
        SET email = p_email, last_seen_at = now()
        WHERE google_subject = p_google_subject;
    ELSE
        IF p_claim_legacy THEN
            SELECT h.id INTO v_household_id
            FROM public.households h
            WHERE h.legacy_claimable = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM public.household_accounts a WHERE a.household_id = h.id
              )
            ORDER BY h.created_at
            LIMIT 1
            FOR UPDATE;
        END IF;

        IF v_household_id IS NOT NULL THEN
            SELECT p.id INTO v_owner_profile_id
            FROM public.profiles p
            WHERE p.household_id = v_household_id
            ORDER BY p.member_order, p.created_at
            LIMIT 1;
            UPDATE public.households
            SET legacy_claimable = FALSE, setup_completed_at = COALESCE(setup_completed_at, now()),
                updated_at = now()
            WHERE id = v_household_id;
        ELSE
            INSERT INTO public.households(timezone_name)
            VALUES (COALESCE(NULLIF(btrim(p_timezone_name), ''), 'UTC'))
            RETURNING id INTO v_household_id;

            member_name := COALESCE(
                NULLIF(btrim(p_display_name), ''), split_part(p_email, '@', 1), 'Household owner'
            );
            INSERT INTO public.profiles(
                id, household_id, full_name, household_size, timezone_name,
                member_order, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), v_household_id, member_name, 1,
                COALESCE(NULLIF(btrim(p_timezone_name), ''), 'UTC'), 0, now(), now()
            ) RETURNING id INTO v_owner_profile_id;
            INSERT INTO public.nutrition_targets(profile_id) VALUES (v_owner_profile_id);
        END IF;

        INSERT INTO public.household_accounts(
            google_subject, household_id, owner_profile_id, profile_id, role, email
        ) VALUES (
            p_google_subject, v_household_id, v_owner_profile_id, v_owner_profile_id, 'owner', p_email
        );
    END IF;

    RETURN public.household_account_context(p_google_subject);
END;
$$;

-- Join an existing household through its current invite link. The joiner
-- either claims an unclaimed member profile (keeping its history) or gets a
-- new profile named after their Google account.
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
        IF EXISTS (
            SELECT 1 FROM public.profiles p
            WHERE p.household_id = v_household_id AND lower(btrim(p.full_name)) = lower(btrim(v_name))
        ) THEN
            v_name := v_name || ' (' || split_part(p_email, '@', 1) || ')';
        END IF;
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

-- First-time setup for a new owner: their own name, other members by name,
-- and how many people the household cooks for.
CREATE OR REPLACE FUNCTION public.complete_household_setup(
    p_google_subject TEXT,
    p_owner_name TEXT,
    p_member_names TEXT[],
    p_household_size INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    account public.household_accounts%ROWTYPE;
    v_timezone TEXT;
    v_name TEXT;
    v_order INTEGER := 0;
    v_profile_id UUID;
BEGIN
    SELECT * INTO account FROM public.household_accounts
    WHERE google_subject = p_google_subject AND role = 'owner';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'owner_required' USING ERRCODE = '42501';
    END IF;
    SELECT timezone_name INTO v_timezone FROM public.households WHERE id = account.household_id FOR UPDATE;

    UPDATE public.profiles SET
        full_name = COALESCE(NULLIF(btrim(p_owner_name), ''), full_name),
        household_size = GREATEST(1, p_household_size),
        updated_at = now()
    WHERE id = account.owner_profile_id;

    FOREACH v_name IN ARRAY COALESCE(p_member_names, ARRAY[]::TEXT[]) LOOP
        v_name := NULLIF(btrim(v_name), '');
        CONTINUE WHEN v_name IS NULL;
        CONTINUE WHEN EXISTS (
            SELECT 1 FROM public.profiles p
            WHERE p.household_id = account.household_id AND lower(btrim(p.full_name)) = lower(v_name)
        );
        v_order := v_order + 1;
        INSERT INTO public.profiles(
            id, household_id, full_name, household_size, timezone_name,
            member_order, created_at, updated_at
        ) VALUES (
            gen_random_uuid(), account.household_id, v_name, 1, COALESCE(v_timezone, 'UTC'),
            v_order, now(), now()
        ) RETURNING id INTO v_profile_id;
        INSERT INTO public.nutrition_targets(profile_id) VALUES (v_profile_id);
    END LOOP;

    UPDATE public.households SET setup_completed_at = now(), updated_at = now()
    WHERE id = account.household_id;

    RETURN public.household_account_context(p_google_subject);
END;
$$;

-- Owners delete the whole household; members delete only their own login and
-- their own member profile (with its nutrition history).
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
        DELETE FROM public.profiles WHERE id = account.profile_id;
    END IF;
    RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION public.household_account_context(TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.household_account_context(TEXT) TO service_role;
REVOKE ALL ON FUNCTION public.join_household_with_invite(TEXT, TEXT, TEXT, TEXT, UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.join_household_with_invite(TEXT, TEXT, TEXT, TEXT, UUID) TO service_role;
REVOKE ALL ON FUNCTION public.complete_household_setup(TEXT, TEXT, TEXT[], INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.complete_household_setup(TEXT, TEXT, TEXT[], INTEGER) TO service_role;
REVOKE ALL ON FUNCTION public.delete_household_account(TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.delete_household_account(TEXT) TO service_role;
REVOKE ALL ON FUNCTION public.ensure_google_household(TEXT, TEXT, TEXT, TEXT, BOOLEAN) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.ensure_google_household(TEXT, TEXT, TEXT, TEXT, BOOLEAN) TO service_role;
