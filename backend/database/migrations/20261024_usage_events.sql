-- App-level usage metrics for AI requests.
--
-- One row per AI request (chat, photo, pantry reconciliation, grocery-app cart
-- build): feature names, outcome, timing, model calls and token counts. No
-- message text, photos, food, or grocery-app data. Accounts and households
-- appear only as keyed hashes. Rows are kept for 90 days.

BEGIN;

CREATE TABLE IF NOT EXISTS public.usage_events (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_key TEXT NOT NULL,
    household_key TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('chat', 'photo', 'pantry_reconcile', 'grocery_cart_build')),
    features TEXT[] NOT NULL DEFAULT '{}',
    outcome TEXT NOT NULL CHECK (outcome IN ('ok', 'limit', 'quota', 'rejected', 'error')),
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    first_response_ms INTEGER CHECK (first_response_ms >= 0),
    model_calls INTEGER NOT NULL DEFAULT 0 CHECK (model_calls >= 0),
    input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0)
);
CREATE INDEX IF NOT EXISTS usage_events_occurred_at_idx ON public.usage_events (occurred_at);
CREATE INDEX IF NOT EXISTS usage_events_household_key_idx ON public.usage_events (household_key);

ALTER TABLE public.usage_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.usage_events FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, DELETE ON TABLE public.usage_events TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.usage_events_id_seq TO service_role;
REVOKE ALL ON SEQUENCE public.usage_events_id_seq FROM PUBLIC, anon, authenticated;

CREATE EXTENSION IF NOT EXISTS pg_cron;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'kitch-expire-usage-events') THEN
        PERFORM cron.schedule(
            'kitch-expire-usage-events',
            '41 3 * * *',
            $command$
                DELETE FROM public.usage_events
                WHERE occurred_at < now() - interval '90 days';
            $command$
        );
    END IF;
END $$;

NOTIFY pgrst, 'reload schema';

COMMIT;
