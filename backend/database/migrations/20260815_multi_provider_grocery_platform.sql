-- Breaking, provider-neutral grocery commerce schema.
-- Existing external checkout drafts are intentionally discarded; the native
-- Kitch grocery cart is not modified.

BEGIN;

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS preferred_grocery_provider TEXT;

DROP FUNCTION IF EXISTS public.claim_provider_checkout_operation(uuid, text, uuid, integer);
DROP FUNCTION IF EXISTS public.release_provider_checkout_operation(uuid, text, uuid);
DROP TABLE IF EXISTS public.provider_checkout_drafts;

CREATE TABLE public.provider_checkout_drafts (
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

CREATE INDEX idx_provider_checkout_drafts_profile_provider
    ON public.provider_checkout_drafts(profile_id, provider, provider_environment);

CREATE TABLE IF NOT EXISTS public.provider_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (length(btrim(provider)) > 0),
    provider_environment TEXT NOT NULL
        CHECK (provider_environment IN ('local', 'staging', 'production')),
    access_token_ciphertext TEXT NOT NULL,
    token_type TEXT NOT NULL DEFAULT 'Bearer',
    scope TEXT NOT NULL DEFAULT '',
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status TEXT NOT NULL DEFAULT 'connected'
        CHECK (status IN ('connected', 'reconnect_required', 'revoked', 'failed')),
    last_error_code TEXT,
    connected_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (profile_id, provider, provider_environment)
);

CREATE TABLE IF NOT EXISTS public.provider_oauth_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    provider_environment TEXT NOT NULL
        CHECK (provider_environment IN ('local', 'staging', 'production')),
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
    provider_environment TEXT NOT NULL
        CHECK (provider_environment IN ('local', 'staging', 'production')),
    state_hash TEXT NOT NULL UNIQUE,
    code_verifier_ciphertext TEXT NOT NULL,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_provider_connections_profile_provider
    ON public.provider_connections(profile_id, provider, provider_environment);
CREATE INDEX IF NOT EXISTS idx_provider_oauth_flows_expiry
    ON public.provider_oauth_flows(expires_at);

DO $$
DECLARE
    table_name text;
    policy_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'provider_checkout_drafts',
        'provider_connections',
        'provider_oauth_clients',
        'provider_oauth_flows'
    ]
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
        FOR policy_name IN
            SELECT policyname FROM pg_policies
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

CREATE FUNCTION public.claim_provider_checkout_operation(
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
    INSERT INTO public.provider_checkout_drafts (
        profile_id, provider, provider_environment
    ) VALUES (
        p_profile_id, p_provider, p_provider_environment
    ) ON CONFLICT (profile_id, provider, provider_environment) DO NOTHING;

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

CREATE FUNCTION public.release_provider_checkout_operation(
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

NOTIFY pgrst, 'reload schema';

COMMIT;
