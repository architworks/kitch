-- Kitch: Supabase PostgreSQL Database DDL Schema

-- 1. Create User Profiles Table (Linked to Supabase Auth)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    diet_preference TEXT NOT NULL DEFAULT 'balanced' CHECK (diet_preference IN ('balanced', 'keto', 'vegan', 'high-protein')),
    household_size INTEGER NOT NULL DEFAULT 3 CHECK (household_size >= 1),
    daily_calorie_target INTEGER NOT NULL DEFAULT 2000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS (Row Level Security) on Profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile" 
    ON public.profiles FOR SELECT 
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" 
    ON public.profiles FOR UPDATE 
    USING (auth.uid() = id);


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

-- Enable RLS on Meal Plans
ALTER TABLE public.meal_plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own meal plan" 
    ON public.meal_plans FOR ALL 
    USING (auth.uid() = profile_id);


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

-- Enable RLS on Pantry Stock
ALTER TABLE public.pantry_stock ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own pantry stock" 
    ON public.pantry_stock FOR ALL 
    USING (auth.uid() = profile_id);


-- 4. Create Shared Native Grocery Cart Table
CREATE TABLE IF NOT EXISTS public.grocery_cart_items (
    id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
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

-- Enable RLS on Grocery Cart Items
ALTER TABLE public.grocery_cart_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own grocery cart"
    ON public.grocery_cart_items FOR ALL
    USING (auth.uid() = profile_id);


-- 5. Create Daily Macro Intake Journal Table
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

-- Enable RLS on Macro Diary
ALTER TABLE public.macro_diary ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own macro diary logs" 
    ON public.macro_diary FOR ALL 
    USING (auth.uid() = profile_id);


-- --- INDEXING FOR OPTIMAL QUERY PERFORMANCE ---
CREATE INDEX IF NOT EXISTS idx_meal_plans_profile_id ON public.meal_plans(profile_id);
CREATE INDEX IF NOT EXISTS idx_pantry_stock_profile_id ON public.pantry_stock(profile_id);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_id ON public.grocery_cart_items(profile_id);
CREATE INDEX IF NOT EXISTS idx_grocery_cart_items_profile_source ON public.grocery_cart_items(profile_id, source);
CREATE INDEX IF NOT EXISTS idx_macro_diary_profile_id_date ON public.macro_diary(profile_id, logged_at);
