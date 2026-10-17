-- Security hardening from the 2026-10-17 audit (defence in depth; the
-- backend already enforces both rules before calling these functions).
--
-- 1. save_recipe_grocery_plan_with_cart: an existing plan id is updated only
--    by its own household, never by another one (finding #8).
-- 2. remove_future_meal_plan_entries: bounded scopes, so a tiny request cannot
--    expand thousands of years of dates (findings #7, #14, #22).
--
-- Function signatures are unchanged, so the deployed backend keeps working.

BEGIN;

CREATE OR REPLACE FUNCTION public.save_recipe_grocery_plan_with_cart(
    p_plan_id uuid, p_profile_id uuid, p_scope jsonb, p_request_text text,
    p_recipe_cards jsonb, p_ingredients jsonb, p_pantry_considerations jsonb,
    p_household_size integer, p_notes text, p_source text, p_updates_cart boolean,
    p_cart_items jsonb DEFAULT '[]'::jsonb, p_created_at timestamptz DEFAULT now(),
    p_updated_at timestamptz DEFAULT now()
)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
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
    ) VALUES (
        p_plan_id, p_profile_id, COALESCE(p_scope, '{}'::jsonb),
        COALESCE(p_request_text, ''), COALESCE(p_recipe_cards, '[]'::jsonb),
        COALESCE(p_ingredients, '[]'::jsonb),
        COALESCE(p_pantry_considerations, '[]'::jsonb), p_household_size,
        COALESCE(p_notes, ''), p_source, p_updates_cart,
        CASE WHEN p_updates_cart THEN jsonb_array_length(COALESCE(p_cart_items, '[]'::jsonb)) ELSE 0 END,
        p_created_at, p_updated_at
    )
    ON CONFLICT (id) DO UPDATE SET
        scope = EXCLUDED.scope, request_text = EXCLUDED.request_text,
        recipe_cards = EXCLUDED.recipe_cards, ingredients = EXCLUDED.ingredients,
        pantry_considerations = EXCLUDED.pantry_considerations,
        household_size = EXCLUDED.household_size, notes = EXCLUDED.notes,
        source = EXCLUDED.source, updates_cart = EXCLUDED.updates_cart,
        cart_item_count = EXCLUDED.cart_item_count, updated_at = EXCLUDED.updated_at
    -- Only the owning household may update an existing plan id.
    WHERE public.recipe_grocery_plans.profile_id = EXCLUDED.profile_id
    RETURNING * INTO saved_plan;
    IF saved_plan.id IS NULL THEN
        RAISE EXCEPTION 'recipe plan belongs to another household' USING ERRCODE = '42501';
    END IF;
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
        INTO saved_cart FROM public.grocery_cart_items AS cart_row
        WHERE cart_row.profile_id = p_profile_id;
    END IF;
    RETURN jsonb_build_object(
        'plan', to_jsonb(saved_plan), 'cart', COALESCE(saved_cart, '[]'::jsonb)
    );
END; $$;

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
    IF jsonb_array_length(p_operations) > 31 THEN
        RAISE EXCEPTION 'remove at most 31 meal-plan scopes at a time' USING ERRCODE = '22023';
    END IF;
    FOR op IN SELECT * FROM jsonb_array_elements(p_operations) LOOP
        kind := lower(btrim(op->>'action'));
        start_date := (op->>'start_date')::date;
        end_date := COALESCE(NULLIF(op->>'end_date', '')::date, start_date);
        IF start_date < household_today OR end_date < start_date THEN
            RAISE EXCEPTION 'only valid non-past dates may be removed' USING ERRCODE = '22023';
        END IF;
        IF end_date - start_date >= 366 THEN
            RAISE EXCEPTION 'date ranges are limited to 366 days' USING ERRCODE = '22023';
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

COMMIT;
