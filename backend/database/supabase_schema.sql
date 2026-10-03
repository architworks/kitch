-- Kitch: Supabase PostgreSQL Database DDL Schema

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Create User Profiles Table
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    household_size INTEGER NOT NULL DEFAULT 3 CHECK (household_size >= 1),
    timezone_name TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    pantry_revision BIGINT NOT NULL DEFAULT 0,
    pantry_reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Nutrition goals are user-specific operational state, not household-profile
-- preferences.
CREATE TABLE IF NOT EXISTS public.nutrition_targets (
    profile_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    daily_calorie_target INTEGER NOT NULL DEFAULT 2000 CHECK (daily_calorie_target > 0),
    protein_target_g INTEGER NOT NULL DEFAULT 150 CHECK (protein_target_g > 0),
    carbs_target_g INTEGER NOT NULL DEFAULT 200 CHECK (carbs_target_g > 0),
    fat_target_g INTEGER NOT NULL DEFAULT 67 CHECK (fat_target_g > 0),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- The last provider selected in the checkout UI is operational workflow state,
-- not a semantic household preference.
CREATE TABLE IF NOT EXISTS public.provider_selection_state (
    profile_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    selected_provider TEXT NOT NULL CHECK (length(btrim(selected_provider)) > 0),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
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
    purchase_amount NUMERIC(10,2) NOT NULL DEFAULT 1.00 CHECK (purchase_amount >= 0.00),
    purchase_unit TEXT NOT NULL DEFAULT 'piece',
    pantry_allocation JSONB NOT NULL DEFAULT '{}'::jsonb,
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
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 7. Create Durable Provider Checkout Draft Table
CREATE TABLE IF NOT EXISTS public.provider_checkout_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (length(btrim(provider)) > 0),
    provider_environment TEXT NOT NULL DEFAULT 'production'
        CHECK (provider_environment IN ('local', 'staging', 'production')),
    capability_version TEXT NOT NULL DEFAULT '',
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
    payment_options JSONB NOT NULL DEFAULT '[]'::jsonb,
    selected_payment_method_id TEXT,
    selected_payment_method JSONB,
    payment_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    order_review_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    can_place_order BOOLEAN NOT NULL DEFAULT FALSE,
    order_blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
    confirmation_token TEXT,
    snapshot_hash TEXT NOT NULL DEFAULT '',
    checkout_attempt_id UUID,
    provider_order_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    order_results JSONB NOT NULL DEFAULT '[]'::jsonb,
    ambiguous_order BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft', 'syncing', 'ready', 'changed', 'blocked',
            'checkout_pending', 'payment_pending', 'ordered', 'unknown'
        )),
    last_validated_at TIMESTAMP WITH TIME ZONE,
    operation_id UUID,
    lease_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (profile_id, provider, provider_environment)
);

CREATE TABLE IF NOT EXISTS public.provider_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_environment TEXT NOT NULL CHECK (provider_environment IN ('local', 'staging', 'production')),
    access_token_ciphertext TEXT NOT NULL,
    token_type TEXT NOT NULL DEFAULT 'Bearer',
    scope TEXT NOT NULL DEFAULT '',
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status TEXT NOT NULL DEFAULT 'connected' CHECK (status IN ('connected', 'reconnect_required', 'revoked', 'failed')),
    last_error_code TEXT,
    connected_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (profile_id, provider, provider_environment)
);

CREATE TABLE IF NOT EXISTS public.provider_oauth_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    provider_environment TEXT NOT NULL CHECK (provider_environment IN ('local', 'staging', 'production')),
    client_id TEXT NOT NULL,
    registration JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (provider, provider_environment)
);

CREATE TABLE IF NOT EXISTS public.provider_oauth_flows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_environment TEXT NOT NULL CHECK (provider_environment IN ('local', 'staging', 'production')),
    state_hash TEXT NOT NULL UNIQUE,
    code_verifier_ciphertext TEXT NOT NULL,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE TABLE IF NOT EXISTS public.pending_agent_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    active_user TEXT NOT NULL DEFAULT '',
    action_type TEXT NOT NULL CHECK (length(btrim(action_type)) > 0),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    impact_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending'
        CONSTRAINT pending_agent_actions_status_check
        CHECK (status IN ('pending', 'executing', 'confirmed', 'cancelled', 'expired', 'failed')),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (now() + interval '10 minutes'),
    consumed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.pending_agent_actions
    DROP CONSTRAINT IF EXISTS pending_agent_actions_status_check;
