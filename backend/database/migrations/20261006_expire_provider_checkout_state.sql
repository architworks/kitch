-- Bound retention of provider carts, payment state, and order outcomes.
-- The application refreshes this deadline only while a review is actively used;
-- pg_cron removes abandoned records even if that household never returns.

ALTER TABLE public.provider_checkout_drafts
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- Remove legacy payment hand-off links immediately. They are returned only in
-- the live checkout response and are not needed for recovery.
UPDATE public.provider_checkout_drafts
SET payment_state = COALESCE(payment_state, '{}'::jsonb)
    - 'upi_intent_url'
    - 'bridge_url';

UPDATE public.provider_checkout_drafts
SET expires_at = LEAST(
    COALESCE(updated_at, now()) + interval '24 hours',
    now() + interval '24 hours'
)
WHERE expires_at IS NULL;

ALTER TABLE public.provider_checkout_drafts
    ALTER COLUMN expires_at SET DEFAULT (now() + interval '24 hours'),
    ALTER COLUMN expires_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_provider_checkout_drafts_expiry
    ON public.provider_checkout_drafts(expires_at);

CREATE EXTENSION IF NOT EXISTS pg_cron;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM cron.job
        WHERE jobname = 'kitch-expire-provider-checkout-state'
    ) THEN
        PERFORM cron.schedule(
            'kitch-expire-provider-checkout-state',
            '17 * * * *',
            $command$
                DELETE FROM public.provider_checkout_drafts
                WHERE expires_at <= now();
            $command$
        );
    END IF;
END $$;
