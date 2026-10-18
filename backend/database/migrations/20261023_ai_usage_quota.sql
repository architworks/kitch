-- Shared usage caps for AI-backed requests.
--
-- Every chat message, photo, pantry reconciliation and grocery-app cart build
-- runs paid model calls. The app's per-instance throttle does not hold across
-- serverless instances, so these caps live in the database and apply per
-- account, per household and per IP address (hashed, never stored raw), in
-- fixed 10-minute and daily windows.

BEGIN;

CREATE TABLE IF NOT EXISTS public.ai_usage_windows (
    bucket TEXT NOT NULL,
    window_seconds INTEGER NOT NULL CHECK (window_seconds > 0),
    window_start TIMESTAMPTZ NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket, window_seconds, window_start)
);

ALTER TABLE public.ai_usage_windows ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.ai_usage_windows FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.ai_usage_windows TO service_role;

-- Counts one request against every bucket, or none of them: if any window is
-- already full, the increments are undone and the caller gets the longest
-- wait. Upserts lock each counter row, so concurrent requests cannot both
-- slip past the last slot.
CREATE OR REPLACE FUNCTION public.consume_ai_quota(
    p_buckets TEXT[],
    p_limits INTEGER[],
    p_windows INTEGER[]
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_now TIMESTAMPTZ := clock_timestamp();
    v_start TIMESTAMPTZ;
    v_count INTEGER;
    v_retry INTEGER := 0;
    i INTEGER;
BEGIN
    IF cardinality(p_buckets) = 0
       OR cardinality(p_buckets) <> cardinality(p_limits)
       OR cardinality(p_buckets) <> cardinality(p_windows) THEN
        RAISE EXCEPTION 'quota_arguments_invalid' USING ERRCODE = '22023';
    END IF;
    BEGIN
        FOR i IN 1..cardinality(p_buckets) LOOP
            v_start := to_timestamp(floor(extract(epoch FROM v_now) / p_windows[i]) * p_windows[i]);
            INSERT INTO public.ai_usage_windows AS w (bucket, window_seconds, window_start, request_count)
            VALUES (p_buckets[i], p_windows[i], v_start, 1)
            ON CONFLICT (bucket, window_seconds, window_start)
            DO UPDATE SET request_count = w.request_count + 1
            RETURNING w.request_count INTO v_count;
            IF v_count > p_limits[i] THEN
                v_retry := GREATEST(v_retry, CEIL(extract(epoch FROM (v_start + make_interval(secs => p_windows[i]) - v_now)))::INTEGER, 1);
            END IF;
        END LOOP;
        IF v_retry > 0 THEN
            RAISE EXCEPTION 'quota_exceeded' USING ERRCODE = 'KQ001';
        END IF;
    EXCEPTION WHEN SQLSTATE 'KQ001' THEN
        -- The subtransaction is rolled back, so a refused request uses no quota.
        RETURN jsonb_build_object('allowed', false, 'retry_after', v_retry);
    END;
    RETURN jsonb_build_object('allowed', true);
END;
$$;

REVOKE ALL ON FUNCTION public.consume_ai_quota(TEXT[], INTEGER[], INTEGER[]) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.consume_ai_quota(TEXT[], INTEGER[], INTEGER[]) TO service_role;

-- Counters are only needed for the current windows; drop them after two days.
CREATE EXTENSION IF NOT EXISTS pg_cron;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'kitch-expire-ai-usage-windows') THEN
        PERFORM cron.schedule(
            'kitch-expire-ai-usage-windows',
            '23 3 * * *',
            $command$
                DELETE FROM public.ai_usage_windows
                WHERE window_start < now() - interval '2 days';
            $command$
        );
    END IF;
END $$;

NOTIFY pgrst, 'reload schema';

COMMIT;
