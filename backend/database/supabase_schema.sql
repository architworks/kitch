-- Kitch: Supabase PostgreSQL Database DDL Schema

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Create User Profiles Table
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    diet_preference TEXT NOT NULL DEFAULT 'balanced' CHECK (diet_preference IN ('balanced', 'keto', 'vegan', 'high-protein')),
    household_size INTEGER NOT NULL DEFAULT 3 CHECK (household_size >= 1),
    daily_calorie_target INTEGER NOT NULL DEFAULT 2000,
    timezone_name TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Create Date-Specific Meal Plans Table
CREATE TABLE IF NOT EXISTS public.meal_plans (
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

-- 3. Create Pantry & Fridge Stock Table
CREATE TABLE IF NOT EXISTS public.pantry_stock (
    id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (amount >= 0.00),
    unit TEXT NOT NULL DEFAULT 'piece',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (profile_id, ingredient_name)
);

-- 4. Create Recipe + Grocery Plan Artifact Table
CREATE TABLE IF NOT EXISTS public.recipe_grocery_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    request_text TEXT NOT NULL DEFAULT '',
    recipe_cards JSONB NOT NULL DEFAULT '[]'::jsonb,
    ingredients JSONB NOT NULL DEFAULT '[]'::jsonb,
    pantry_considerations JSONB NOT NULL DEFAULT '[]'::jsonb,
    household_size INTEGER NOT NULL DEFAULT 3 CHECK (household_size >= 1),
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'agent' CHECK (source IN ('agent', 'manual')),
    updates_cart BOOLEAN NOT NULL DEFAULT FALSE,
    cart_item_count INTEGER NOT NULL DEFAULT 0 CHECK (cart_item_count >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.recipe_grocery_plans
    ADD COLUMN IF NOT EXISTS updates_cart BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.recipe_grocery_plans
    ADD COLUMN IF NOT EXISTS cart_item_count INTEGER NOT NULL DEFAULT 0 CHECK (cart_item_count >= 0);


-- 5. Create Shared Native Grocery Cart Table
CREATE TABLE IF NOT EXISTS public.grocery_cart_items (
    id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    recipe_grocery_plan_id UUID REFERENCES public.recipe_grocery_plans(id) ON DELETE SET NULL,
    ingredient_name TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL DEFAULT 1.00 CHECK (amount >= 0.00),
    unit TEXT NOT NULL DEFAULT 'piece',
    category TEXT NOT NULL DEFAULT 'General',
    source TEXT NOT NULL DEFAULT 'agent' CHECK (source IN ('agent', 'manual')),
    checked BOOLEAN NOT NULL DEFAULT FALSE,
    already_stocked BOOLEAN NOT NULL DEFAULT FALSE,
    stock_note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.grocery_cart_items
    ADD COLUMN IF NOT EXISTS recipe_grocery_plan_id UUID REFERENCES public.recipe_grocery_plans(id) ON DELETE SET NULL;

-- 6. Create Daily Macro Intake Journal Table
CREATE TABLE IF NOT EXISTS public.macro_diary (
    id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    meal_name TEXT NOT NULL,
    calories INTEGER NOT NULL DEFAULT 0 CHECK (calories >= 0),
    protein_g INTEGER NOT NULL DEFAULT 0 CHECK (protein_g >= 0),
    carbs_g INTEGER NOT NULL DEFAULT 0 CHECK (carbs_g >= 0),
    fat_g INTEGER NOT NULL DEFAULT 0 CHECK (fat_g >= 0),
    fiber_g INTEGER NOT NULL DEFAULT 0 CHECK (fiber_g >= 0),
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 7. Create Durable Provider Checkout Draft Table
CREATE TABLE IF NOT EXISTS public.provider_checkout_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (length(btrim(provider)) > 0),
    selected_address_id TEXT NOT NULL DEFAULT '',
    selected_native_item_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    native_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    mapped_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    matched_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    unavailable_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    replacements JSONB NOT NULL DEFAULT '[]'::jsonb,
    changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    provider_cart JSONB,
    cart_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    checkout_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    store_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    selected_payment_method_id TEXT,
    order_review_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    can_place_order BOOLEAN NOT NULL DEFAULT FALSE,
    order_blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
    confirmation_token TEXT,
    snapshot_hash TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'ready', 'changed', 'blocked', 'ordered')),
    last_validated_at TIMESTAMP WITH TIME ZONE,
    operation_id UUID,
    lease_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (profile_id, provider)
);

-- --- INDEXING FOR OPTIMAL QUERY PERFORMANCE ---
CREATE INDEX IF NOT EXISTS idx_meal_plans_profile_date ON public.meal_plans(profile_id, plan_date);
CREATE INDEX IF NOT EXISTS idx_pantry_stock_profile_id ON public.pantry_stock(profile_id);
CREATE INDEX IF NOT EXISTS idx_recipe_grocery_plans_profile_created_at ON public.recipe_grocery_plans(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_id ON public.grocery_cart_items(profile_id);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_source ON public.grocery_cart_items(profile_id, source);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_recipe_plan ON public.grocery_cart_items(profile_id, recipe_grocery_plan_id);
CREATE INDEX IF NOT EXISTS idx_macro_diary_profile_id_date ON public.macro_diary(profile_id, logged_at);
CREATE INDEX IF NOT EXISTS idx_provider_checkout_drafts_profile_provider
    ON public.provider_checkout_drafts(profile_id, provider);

-- --- BACKEND-ONLY SECURITY ---
-- Kitch's browser talks only to FastAPI. The backend uses a Supabase secret
-- key (or temporary legacy service_role key), which bypasses RLS.
DO $$
DECLARE
    table_name text;
    policy_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'profiles',
        'meal_plans',
        'pantry_stock',
        'recipe_grocery_plans',
        'grocery_cart_items',
        'macro_diary',
        'provider_checkout_drafts'
    ]
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);

        FOR policy_name IN
            SELECT policyname
            FROM pg_policies
            WHERE schemaname = 'public' AND tablename = table_name
        LOOP
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', policy_name, table_name);
        END LOOP;

        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM PUBLIC, anon, authenticated',
            table_name
        );
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO service_role',
            table_name
        );
    END LOOP;
