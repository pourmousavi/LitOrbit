-- Add visibility (private/shared) to collections so users can have personal lists
-- Existing rows default to 'shared' to preserve current behavior.
ALTER TABLE collections
    ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'shared';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'collections_visibility_check'
    ) THEN
        ALTER TABLE collections
            ADD CONSTRAINT collections_visibility_check
            CHECK (visibility IN ('private', 'shared'));
    END IF;
END $$;