ALTER TABLE public.pending_agent_actions
    ADD CONSTRAINT pending_agent_actions_status_check
    CHECK (status IN ('pending', 'executing', 'confirmed', 'cancelled', 'expired', 'failed'));

-- --- INDEXING FOR OPTIMAL QUERY PERFORMANCE ---
CREATE INDEX IF NOT EXISTS idx_meal_plans_profile_date ON public.meal_plans(profile_id, plan_date);
CREATE INDEX IF NOT EXISTS idx_pantry_stock_profile_id ON public.pantry_stock(profile_id);
CREATE INDEX IF NOT EXISTS idx_recipe_grocery_plans_profile_created_at ON public.recipe_grocery_plans(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_id ON public.grocery_cart_items(profile_id);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_source ON public.grocery_cart_items(profile_id, source);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_recipe_plan ON public.grocery_cart_items(profile_id, recipe_grocery_plan_id);
CREATE INDEX IF NOT EXISTS idx_macro_diary_profile_id_date ON public.macro_diary(profile_id, logged_at);
CREATE INDEX IF NOT EXISTS idx_provider_checkout_drafts_profile_provider
    ON public.provider_checkout_drafts(profile_id, provider, provider_environment);
CREATE INDEX IF NOT EXISTS idx_provider_connections_profile_provider
    ON public.provider_connections(profile_id, provider, provider_environment);
CREATE INDEX IF NOT EXISTS idx_provider_oauth_flows_expiry
    ON public.provider_oauth_flows(expires_at);
CREATE INDEX IF NOT EXISTS idx_pending_agent_actions_profile_status
    ON public.pending_agent_actions(profile_id, status, expires_at);

CREATE OR REPLACE FUNCTION public.claim_pending_agent_action(
    p_profile_id uuid, p_action_id uuid
)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE claimed public.pending_agent_actions%ROWTYPE;
BEGIN
    UPDATE public.pending_agent_actions SET
        status = 'executing', updated_at = now()
    WHERE profile_id = p_profile_id AND id = p_action_id
      AND status = 'pending' AND expires_at > now()
    RETURNING * INTO claimed;
    IF NOT FOUND THEN RETURN NULL; END IF;
    RETURN to_jsonb(claimed);
END; $$;

REVOKE ALL ON FUNCTION public.claim_pending_agent_action(uuid, uuid)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_pending_agent_action(uuid, uuid) TO service_role;

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
        'nutrition_targets',
        'provider_selection_state',
        'meal_plans',
        'pantry_stock',
        'recipe_grocery_plans',
        'grocery_cart_items',
        'macro_diary',
        'provider_checkout_drafts',
        'provider_connections',
        'provider_oauth_clients',
        'provider_oauth_flows',
        'pending_agent_actions'
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
    p_provider_environment text,
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
    INSERT INTO public.provider_checkout_drafts (profile_id, provider, provider_environment)
    VALUES (p_profile_id, p_provider, p_provider_environment)
    ON CONFLICT (profile_id, provider, provider_environment) DO NOTHING;

    UPDATE public.provider_checkout_drafts
    SET operation_id = p_operation_id,
        lease_expires_at = now() + make_interval(secs => GREATEST(1, p_lease_seconds)),
        updated_at = now()
    WHERE profile_id = p_profile_id
      AND provider = p_provider
      AND provider_environment = p_provider_environment
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
    p_provider_environment text,
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
      AND provider_environment = p_provider_environment
      AND operation_id = p_operation_id;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows > 0;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_provider_checkout_operation(uuid, text, text, uuid, integer)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.release_provider_checkout_operation(uuid, text, text, uuid)
    FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.claim_provider_checkout_operation(uuid, text, text, uuid, integer)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.release_provider_checkout_operation(uuid, text, text, uuid)
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

    IF p_recipe_grocery_plan_id IS NOT NULL THEN
        DELETE FROM public.grocery_cart_items
        WHERE profile_id = p_profile_id AND source = 'agent'
          AND recipe_grocery_plan_id = p_recipe_grocery_plan_id;
    ELSE
        DELETE FROM public.grocery_cart_items
        WHERE profile_id = p_profile_id AND source = 'agent';
    END IF;

    INSERT INTO public.grocery_cart_items (
        profile_id, recipe_grocery_plan_id, ingredient_name, amount, unit,
        category, source, checked, purchase_amount, purchase_unit, pantry_allocation
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
        COALESCE(item.purchase_amount, item.amount, 1),
        COALESCE(NULLIF(item.purchase_unit, ''), NULLIF(item.unit, ''), 'piece'),
        COALESCE(item.pantry_allocation, '{}'::jsonb)
    FROM jsonb_to_recordset(COALESCE(p_cart_items, '[]'::jsonb)) AS item(
        ingredient_name text,
        amount numeric,
        unit text,
        category text,
        checked boolean,
        purchase_amount numeric,
        purchase_unit text,
        pantry_allocation jsonb
    );

    SELECT COALESCE(jsonb_agg(to_jsonb(cart_row) ORDER BY cart_row.id), '[]'::jsonb)
    INTO saved_cart
    FROM public.grocery_cart_items AS cart_row
    WHERE cart_row.profile_id = p_profile_id;

    DELETE FROM public.provider_checkout_drafts WHERE profile_id = p_profile_id;

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
    plan_preexisted boolean;
BEGIN
    IF jsonb_typeof(COALESCE(p_cart_items, '[]'::jsonb)) <> 'array' THEN
        RAISE EXCEPTION 'p_cart_items must be a JSON array' USING ERRCODE = '22023';
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM public.recipe_grocery_plans
        WHERE id = p_plan_id AND profile_id = p_profile_id
    ) INTO plan_preexisted;

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
        IF NOT plan_preexisted THEN
            DELETE FROM public.grocery_cart_items
            WHERE profile_id = p_profile_id AND source = 'agent';
        END IF;
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

-- --- TRANSACTIONAL STANDALONE NATIVE-CART CHANGES ---
CREATE OR REPLACE FUNCTION public.apply_native_grocery_cart_changes(
    p_profile_id uuid,
    p_changes jsonb
)
RETURNS SETOF public.grocery_cart_items
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    change jsonb;
    change_action text;
    requested_name text;
    requested_unit text;
    requested_amount numeric;
    target_id bigint;
    target_count integer;
BEGIN
    IF jsonb_typeof(p_changes) <> 'array' OR jsonb_array_length(p_changes) = 0 THEN
        RAISE EXCEPTION 'changes must be a non-empty JSON array'
            USING ERRCODE = '22023';
    END IF;

    FOR change IN SELECT * FROM jsonb_array_elements(p_changes)
    LOOP
        IF jsonb_typeof(change) <> 'object' THEN
            RAISE EXCEPTION 'each native-cart change must be an object'
                USING ERRCODE = '22023';
        END IF;

        change_action := lower(btrim(COALESCE(change->>'action', 'add')));
        requested_name := NULLIF(btrim(COALESCE(change->>'name', change->>'item')), '');
        requested_unit := COALESCE(NULLIF(btrim(change->>'unit'), ''), 'piece');
        target_id := NULL;
        target_count := 0;

        IF change_action = 'add' THEN
            IF requested_name IS NULL THEN
                RAISE EXCEPTION 'an item name is required for add'
                    USING ERRCODE = '22023';
            END IF;
            BEGIN
                requested_amount := COALESCE(
                    NULLIF(change->>'amount', '')::numeric,
                    NULLIF(change->>'quantity', '')::numeric,
                    1
                );
            EXCEPTION WHEN invalid_text_representation THEN
                RAISE EXCEPTION 'the amount for % must be numeric', requested_name
                    USING ERRCODE = '22023';
            END;
            IF requested_amount <= 0 THEN
                RAISE EXCEPTION 'the amount for % must be greater than zero', requested_name
                    USING ERRCODE = '22023';
            END IF;

            SELECT count(*), min(cart.id)
            INTO target_count, target_id
            FROM public.grocery_cart_items cart
            WHERE cart.profile_id = p_profile_id
              AND lower(btrim(cart.ingredient_name)) = lower(requested_name)
              AND lower(btrim(cart.unit)) = lower(requested_unit);

            IF target_count > 1 THEN
                RAISE EXCEPTION 'more than one native-cart row matches % %; use item_id',
                    requested_name, requested_unit USING ERRCODE = '22023';
            ELSIF target_count = 1 THEN
                UPDATE public.grocery_cart_items
                SET amount = amount + requested_amount,
                    purchase_amount = purchase_amount + requested_amount,
                    updated_at = now()
                WHERE profile_id = p_profile_id AND id = target_id;
            ELSE
                INSERT INTO public.grocery_cart_items (
                    profile_id, ingredient_name, amount, unit, category, source,
                    checked, purchase_amount, purchase_unit, pantry_allocation
                ) VALUES (
                    p_profile_id,
                    requested_name,
                    requested_amount,
                    requested_unit,
                    COALESCE(NULLIF(btrim(change->>'category'), ''), 'General'),
                    'manual',
                    COALESCE((change->>'checked')::boolean, false),
                    requested_amount,
                    requested_unit,
                    '{}'::jsonb
                );
            END IF;

        ELSIF change_action IN ('set', 'update', 'remove', 'delete') THEN
            IF NULLIF(btrim(change->>'item_id'), '') IS NOT NULL
               OR NULLIF(btrim(change->>'id'), '') IS NOT NULL THEN
                BEGIN
                    target_id := COALESCE(
                        NULLIF(btrim(change->>'item_id'), '')::bigint,
                        NULLIF(btrim(change->>'id'), '')::bigint
                    );
                EXCEPTION WHEN invalid_text_representation THEN
                    RAISE EXCEPTION 'item_id must be an integer' USING ERRCODE = '22023';
                END;
                SELECT count(*) INTO target_count
                FROM public.grocery_cart_items cart
                WHERE cart.profile_id = p_profile_id AND cart.id = target_id;
            ELSE
                IF requested_name IS NULL THEN
                    RAISE EXCEPTION 'item_id or exact item name is required for %', change_action
                        USING ERRCODE = '22023';
                END IF;
                SELECT count(*), min(cart.id)
                INTO target_count, target_id
                FROM public.grocery_cart_items cart
                WHERE cart.profile_id = p_profile_id
                  AND lower(btrim(cart.ingredient_name)) = lower(requested_name)
                  AND (
                      NULLIF(btrim(change->>'unit'), '') IS NULL
                      OR lower(btrim(cart.unit)) = lower(btrim(change->>'unit'))
                  );
            END IF;

            IF target_count = 0 THEN
                RAISE EXCEPTION 'the native-cart row to % was not found', change_action
                    USING ERRCODE = '22023';
            ELSIF target_count > 1 THEN
                RAISE EXCEPTION 'more than one native-cart row matches; use item_id'
                    USING ERRCODE = '22023';
            END IF;

            IF change_action IN ('remove', 'delete') THEN
                DELETE FROM public.grocery_cart_items
                WHERE profile_id = p_profile_id AND id = target_id;
            ELSE
                IF change ? 'amount' THEN
                    BEGIN
                        requested_amount := (change->>'amount')::numeric;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'the updated amount must be numeric'
                            USING ERRCODE = '22023';
                    END;
                    IF requested_amount <= 0 THEN
                        RAISE EXCEPTION 'the updated amount must be greater than zero'
                            USING ERRCODE = '22023';
                    END IF;
                END IF;
                IF change ? 'name' AND NULLIF(btrim(change->>'name'), '') IS NULL THEN
                    RAISE EXCEPTION 'the updated item name cannot be empty'
                        USING ERRCODE = '22023';
                END IF;
                IF change ? 'unit' AND NULLIF(btrim(change->>'unit'), '') IS NULL THEN
                    RAISE EXCEPTION 'the updated unit cannot be empty'
                        USING ERRCODE = '22023';
                END IF;

                UPDATE public.grocery_cart_items
                SET ingredient_name = CASE WHEN change ? 'name' THEN btrim(change->>'name') ELSE ingredient_name END,
                    amount = CASE WHEN change ? 'amount' THEN requested_amount ELSE amount END,
                    unit = CASE WHEN change ? 'unit' THEN btrim(change->>'unit') ELSE unit END,
                    category = CASE
                        WHEN change ? 'category' THEN COALESCE(NULLIF(btrim(change->>'category'), ''), 'General')
                        ELSE category
                    END,
                    checked = CASE WHEN change ? 'checked' THEN (change->>'checked')::boolean ELSE checked END,
                    purchase_amount = CASE
                        WHEN change ? 'purchase_amount' THEN (change->>'purchase_amount')::numeric
                        WHEN change ? 'amount' THEN requested_amount
                        ELSE purchase_amount
                    END,
                    purchase_unit = CASE WHEN change ? 'unit' THEN btrim(change->>'unit') ELSE purchase_unit END,
                    pantry_allocation = CASE
                        WHEN change ? 'amount' OR change ? 'unit' THEN '{}'::jsonb
                        ELSE pantry_allocation
                    END,
                    updated_at = now()
                WHERE profile_id = p_profile_id AND id = target_id;
            END IF;
        ELSE
            RAISE EXCEPTION 'unsupported native-cart action %', change_action
                USING ERRCODE = '22023';
        END IF;
    END LOOP;

    DELETE FROM public.provider_checkout_drafts WHERE profile_id = p_profile_id;

    RETURN QUERY
    SELECT cart.*
    FROM public.grocery_cart_items cart
    WHERE cart.profile_id = p_profile_id
    ORDER BY cart.category, cart.ingredient_name;
END;
$$;

REVOKE ALL ON FUNCTION public.apply_native_grocery_cart_changes(uuid, jsonb)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.apply_native_grocery_cart_changes(uuid, jsonb)
    TO service_role;

-- --- TRANSACTIONAL REVISIONED PANTRY (DOES NOT IMPLICITLY CHANGE THE CART) ---
DROP FUNCTION IF EXISTS public.apply_pantry_inventory_change(UUID, BIGINT, TEXT, JSONB, JSONB);

CREATE OR REPLACE FUNCTION public.apply_pantry_inventory_change(
    p_profile_id UUID, p_expected_revision BIGINT, p_mode TEXT,
    p_items JSONB
)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE
    current_revision BIGINT; current_reviewed_at TIMESTAMPTZ; item JSONB; item_id BIGINT; item_name TEXT;
    item_unit TEXT; item_amount NUMERIC; operation TEXT;
    saved_pantry JSONB;
BEGIN
    IF p_mode NOT IN ('patch', 'replace') THEN
        RAISE EXCEPTION 'pantry mode must be patch or replace' USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(COALESCE(p_items, '[]'::jsonb)) <> 'array' THEN
        RAISE EXCEPTION 'pantry items must be an array' USING ERRCODE = '22023';
    END IF;
    SELECT pantry_revision, pantry_reviewed_at INTO current_revision, current_reviewed_at FROM public.profiles
    WHERE id = p_profile_id FOR UPDATE;
    IF current_revision IS NULL THEN
        RAISE EXCEPTION 'household profile is missing' USING ERRCODE = '22023';
    END IF;
    IF current_revision <> p_expected_revision THEN
        RAISE EXCEPTION 'pantry revision conflict' USING ERRCODE = '40001';
    END IF;
    IF p_mode = 'replace' THEN
        DELETE FROM public.pantry_stock WHERE profile_id = p_profile_id;
        FOR item IN SELECT * FROM jsonb_array_elements(COALESCE(p_items, '[]'::jsonb)) LOOP
            item_name := NULLIF(btrim(item->>'name'), '');
            item_unit := COALESCE(NULLIF(btrim(item->>'unit'), ''), 'piece');
            item_amount := COALESCE((item->>'amount')::numeric, 0);
            IF item_name IS NULL OR item_amount < 0 THEN
                RAISE EXCEPTION 'replacement items need a name and nonnegative amount' USING ERRCODE = '22023';
            END IF;
            IF item_amount > 0 THEN
                INSERT INTO public.pantry_stock(profile_id, ingredient_name, amount, unit, updated_at)
                VALUES (p_profile_id, item_name, item_amount, item_unit, now());
            END IF;
        END LOOP;
    ELSE
        IF jsonb_array_length(p_items) = 0 THEN
            RAISE EXCEPTION 'patch requires at least one operation' USING ERRCODE = '22023';
        END IF;
        FOR item IN SELECT * FROM jsonb_array_elements(p_items) LOOP
            operation := lower(btrim(COALESCE(item->>'action', '')));
            item_name := NULLIF(btrim(item->>'name'), '');
            item_unit := COALESCE(NULLIF(btrim(item->>'unit'), ''), 'piece');
            item_id := NULLIF(item->>'id', '')::bigint;
            IF operation = 'add' THEN
                item_amount := COALESCE((item->>'amount')::numeric, 0);
                IF item_name IS NULL OR item_amount <= 0 THEN
                    RAISE EXCEPTION 'add requires a name and positive amount' USING ERRCODE = '22023';
                END IF;
                UPDATE public.pantry_stock SET amount = amount + item_amount,
                    updated_at = now()
                WHERE profile_id = p_profile_id
                  AND (id = item_id OR (item_id IS NULL AND lower(ingredient_name) = lower(item_name)));
                IF NOT FOUND THEN
                    INSERT INTO public.pantry_stock(profile_id, ingredient_name, amount, unit, updated_at)
                    VALUES (p_profile_id, item_name, item_amount, item_unit, now());
                END IF;
            ELSIF operation IN ('set', 'adjust') THEN
                item_amount := (item->>'amount')::numeric;
                IF operation = 'set' AND item_amount < 0 THEN
                    RAISE EXCEPTION 'set amount cannot be negative' USING ERRCODE = '22023';
                END IF;
                UPDATE public.pantry_stock SET
                    ingredient_name = CASE WHEN operation = 'set' THEN COALESCE(item_name, ingredient_name) ELSE ingredient_name END,
                    amount = CASE WHEN operation = 'adjust' THEN GREATEST(0, amount + item_amount) ELSE item_amount END,
                    unit = CASE WHEN operation = 'set' THEN COALESCE(NULLIF(btrim(item->>'unit'), ''), unit) ELSE unit END,
                    updated_at = now()
                WHERE profile_id = p_profile_id
                  AND (id = item_id OR (item_id IS NULL AND lower(ingredient_name) = lower(item_name)));
                IF NOT FOUND AND operation = 'set' AND item_id IS NULL AND item_name IS NOT NULL AND item_amount > 0 THEN
                    INSERT INTO public.pantry_stock(profile_id, ingredient_name, amount, unit, updated_at)
                    VALUES (p_profile_id, item_name, item_amount, item_unit, now());
                ELSIF NOT FOUND THEN
                    RAISE EXCEPTION 'pantry operation referenced an unknown row' USING ERRCODE = '22023';
                END IF;
                DELETE FROM public.pantry_stock WHERE profile_id = p_profile_id AND amount <= 0;
            ELSIF operation IN ('remove', 'delete') THEN
                DELETE FROM public.pantry_stock WHERE profile_id = p_profile_id
                  AND (id = item_id OR (item_id IS NULL AND lower(ingredient_name) = lower(item_name)));
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'pantry remove referenced an unknown row' USING ERRCODE = '22023';
                END IF;
            ELSE
                RAISE EXCEPTION 'unsupported pantry action %', operation USING ERRCODE = '22023';
            END IF;
        END LOOP;
    END IF;

    UPDATE public.profiles SET pantry_revision = pantry_revision + 1,
        pantry_reviewed_at = CASE WHEN p_mode = 'replace' THEN now() ELSE pantry_reviewed_at END
    WHERE id = p_profile_id;
    SELECT COALESCE(jsonb_agg(to_jsonb(p) ORDER BY p.ingredient_name), '[]'::jsonb)
    INTO saved_pantry FROM public.pantry_stock p WHERE p.profile_id = p_profile_id;
    RETURN jsonb_build_object(
        'revision', current_revision + 1,
        'reviewed_at', CASE WHEN p_mode = 'replace' THEN now() ELSE current_reviewed_at END,
        'pantry', saved_pantry
    );
END; $$;

REVOKE ALL ON FUNCTION public.apply_pantry_inventory_change(UUID, BIGINT, TEXT, JSONB)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.apply_pantry_inventory_change(UUID, BIGINT, TEXT, JSONB)
    TO service_role;

-- Cart quantities change only when the UI or agent explicitly requests this operation.
CREATE OR REPLACE FUNCTION public.apply_pantry_cart_reconciliation(
    p_profile_id UUID, p_expected_revision BIGINT, p_cart_reconciliation JSONB
)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE
    current_revision BIGINT; item JSONB; saved_cart JSONB; intent_changed BOOLEAN := false;
    existing_purchase_amount NUMERIC; existing_purchase_unit TEXT;
    next_purchase_amount NUMERIC; next_purchase_unit TEXT; next_allocation JSONB;
BEGIN
    IF jsonb_typeof(COALESCE(p_cart_reconciliation, '[]'::jsonb)) <> 'array' THEN
        RAISE EXCEPTION 'cart reconciliation must be an array' USING ERRCODE = '22023';
    END IF;
    SELECT pantry_revision INTO current_revision FROM public.profiles
    WHERE id = p_profile_id FOR SHARE;
    IF current_revision IS NULL THEN
        RAISE EXCEPTION 'household profile is missing' USING ERRCODE = '22023';
    END IF;
    IF current_revision <> p_expected_revision THEN
        RAISE EXCEPTION 'pantry revision conflict' USING ERRCODE = '40001';
    END IF;
    PERFORM 1 FROM public.grocery_cart_items WHERE profile_id = p_profile_id FOR UPDATE;
    IF (SELECT count(*) FROM public.grocery_cart_items WHERE profile_id = p_profile_id)
       <> jsonb_array_length(COALESCE(p_cart_reconciliation, '[]'::jsonb)) THEN
        RAISE EXCEPTION 'native cart changed during pantry reconciliation' USING ERRCODE = '40001';
    END IF;
    FOR item IN SELECT * FROM jsonb_array_elements(COALESCE(p_cart_reconciliation, '[]'::jsonb)) LOOP
        SELECT purchase_amount, purchase_unit
        INTO existing_purchase_amount, existing_purchase_unit
        FROM public.grocery_cart_items
        WHERE profile_id = p_profile_id AND id = (item->>'id')::bigint
          AND lower(ingredient_name) = lower(item->>'required_name')
          AND amount = (item->>'required_amount')::numeric
          AND lower(unit) = lower(item->>'required_unit');
        IF NOT FOUND THEN
            RAISE EXCEPTION 'cart reconciliation referenced an unknown row' USING ERRCODE = '22023';
        END IF;
        next_purchase_amount := (item->>'purchase_amount')::numeric;
        next_purchase_unit := COALESCE(NULLIF(item->>'purchase_unit', ''), item->>'required_unit');
        next_allocation := COALESCE(item->'pantry_allocation', '{}'::jsonb);
        intent_changed := intent_changed OR existing_purchase_amount IS DISTINCT FROM next_purchase_amount
          OR existing_purchase_unit IS DISTINCT FROM next_purchase_unit;
        UPDATE public.grocery_cart_items SET
            purchase_amount = next_purchase_amount, purchase_unit = next_purchase_unit,
            pantry_allocation = next_allocation, updated_at = now()
        WHERE profile_id = p_profile_id AND id = (item->>'id')::bigint;
    END LOOP;
    IF intent_changed THEN
        DELETE FROM public.provider_checkout_drafts WHERE profile_id = p_profile_id;
    END IF;
    SELECT COALESCE(jsonb_agg(to_jsonb(c) ORDER BY c.category, c.ingredient_name), '[]'::jsonb)
    INTO saved_cart FROM public.grocery_cart_items c WHERE c.profile_id = p_profile_id;
    RETURN jsonb_build_object(
        'pantry_revision', current_revision,
        'provider_review_invalidated', intent_changed,
        'grocery_cart', saved_cart
    );
END; $$;

REVOKE ALL ON FUNCTION public.apply_pantry_cart_reconciliation(UUID, BIGINT, JSONB)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.apply_pantry_cart_reconciliation(UUID, BIGINT, JSONB)
    TO service_role;

CREATE OR REPLACE FUNCTION public.remove_future_meal_plan_entries(
    p_profile_id uuid, p_operations jsonb
)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE op jsonb; kind text; start_date date; end_date date; slot text;
    household_today date; affected jsonb := '[]'::jsonb;
BEGIN
    SELECT (now() AT TIME ZONE timezone_name)::date INTO household_today
    FROM public.profiles WHERE id = p_profile_id;
    IF jsonb_typeof(p_operations) <> 'array' OR jsonb_array_length(p_operations) = 0 THEN
        RAISE EXCEPTION 'operations must be a non-empty array' USING ERRCODE = '22023';
    END IF;
    FOR op IN SELECT * FROM jsonb_array_elements(p_operations) LOOP
        kind := lower(btrim(op->>'action'));
        start_date := (op->>'start_date')::date;
        end_date := COALESCE(NULLIF(op->>'end_date', '')::date, start_date);
        IF start_date < household_today OR end_date < start_date THEN
            RAISE EXCEPTION 'only valid non-past dates may be removed' USING ERRCODE = '22023';
        END IF;
        affected := affected || to_jsonb(ARRAY(SELECT generate_series(start_date, end_date, interval '1 day')::date));
        IF kind = 'slot' THEN
            IF start_date <> end_date THEN RAISE EXCEPTION 'slot removal targets one date' USING ERRCODE = '22023'; END IF;
            slot := lower(btrim(op->>'meal_slot'));
            IF slot NOT IN ('breakfast', 'lunch', 'dinner') THEN RAISE EXCEPTION 'invalid meal slot' USING ERRCODE = '22023'; END IF;
            UPDATE public.meal_plans SET
                breakfast_name = CASE WHEN slot = 'breakfast' THEN NULL ELSE breakfast_name END,
                lunch_name = CASE WHEN slot = 'lunch' THEN NULL ELSE lunch_name END,
                dinner_name = CASE WHEN slot = 'dinner' THEN NULL ELSE dinner_name END,
                updated_at = now()
            WHERE profile_id = p_profile_id AND plan_date = start_date;
            DELETE FROM public.meal_plans WHERE profile_id = p_profile_id AND plan_date = start_date
              AND breakfast_name IS NULL AND lunch_name IS NULL AND dinner_name IS NULL;
        ELSIF kind IN ('date', 'range') THEN
            DELETE FROM public.meal_plans WHERE profile_id = p_profile_id AND plan_date BETWEEN start_date AND end_date;
        ELSE RAISE EXCEPTION 'unsupported meal removal action' USING ERRCODE = '22023'; END IF;
    END LOOP;
    RETURN jsonb_build_object('affected_dates', (SELECT jsonb_agg(DISTINCT value) FROM jsonb_array_elements(affected)));
END; $$;

REVOKE ALL ON FUNCTION public.remove_future_meal_plan_entries(uuid, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.remove_future_meal_plan_entries(uuid, jsonb) TO service_role;

CREATE OR REPLACE FUNCTION public.delete_recipe_grocery_plan(
    p_profile_id uuid, p_plan_id uuid
)
RETURNS boolean LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE deleted_count integer;
BEGIN
    DELETE FROM public.grocery_cart_items
    WHERE profile_id = p_profile_id AND recipe_grocery_plan_id = p_plan_id;
    DELETE FROM public.recipe_grocery_plans
    WHERE profile_id = p_profile_id AND id = p_plan_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    IF deleted_count > 0 THEN
        DELETE FROM public.provider_checkout_drafts WHERE profile_id = p_profile_id;
    END IF;
    RETURN deleted_count = 1;
END; $$;
REVOKE ALL ON FUNCTION public.delete_recipe_grocery_plan(uuid, uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.delete_recipe_grocery_plan(uuid, uuid) TO service_role;