END
$$;

REVOKE ALL PRIVILEGES ON SEQUENCE public.meal_plans_id_seq FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON SEQUENCE public.pantry_stock_id_seq FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON SEQUENCE public.grocery_cart_items_id_seq FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON SEQUENCE public.macro_diary_id_seq FROM PUBLIC, anon, authenticated;

GRANT USAGE, SELECT ON SEQUENCE public.meal_plans_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.pantry_stock_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.grocery_cart_items_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.macro_diary_id_seq TO service_role;

-- --- TRANSACTIONAL DATE-SPECIFIC MEAL PLANNING ---
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
    IF jsonb_array_length(p_days) <> expected_count OR (
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
            profile_id, plan_date, breakfast_name, lunch_name, dinner_name
        ) VALUES (
            p_profile_id,
            edit_date,
            CASE WHEN edit_slot = 'breakfast' THEN edit_name END,
            CASE WHEN edit_slot = 'lunch' THEN edit_name END,
            CASE WHEN edit_slot = 'dinner' THEN edit_name END
        )
        ON CONFLICT (profile_id, plan_date) DO UPDATE SET
            breakfast_name = CASE WHEN edit_slot = 'breakfast' THEN edit_name ELSE meal_plans.breakfast_name END,
            lunch_name = CASE WHEN edit_slot = 'lunch' THEN edit_name ELSE meal_plans.lunch_name END,
            dinner_name = CASE WHEN edit_slot = 'dinner' THEN edit_name ELSE meal_plans.dinner_name END,
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

