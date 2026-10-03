-- Keep household profiles factual. Semantic food/brand preferences live only
-- in the agent memory service; provider selection and nutrition targets belong
-- to their own operational domains.

BEGIN;

CREATE TABLE public.nutrition_targets (
    profile_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    daily_calorie_target INTEGER NOT NULL DEFAULT 2000 CHECK (daily_calorie_target > 0),
    protein_target_g INTEGER NOT NULL DEFAULT 150 CHECK (protein_target_g > 0),
    carbs_target_g INTEGER NOT NULL DEFAULT 200 CHECK (carbs_target_g > 0),
    fat_target_g INTEGER NOT NULL DEFAULT 67 CHECK (fat_target_g > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

INSERT INTO public.nutrition_targets (
    profile_id, daily_calorie_target, protein_target_g, carbs_target_g, fat_target_g
)
SELECT id, daily_calorie_target, 150, 200, 67
FROM public.profiles
ON CONFLICT (profile_id) DO NOTHING;

CREATE TABLE public.provider_selection_state (
    profile_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    selected_provider TEXT NOT NULL CHECK (length(btrim(selected_provider)) > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

INSERT INTO public.provider_selection_state (profile_id, selected_provider)
SELECT id, preferred_grocery_provider
FROM public.profiles
WHERE NULLIF(btrim(preferred_grocery_provider), '') IS NOT NULL
ON CONFLICT (profile_id) DO UPDATE SET
    selected_provider = EXCLUDED.selected_provider,
    updated_at = now();

-- Persist the configured prototype member names as factual profile data.
UPDATE public.profiles SET full_name = 'Archit'
WHERE id = '00000000-0000-0000-0000-000000000000';
UPDATE public.profiles SET full_name = 'Anubhav'
WHERE id = '11111111-1111-1111-1111-111111111111';
UPDATE public.profiles SET full_name = 'Naman'
WHERE id = '22222222-2222-2222-2222-222222222222';

ALTER TABLE public.profiles
    DROP COLUMN diet_preference,
    DROP COLUMN daily_calorie_target,
    DROP COLUMN preferred_grocery_provider;

ALTER TABLE public.nutrition_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.provider_selection_state ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.nutrition_targets
    FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.provider_selection_state
    FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.nutrition_targets TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.provider_selection_state TO service_role;

COMMIT;
