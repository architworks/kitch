-- Kitch: Supabase PostgreSQL Database DDL Schema

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Create User Profiles Table
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    diet_preference TEXT NOT NULL DEFAULT 'balanced' CHECK (diet_preference IN ('balanced', 'keto', 'vegan', 'high-protein')),
    household_size INTEGER NOT NULL DEFAULT 3 CHECK (household_size >= 1),
    daily_calorie_target INTEGER NOT NULL DEFAULT 2000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Create Weekly Meal Plans Table
CREATE TABLE IF NOT EXISTS public.meal_plans (
    id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    day TEXT NOT NULL CHECK (day IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),
    breakfast_recipe_id TEXT,
    lunch_recipe_id TEXT,
    dinner_recipe_id TEXT,
    snack_recipe_id TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (profile_id, day)
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

-- --- INDEXING FOR OPTIMAL QUERY PERFORMANCE ---
CREATE INDEX IF NOT EXISTS idx_meal_plans_profile_id ON public.meal_plans(profile_id);
CREATE INDEX IF NOT EXISTS idx_pantry_stock_profile_id ON public.pantry_stock(profile_id);
CREATE INDEX IF NOT EXISTS idx_recipe_grocery_plans_profile_created_at ON public.recipe_grocery_plans(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_id ON public.grocery_cart_items(profile_id);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_source ON public.grocery_cart_items(profile_id, source);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_recipe_plan ON public.grocery_cart_items(profile_id, recipe_grocery_plan_id);
CREATE INDEX IF NOT EXISTS idx_macro_diary_profile_id_date ON public.macro_diary(profile_id, logged_at);

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
        'macro_diary'
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
