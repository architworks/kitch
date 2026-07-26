-- Adds the durable recipe artifact and native grocery cart tables expected by
-- backend/app/supabase_client.py.
--
-- This migration is safe to rerun after it has completed successfully.

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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

ALTER TABLE public.recipe_grocery_plans ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'recipe_grocery_plans'
          AND policyname = 'Users can manage own recipe grocery plans'
    ) THEN
        CREATE POLICY "Users can manage own recipe grocery plans"
            ON public.recipe_grocery_plans
            FOR ALL
            USING (auth.uid() = profile_id)
            WITH CHECK (auth.uid() = profile_id);
    END IF;
END
$$;

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

ALTER TABLE public.grocery_cart_items ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'grocery_cart_items'
          AND policyname = 'Users can manage own grocery cart'
    ) THEN
        CREATE POLICY "Users can manage own grocery cart"
            ON public.grocery_cart_items
            FOR ALL
            USING (auth.uid() = profile_id)
            WITH CHECK (auth.uid() = profile_id);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_recipe_grocery_plans_profile_created_at
    ON public.recipe_grocery_plans(profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_id
    ON public.grocery_cart_items(profile_id);

CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_source
    ON public.grocery_cart_items(profile_id, source);

CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_recipe_plan
    ON public.grocery_cart_items(profile_id, recipe_grocery_plan_id);

NOTIFY pgrst, 'reload schema';

COMMIT;
