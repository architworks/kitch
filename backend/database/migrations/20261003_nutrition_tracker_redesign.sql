-- Date-aware personal nutrition diary with meal grouping and editable portions.

ALTER TABLE public.macro_diary
    ADD COLUMN IF NOT EXISTS quantity NUMERIC(10,2) NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS unit TEXT NOT NULL DEFAULT 'serving',
    ADD COLUMN IF NOT EXISTS meal_type TEXT;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'macro_diary'
          AND column_name = 'logged_at'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'macro_diary'
          AND column_name = 'consumed_at'
    ) THEN
        ALTER TABLE public.macro_diary RENAME COLUMN logged_at TO consumed_at;
    END IF;
END $$;

UPDATE public.macro_diary AS diary
SET meal_type = CASE
    WHEN EXTRACT(HOUR FROM diary.consumed_at AT TIME ZONE COALESCE(profile.timezone_name, 'Asia/Kolkata'))
        BETWEEN 5 AND 10 THEN 'breakfast'
    WHEN EXTRACT(HOUR FROM diary.consumed_at AT TIME ZONE COALESCE(profile.timezone_name, 'Asia/Kolkata'))
        BETWEEN 11 AND 15 THEN 'lunch'
    WHEN EXTRACT(HOUR FROM diary.consumed_at AT TIME ZONE COALESCE(profile.timezone_name, 'Asia/Kolkata'))
        BETWEEN 16 AND 18 THEN 'snack'
    ELSE 'dinner'
END
FROM public.profiles AS profile
WHERE diary.profile_id = profile.id AND diary.meal_type IS NULL;

ALTER TABLE public.macro_diary
    ALTER COLUMN meal_type SET NOT NULL,
    ALTER COLUMN meal_type SET DEFAULT 'dinner';

ALTER TABLE public.macro_diary
    DROP CONSTRAINT IF EXISTS macro_diary_meal_type_check,
    DROP CONSTRAINT IF EXISTS macro_diary_quantity_check;

ALTER TABLE public.macro_diary
    ADD CONSTRAINT macro_diary_meal_type_check
        CHECK (meal_type IN ('breakfast', 'lunch', 'snack', 'dinner')),
    ADD CONSTRAINT macro_diary_quantity_check CHECK (quantity > 0);

DROP INDEX IF EXISTS public.idx_macro_diary_profile_id_date;
CREATE INDEX idx_macro_diary_profile_consumed_at
    ON public.macro_diary(profile_id, consumed_at DESC);