-- --- PROVIDER CHECKOUT OPERATION LEASES ---
CREATE OR REPLACE FUNCTION public.claim_provider_checkout_operation(
    p_profile_id uuid,
    p_provider text,
    p_operation_id uuid,
    p_lease_seconds integer DEFAULT 120
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    affected_rows integer := 0;
BEGIN
    INSERT INTO public.provider_checkout_drafts (profile_id, provider)
    VALUES (p_profile_id, p_provider)
    ON CONFLICT (profile_id, provider) DO NOTHING;

    UPDATE public.provider_checkout_drafts
    SET operation_id = p_operation_id,
        lease_expires_at = now() + make_interval(secs => GREATEST(1, p_lease_seconds)),
        updated_at = now()
    WHERE profile_id = p_profile_id
      AND provider = p_provider
      AND (
          operation_id IS NULL
          OR lease_expires_at IS NULL
          OR lease_expires_at <= now()
          OR operation_id = p_operation_id
      );

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows > 0;
END;
$$;

CREATE OR REPLACE FUNCTION public.release_provider_checkout_operation(
    p_profile_id uuid,
    p_provider text,
    p_operation_id uuid
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    affected_rows integer := 0;
BEGIN
    UPDATE public.provider_checkout_drafts
    SET operation_id = NULL,
        lease_expires_at = NULL,
        updated_at = now()
    WHERE profile_id = p_profile_id
      AND provider = p_provider
      AND operation_id = p_operation_id;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows > 0;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_provider_checkout_operation(uuid, text, uuid, integer)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.release_provider_checkout_operation(uuid, text, uuid)
    FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.claim_provider_checkout_operation(uuid, text, uuid, integer)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.release_provider_checkout_operation(uuid, text, uuid)
    TO service_role;

-- --- TRANSACTIONAL RECIPE/CART PERSISTENCE ---
CREATE OR REPLACE FUNCTION public.replace_planned_grocery_cart(
    p_profile_id uuid,
    p_cart_items jsonb DEFAULT '[]'::jsonb,
    p_recipe_grocery_plan_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    saved_cart jsonb;
BEGIN
    IF jsonb_typeof(COALESCE(p_cart_items, '[]'::jsonb)) <> 'array' THEN
        RAISE EXCEPTION 'p_cart_items must be a JSON array' USING ERRCODE = '22023';
    END IF;

    DELETE FROM public.grocery_cart_items
    WHERE profile_id = p_profile_id AND source = 'agent';

    INSERT INTO public.grocery_cart_items (
        profile_id, recipe_grocery_plan_id, ingredient_name, amount, unit,
        category, source, checked, already_stocked, stock_note
    )
    SELECT
        p_profile_id,
        p_recipe_grocery_plan_id,
        item.ingredient_name,
        COALESCE(item.amount, 1),
        COALESCE(NULLIF(item.unit, ''), 'piece'),
        COALESCE(NULLIF(item.category, ''), 'General'),
        'agent',
        COALESCE(item.checked, FALSE),
        COALESCE(item.already_stocked, FALSE),
        COALESCE(item.stock_note, '')
    FROM jsonb_to_recordset(COALESCE(p_cart_items, '[]'::jsonb)) AS item(
        ingredient_name text,
        amount numeric,
        unit text,
        category text,
        checked boolean,
        already_stocked boolean,
        stock_note text
    );

    SELECT COALESCE(jsonb_agg(to_jsonb(cart_row) ORDER BY cart_row.id), '[]'::jsonb)
    INTO saved_cart
    FROM public.grocery_cart_items AS cart_row
    WHERE cart_row.profile_id = p_profile_id;

    RETURN saved_cart;
END;
$$;

CREATE OR REPLACE FUNCTION public.save_recipe_grocery_plan_with_cart(
    p_plan_id uuid,
    p_profile_id uuid,
    p_scope jsonb,
    p_request_text text,
    p_recipe_cards jsonb,
    p_ingredients jsonb,
    p_pantry_considerations jsonb,
    p_household_size integer,
    p_notes text,
    p_source text,
    p_updates_cart boolean,
    p_cart_items jsonb DEFAULT '[]'::jsonb,
    p_created_at timestamptz DEFAULT now(),
    p_updated_at timestamptz DEFAULT now()
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    saved_plan public.recipe_grocery_plans%ROWTYPE;
    saved_cart jsonb;
BEGIN
    IF jsonb_typeof(COALESCE(p_cart_items, '[]'::jsonb)) <> 'array' THEN
        RAISE EXCEPTION 'p_cart_items must be a JSON array' USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.recipe_grocery_plans (
        id, profile_id, scope, request_text, recipe_cards, ingredients,
        pantry_considerations, household_size, notes, source, updates_cart,
        cart_item_count, created_at, updated_at
    )
    VALUES (
        p_plan_id, p_profile_id, COALESCE(p_scope, '{}'::jsonb),
        COALESCE(p_request_text, ''), COALESCE(p_recipe_cards, '[]'::jsonb),
        COALESCE(p_ingredients, '[]'::jsonb),
        COALESCE(p_pantry_considerations, '[]'::jsonb), p_household_size,
        COALESCE(p_notes, ''), p_source, p_updates_cart,
        CASE WHEN p_updates_cart THEN jsonb_array_length(COALESCE(p_cart_items, '[]'::jsonb)) ELSE 0 END,
        p_created_at, p_updated_at
    )
    ON CONFLICT (id) DO UPDATE SET
        scope = EXCLUDED.scope,
        request_text = EXCLUDED.request_text,
        recipe_cards = EXCLUDED.recipe_cards,
        ingredients = EXCLUDED.ingredients,
        pantry_considerations = EXCLUDED.pantry_considerations,
        household_size = EXCLUDED.household_size,
        notes = EXCLUDED.notes,
        source = EXCLUDED.source,
        updates_cart = EXCLUDED.updates_cart,
        cart_item_count = EXCLUDED.cart_item_count,
        updated_at = EXCLUDED.updated_at
    RETURNING * INTO saved_plan;

    IF p_updates_cart THEN
        saved_cart := public.replace_planned_grocery_cart(
            p_profile_id, p_cart_items, saved_plan.id
        );
    ELSE
        SELECT COALESCE(jsonb_agg(to_jsonb(cart_row) ORDER BY cart_row.id), '[]'::jsonb)
        INTO saved_cart
        FROM public.grocery_cart_items AS cart_row
        WHERE cart_row.profile_id = p_profile_id;
    END IF;

    RETURN jsonb_build_object(
        'plan', to_jsonb(saved_plan),
        'cart', COALESCE(saved_cart, '[]'::jsonb)
    );
END;
$$;

REVOKE ALL ON FUNCTION public.replace_planned_grocery_cart(uuid, jsonb, uuid)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.save_recipe_grocery_plan_with_cart(
    uuid, uuid, jsonb, text, jsonb, jsonb, jsonb, integer, text, text,
    boolean, jsonb, timestamptz, timestamptz
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.replace_planned_grocery_cart(uuid, jsonb, uuid)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.save_recipe_grocery_plan_with_cart(
    uuid, uuid, jsonb, text, jsonb, jsonb, jsonb, integer, text, text,
    boolean, jsonb, timestamptz, timestamptz
) TO service_role;
