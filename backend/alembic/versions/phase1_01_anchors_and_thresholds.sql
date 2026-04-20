-- Phase 1 Chunk 1: anchor sets for k-NN semantic gate + admin-tunable thresholds

-- Add positive and negative anchor sets to user_profiles
ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS positive_anchors JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS negative_anchors JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Add tunable similarity threshold and negative anchor lambda to system_settings
ALTER TABLE system_settings
  ADD COLUMN IF NOT EXISTS similarity_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.50;

ALTER TABLE system_settings
  ADD COLUMN IF NOT EXISTS negative_anchor_lambda DOUBLE PRECISION NOT NULL DEFAULT 0.5;

-- Backfill positive_anchors from existing reference_papers (embedding IS NOT NULL).
-- Each reference paper becomes a positive anchor with source="reference", weight=1.0.
UPDATE user_profiles up
SET positive_anchors = COALESCE(
  (
    SELECT jsonb_agg(
      jsonb_build_object(
        'paper_id', rp.id::text,
        'embedding', rp.embedding,
        'source', 'reference',
        'weight', 1.0,
        'added_at', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
        'tags', '[]'::jsonb
      )
    )
    FROM reference_papers rp
    WHERE rp.user_id = up.id
      AND rp.embedding IS NOT NULL
  ),
  '[]'::jsonb
);
