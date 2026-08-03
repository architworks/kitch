-- Durable, backend-only provider checkout state and serialized provider operations.

BEGIN;

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

CREATE INDEX IF NOT EXISTS idx_provider_checkout_drafts_profile_provider
    ON public.provider_checkout_drafts(profile_id, provider);

ALTER TABLE public.provider_checkout_drafts ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    policy_name text;
BEGIN
    FOR policy_name IN
        SELECT policyname
        FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'provider_checkout_drafts'
    LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON public.provider_checkout_drafts',
            policy_name
        );
    END LOOP;
END
$$;

REVOKE ALL PRIVILEGES ON TABLE public.provider_checkout_drafts
    FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.provider_checkout_drafts
    TO service_role;

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

NOTIFY pgrst, 'reload schema';

COMMIT;
