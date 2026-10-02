-- Atomic standalone native-cart changes initiated by chat or another trusted backend flow.

BEGIN;

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
    target_id uuid;
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

            SELECT count(*), min(cart.id::text)::uuid
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
                    updated_at = now()
                WHERE profile_id = p_profile_id AND id = target_id;
            ELSE
                INSERT INTO public.grocery_cart_items (
                    profile_id,
                    ingredient_name,
                    amount,
                    unit,
                    category,
                    source,
                    checked,
                    already_stocked,
                    stock_note
                ) VALUES (
                    p_profile_id,
                    requested_name,
                    requested_amount,
                    requested_unit,
                    COALESCE(NULLIF(btrim(change->>'category'), ''), 'General'),
                    'manual',
                    COALESCE((change->>'checked')::boolean, false),
                    COALESCE(
                        (COALESCE(change->>'alreadyStocked', change->>'already_stocked'))::boolean,
                        false
                    ),
                    COALESCE(change->>'stockNote', change->>'stock_note', '')
                );
            END IF;

        ELSIF change_action IN ('set', 'update', 'remove', 'delete') THEN
            IF NULLIF(btrim(change->>'item_id'), '') IS NOT NULL
               OR NULLIF(btrim(change->>'id'), '') IS NOT NULL THEN
                BEGIN
                    target_id := COALESCE(
                        NULLIF(btrim(change->>'item_id'), '')::uuid,
                        NULLIF(btrim(change->>'id'), '')::uuid
                    );
                EXCEPTION WHEN invalid_text_representation THEN
                    RAISE EXCEPTION 'item_id must be a UUID' USING ERRCODE = '22023';
                END;
                SELECT count(*) INTO target_count
                FROM public.grocery_cart_items cart
                WHERE cart.profile_id = p_profile_id AND cart.id = target_id;
            ELSE
                IF requested_name IS NULL THEN
                    RAISE EXCEPTION 'item_id or exact item name is required for %', change_action
                        USING ERRCODE = '22023';
                END IF;
                SELECT count(*), min(cart.id::text)::uuid
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
                SET ingredient_name = CASE
                        WHEN change ? 'name' THEN btrim(change->>'name')
                        ELSE ingredient_name
                    END,
                    amount = CASE
                        WHEN change ? 'amount' THEN requested_amount
                        ELSE amount
                    END,
                    unit = CASE
                        WHEN change ? 'unit' THEN btrim(change->>'unit')
                        ELSE unit
                    END,
                    category = CASE
                        WHEN change ? 'category' THEN COALESCE(NULLIF(btrim(change->>'category'), ''), 'General')
                        ELSE category
                    END,
                    checked = CASE
                        WHEN change ? 'checked' THEN (change->>'checked')::boolean
                        ELSE checked
                    END,
                    already_stocked = CASE
                        WHEN change ? 'alreadyStocked' THEN (change->>'alreadyStocked')::boolean
                        WHEN change ? 'already_stocked' THEN (change->>'already_stocked')::boolean
                        ELSE already_stocked
                    END,
                    stock_note = CASE
                        WHEN change ? 'stockNote' THEN COALESCE(change->>'stockNote', '')
                        WHEN change ? 'stock_note' THEN COALESCE(change->>'stock_note', '')
                        ELSE stock_note
                    END,
                    updated_at = now()
                WHERE profile_id = p_profile_id AND id = target_id;
            END IF;
        ELSE
            RAISE EXCEPTION 'unsupported native-cart action %', change_action
                USING ERRCODE = '22023';
        END IF;
    END LOOP;

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

NOTIFY pgrst, 'reload schema';

COMMIT;
