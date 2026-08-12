-- Replace the ambiguous weekday schedule with authoritative dated meal plans.
-- This migration intentionally deletes the existing weekday-only schedule.

BEGIN;

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS timezone_name TEXT NOT NULL DEFAULT 'Asia/Kolkata';

DROP TABLE IF EXISTS public.meal_plans CASCADE;

CREATE TABLE public.meal_plans (
    id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    plan_date DATE NOT NULL,
    breakfast_name TEXT,
    lunch_name TEXT,
    dinner_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT meal_plans_has_meal CHECK (
        NULLIF(btrim(breakfast_name), '') IS NOT NULL
        OR NULLIF(btrim(lunch_name), '') IS NOT NULL
        OR NULLIF(btrim(dinner_name), '') IS NOT NULL
    ),
    UNIQUE (profile_id, plan_date)
);

CREATE INDEX idx_meal_plans_profile_date
    ON public.meal_plans(profile_id, plan_date);

ALTER TABLE public.meal_plans ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.meal_plans FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON SEQUENCE public.meal_plans_id_seq FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.meal_plans TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.meal_plans_id_seq TO service_role;

CREATE OR REPLACE FUNCTION public.replace_meal_plan_range(
    p_profile_id uuid,
    p_start_date date,
    p_end_date date,
    p_days jsonb
)
RETURNS SETOF public.meal_plans
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    expected_count integer;
    household_today date;
BEGIN
    SELECT (now() AT TIME ZONE profile.timezone_name)::date
    INTO household_today
    FROM public.profiles profile
    WHERE profile.id = p_profile_id;
    IF household_today IS NULL THEN
        RAISE EXCEPTION 'household profile is missing' USING ERRCODE = '22023';
    END IF;
    IF p_start_date < household_today THEN
        RAISE EXCEPTION 'past meal-plan dates cannot be replaced' USING ERRCODE = '22023';
    END IF;
    IF p_end_date < p_start_date THEN
        RAISE EXCEPTION 'end date precedes start date' USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(p_days) <> 'array' THEN
        RAISE EXCEPTION 'days must be a JSON array' USING ERRCODE = '22023';
    END IF;

    expected_count := (p_end_date - p_start_date) + 1;
    IF jsonb_array_length(p_days) <> expected_count THEN
        RAISE EXCEPTION 'meal plan must contain exactly one row per requested date'
            USING ERRCODE = '22023';
    END IF;
    IF (
        SELECT count(DISTINCT (item->>'plan_date')::date)
        FROM jsonb_array_elements(p_days) item
        WHERE (item->>'plan_date')::date BETWEEN p_start_date AND p_end_date
    ) <> expected_count THEN
        RAISE EXCEPTION 'meal plan dates must exactly cover the requested range'
            USING ERRCODE = '22023';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM jsonb_array_elements(p_days) item
        WHERE NULLIF(btrim(item->>'breakfast'), '') IS NULL
           OR NULLIF(btrim(item->>'lunch'), '') IS NULL
           OR NULLIF(btrim(item->>'dinner'), '') IS NULL
    ) THEN
        RAISE EXCEPTION 'each replacement date requires breakfast, lunch, and dinner'
            USING ERRCODE = '22023';
    END IF;

    DELETE FROM public.meal_plans
    WHERE profile_id = p_profile_id
      AND plan_date BETWEEN p_start_date AND p_end_date;

    INSERT INTO public.meal_plans (
        profile_id, plan_date, breakfast_name, lunch_name, dinner_name
    )
    SELECT
        p_profile_id,
        (item->>'plan_date')::date,
        NULLIF(btrim(item->>'breakfast'), ''),
        NULLIF(btrim(item->>'lunch'), ''),
        NULLIF(btrim(item->>'dinner'), '')
    FROM jsonb_array_elements(p_days) item;

    RETURN QUERY
    SELECT * FROM public.meal_plans
    WHERE profile_id = p_profile_id
      AND plan_date BETWEEN p_start_date AND p_end_date
    ORDER BY plan_date;
END;
$$;

CREATE OR REPLACE FUNCTION public.apply_meal_plan_edits(
    p_profile_id uuid,
    p_edits jsonb
)
RETURNS SETOF public.meal_plans
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    edit jsonb;
    edit_date date;
    edit_slot text;
    edit_name text;
    household_today date;
BEGIN
    SELECT (now() AT TIME ZONE profile.timezone_name)::date
    INTO household_today
    FROM public.profiles profile
    WHERE profile.id = p_profile_id;
    IF household_today IS NULL THEN
        RAISE EXCEPTION 'household profile is missing' USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(p_edits) <> 'array' OR jsonb_array_length(p_edits) = 0 THEN
        RAISE EXCEPTION 'edits must be a non-empty JSON array' USING ERRCODE = '22023';
    END IF;
    IF (
        SELECT count(*)
        FROM jsonb_array_elements(p_edits) item
        WHERE (item->>'plan_date') IS NULL
    ) > 0 THEN
        RAISE EXCEPTION 'each edit requires plan_date' USING ERRCODE = '22023';
    END IF;

    FOR edit IN SELECT * FROM jsonb_array_elements(p_edits)
    LOOP
        edit_date := (edit->>'plan_date')::date;
        IF edit_date < household_today THEN
            RAISE EXCEPTION 'past meal-plan dates cannot be modified' USING ERRCODE = '22023';
        END IF;
        edit_slot := lower(btrim(edit->>'meal_slot'));
        edit_name := NULLIF(btrim(edit->>'meal_name'), '');
        IF edit_slot NOT IN ('breakfast', 'lunch', 'dinner') OR edit_name IS NULL THEN
            RAISE EXCEPTION 'each edit needs a valid meal slot and non-empty meal name'
                USING ERRCODE = '22023';
        END IF;

        INSERT INTO public.meal_plans (
            profile_id,
            plan_date,
            breakfast_name,
            lunch_name,
            dinner_name
        ) VALUES (
            p_profile_id,
            edit_date,
            CASE WHEN edit_slot = 'breakfast' THEN edit_name END,
            CASE WHEN edit_slot = 'lunch' THEN edit_name END,
            CASE WHEN edit_slot = 'dinner' THEN edit_name END
        )
        ON CONFLICT (profile_id, plan_date) DO UPDATE SET
            breakfast_name = CASE
                WHEN edit_slot = 'breakfast' THEN edit_name
                ELSE meal_plans.breakfast_name
            END,
            lunch_name = CASE
                WHEN edit_slot = 'lunch' THEN edit_name
                ELSE meal_plans.lunch_name
            END,
            dinner_name = CASE
                WHEN edit_slot = 'dinner' THEN edit_name
                ELSE meal_plans.dinner_name
            END,
            updated_at = now();
    END LOOP;

    RETURN QUERY
    SELECT DISTINCT ON (plan.plan_date) plan.*
    FROM public.meal_plans plan
    JOIN (
        SELECT DISTINCT (item->>'plan_date')::date AS plan_date
        FROM jsonb_array_elements(p_edits) item
    ) changed USING (plan_date)
    WHERE plan.profile_id = p_profile_id
    ORDER BY plan.plan_date;
END;
$$;

REVOKE ALL ON FUNCTION public.replace_meal_plan_range(uuid, date, date, jsonb)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.apply_meal_plan_edits(uuid, jsonb)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.replace_meal_plan_range(uuid, date, date, jsonb)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.apply_meal_plan_edits(uuid, jsonb)
    TO service_role;

NOTIFY pgrst, 'reload schema';

COMMIT;
