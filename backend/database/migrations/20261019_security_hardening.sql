-- Security hardening from the 2026-10-17 audit (defence in depth; the
-- backend already enforces both rules before calling these functions).
--
-- 1. save_recipe_grocery_plan_with_cart: an existing plan id is updated only
--    by its own household, never by another one (finding #8).
-- 2. remove_future_meal_plan_entries: bounded scopes, so a tiny request cannot
--    expand thousands of years of dates (findings #7, #14, #22).
--
-- 3. Draft invalidation spares a review an order is using (finding #18).
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

-- 3. Cart, pantry and recipe changes invalidate provider reviews, but never a
--    review that an order is using right now: one whose operation lease is
--    held, or whose checkout has been submitted and is awaiting its outcome
--    (finding #18). Ordering re-reads the live cart before submitting anyway.
CREATE OR REPLACE FUNCTION public.invalidate_provider_checkout_drafts(p_profile_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
BEGIN
    DELETE FROM public.provider_checkout_drafts
    WHERE profile_id = p_profile_id
      AND NOT (operation_id IS NOT NULL AND lease_expires_at IS NOT NULL AND lease_expires_at > now())
      AND COALESCE(status, 'draft') NOT IN ('checkout_pending', 'payment_pending', 'unknown');
END; $$;
REVOKE ALL ON FUNCTION public.invalidate_provider_checkout_drafts(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.invalidate_provider_checkout_drafts(uuid) TO service_role;

CREATE OR REPLACE FUNCTION public.apply_native_grocery_cart_changes(
    p_profile_id uuid, p_changes jsonb
)
RETURNS SETOF public.grocery_cart_items LANGUAGE plpgsql SECURITY INVOKER
SET search_path = public, pg_temp AS $$
DECLARE change jsonb; action text; target_id bigint; item_name text;
    item_unit text; item_amount numeric; matches integer;
BEGIN
    IF jsonb_typeof(p_changes) <> 'array' OR jsonb_array_length(p_changes) = 0 THEN
        RAISE EXCEPTION 'changes must be a non-empty JSON array' USING ERRCODE = '22023';
    END IF;
    FOR change IN SELECT * FROM jsonb_array_elements(p_changes) LOOP
        action := lower(btrim(COALESCE(change->>'action', 'add')));
        item_name := NULLIF(btrim(COALESCE(change->>'name', change->>'item')), '');
        item_unit := COALESCE(NULLIF(btrim(change->>'unit'), ''), 'piece');
        target_id := NULLIF(COALESCE(change->>'item_id', change->>'id'), '')::bigint;
        IF action = 'add' THEN
            item_amount := COALESCE(NULLIF(change->>'amount', '')::numeric, NULLIF(change->>'quantity', '')::numeric, 1);
            IF item_name IS NULL OR item_amount <= 0 THEN RAISE EXCEPTION 'add requires name and positive amount' USING ERRCODE = '22023'; END IF;
            SELECT count(*), min(id) INTO matches, target_id FROM public.grocery_cart_items
            WHERE profile_id = p_profile_id AND lower(ingredient_name) = lower(item_name) AND lower(unit) = lower(item_unit);
            IF matches > 1 THEN RAISE EXCEPTION 'ambiguous native cart row' USING ERRCODE = '22023'; END IF;
            IF matches = 1 THEN
                UPDATE public.grocery_cart_items SET amount = amount + item_amount,
                    purchase_amount = purchase_amount + item_amount, updated_at = now()
                WHERE id = target_id AND profile_id = p_profile_id;
            ELSE
                INSERT INTO public.grocery_cart_items(profile_id, ingredient_name, amount, unit,
                    category, source, checked, purchase_amount, purchase_unit, pantry_allocation)
                VALUES(p_profile_id, item_name, item_amount, item_unit,
                    COALESCE(NULLIF(change->>'category', ''), 'General'), 'manual',
                    COALESCE((change->>'checked')::boolean, false), item_amount, item_unit, '{}'::jsonb);
            END IF;
        ELSIF action IN ('set', 'update', 'remove', 'delete') THEN
            IF target_id IS NULL THEN
                SELECT count(*), min(id) INTO matches, target_id FROM public.grocery_cart_items
                WHERE profile_id = p_profile_id AND lower(ingredient_name) = lower(item_name)
                  AND (NOT (change ? 'unit') OR lower(unit) = lower(item_unit));
                IF matches <> 1 THEN RAISE EXCEPTION 'native cart row not uniquely identified' USING ERRCODE = '22023'; END IF;
            END IF;
            IF action IN ('remove', 'delete') THEN
                DELETE FROM public.grocery_cart_items WHERE profile_id = p_profile_id AND id = target_id;
            ELSE
                item_amount := CASE WHEN change ? 'amount' THEN (change->>'amount')::numeric ELSE NULL END;
                UPDATE public.grocery_cart_items SET
                    ingredient_name = CASE WHEN change ? 'name' THEN btrim(change->>'name') ELSE ingredient_name END,
                    amount = COALESCE(item_amount, amount), unit = CASE WHEN change ? 'unit' THEN item_unit ELSE unit END,
                    category = CASE WHEN change ? 'category' THEN COALESCE(NULLIF(change->>'category', ''), 'General') ELSE category END,
                    checked = CASE WHEN change ? 'checked' THEN (change->>'checked')::boolean ELSE checked END,
                    purchase_amount = COALESCE((change->>'purchase_amount')::numeric, item_amount, purchase_amount),
                    purchase_unit = CASE WHEN change ? 'unit' THEN item_unit ELSE purchase_unit END,
                    pantry_allocation = CASE WHEN change ? 'amount' OR change ? 'unit' THEN '{}'::jsonb ELSE pantry_allocation END,
                    updated_at = now()
                WHERE profile_id = p_profile_id AND id = target_id;
            END IF;
        ELSE RAISE EXCEPTION 'unsupported native-cart action %', action USING ERRCODE = '22023';
        END IF;
    END LOOP;
    PERFORM public.invalidate_provider_checkout_drafts(p_profile_id);
    RETURN QUERY SELECT * FROM public.grocery_cart_items WHERE profile_id = p_profile_id ORDER BY category, ingredient_name;
END; $$;

CREATE OR REPLACE FUNCTION public.apply_pantry_cart_reconciliation(
    p_profile_id UUID,
    p_expected_revision BIGINT,
    p_cart_reconciliation JSONB
)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE
    current_revision BIGINT;
    item JSONB;
    saved_cart JSONB;
    intent_changed BOOLEAN := false;
    existing_purchase_amount NUMERIC;
    existing_purchase_unit TEXT;
    next_purchase_amount NUMERIC;
    next_purchase_unit TEXT;
    next_allocation JSONB;
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
            purchase_amount = next_purchase_amount,
            purchase_unit = next_purchase_unit,
            pantry_allocation = next_allocation,
            updated_at = now()
        WHERE profile_id = p_profile_id AND id = (item->>'id')::bigint;
    END LOOP;
    IF intent_changed THEN
        PERFORM public.invalidate_provider_checkout_drafts(p_profile_id);
    END IF;
    SELECT COALESCE(jsonb_agg(to_jsonb(c) ORDER BY c.category, c.ingredient_name), '[]'::jsonb)
    INTO saved_cart FROM public.grocery_cart_items c WHERE c.profile_id = p_profile_id;
    RETURN jsonb_build_object(
        'pantry_revision', current_revision,
        'provider_review_invalidated', intent_changed,
        'grocery_cart', saved_cart
    );
END;
$$;

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
        PERFORM public.invalidate_provider_checkout_drafts(p_profile_id);
    END IF;
    RETURN deleted_count = 1;
END; $$;

CREATE OR REPLACE FUNCTION public.replace_planned_grocery_cart(
    p_profile_id uuid, p_cart_items jsonb DEFAULT '[]'::jsonb,
    p_recipe_grocery_plan_id uuid DEFAULT NULL
)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE saved_cart jsonb;
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
    SELECT p_profile_id, p_recipe_grocery_plan_id, item.ingredient_name,
        COALESCE(item.amount, 1), COALESCE(NULLIF(item.unit, ''), 'piece'),
        COALESCE(NULLIF(item.category, ''), 'General'), 'agent',
        COALESCE(item.checked, false), COALESCE(item.purchase_amount, item.amount, 1),
        COALESCE(NULLIF(item.purchase_unit, ''), NULLIF(item.unit, ''), 'piece'),
        COALESCE(item.pantry_allocation, '{}'::jsonb)
    FROM jsonb_to_recordset(COALESCE(p_cart_items, '[]'::jsonb)) AS item(
        ingredient_name text, amount numeric, unit text, category text, checked boolean,
        purchase_amount numeric, purchase_unit text, pantry_allocation jsonb
    );
    SELECT COALESCE(jsonb_agg(to_jsonb(c) ORDER BY c.id), '[]'::jsonb)
    INTO saved_cart FROM public.grocery_cart_items c WHERE c.profile_id = p_profile_id;
    PERFORM public.invalidate_provider_checkout_drafts(p_profile_id);
    RETURN saved_cart;
END; $$;

NOTIFY pgrst, 'reload schema';

COMMIT;
