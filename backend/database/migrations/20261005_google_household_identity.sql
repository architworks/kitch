-- One verified Google identity owns one Kitch household. Household members are
-- stable application profiles rather than authentication identities.

CREATE TABLE IF NOT EXISTS public.households (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timezone_name TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    legacy_claimable BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_id_fkey;
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS household_id UUID REFERENCES public.households(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS member_order INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now());

DO $$
DECLARE
    legacy_household_id UUID;
BEGIN
    IF EXISTS (SELECT 1 FROM public.profiles WHERE household_id IS NULL) THEN
        INSERT INTO public.households(timezone_name, legacy_claimable)
        SELECT COALESCE(max(timezone_name), 'Asia/Kolkata'), TRUE
        FROM public.profiles
        RETURNING id INTO legacy_household_id;

        UPDATE public.profiles
        SET household_id = legacy_household_id,
            member_order = CASE
                WHEN public.profiles.id = '00000000-0000-0000-0000-000000000000'::uuid THEN 0
                ELSE ordered.row_number
            END
        FROM (
            SELECT id, row_number() OVER (ORDER BY created_at, full_name)::integer AS row_number
            FROM public.profiles
        ) ordered
        WHERE public.profiles.id = ordered.id
          AND public.profiles.household_id IS NULL;
    END IF;
END $$;

ALTER TABLE public.profiles ALTER COLUMN household_id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS profiles_household_name_unique
    ON public.profiles(household_id, lower(btrim(full_name)));
CREATE INDEX IF NOT EXISTS profiles_household_order_idx
    ON public.profiles(household_id, member_order, created_at);

CREATE TABLE IF NOT EXISTS public.household_accounts (
    google_subject TEXT PRIMARY KEY CHECK (length(btrim(google_subject)) > 0),
    household_id UUID NOT NULL UNIQUE REFERENCES public.households(id) ON DELETE CASCADE,
    owner_profile_id UUID NOT NULL UNIQUE REFERENCES public.profiles(id) ON DELETE RESTRICT,
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

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
    members JSONB;
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
        WHERE google_subject = p_google_subject
        RETURNING * INTO account;
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
            SELECT id INTO v_owner_profile_id
            FROM public.profiles
            WHERE profiles.household_id = v_household_id
            ORDER BY member_order, created_at
            LIMIT 1;
            UPDATE public.households
            SET legacy_claimable = FALSE, updated_at = now()
            WHERE id = v_household_id;
        ELSE
            INSERT INTO public.households(timezone_name)
            VALUES (COALESCE(NULLIF(btrim(p_timezone_name), ''), 'UTC'))
            RETURNING id INTO v_household_id;

            member_name := COALESCE(NULLIF(btrim(p_display_name), ''), split_part(p_email, '@', 1), 'Household owner');
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
            google_subject, household_id, owner_profile_id, email
        ) VALUES (
            p_google_subject, v_household_id, v_owner_profile_id, p_email
        ) RETURNING * INTO account;
    END IF;

    SELECT COALESCE(jsonb_agg(
        jsonb_build_object('id', p.id, 'name', p.full_name)
        ORDER BY p.member_order, p.created_at
    ), '[]'::jsonb)
    INTO members
    FROM public.profiles p
    WHERE p.household_id = account.household_id;

    RETURN jsonb_build_object(
        'google_subject', account.google_subject,
        'email', account.email,
        'household_id', account.household_id,
        'owner_profile_id', account.owner_profile_id,
        'members', members
    );
END;
$$;

ALTER TABLE public.households ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.household_accounts ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.households, public.household_accounts
    FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.households, public.household_accounts
    TO service_role;
REVOKE ALL ON FUNCTION public.ensure_google_household(TEXT, TEXT, TEXT, TEXT, BOOLEAN)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.ensure_google_household(TEXT, TEXT, TEXT, TEXT, BOOLEAN)
    TO service_role;
