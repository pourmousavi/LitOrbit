-- Strip the duplicated `embedding` field from each anchor entry inside
-- user_profiles.positive_anchors / negative_anchors.
--
-- Each entry was a dict like:
--   {paper_id, embedding, source, weight, added_at, tags}
-- The 3072-dim embedding (~37 kB) is a duplicate of what's already in
-- papers.embedding / reference_papers.embedding, and was the dominant
-- contributor to Supabase egress (every profile fetch dragged ~3.7 MB
-- of jsonb anchor blobs over the wire).
--
-- After this migration, entries are slimmed to:
--   {paper_id, source, weight, added_at, tags}
-- and the scorer joins back to papers / reference_papers by paper_id
-- at scoring time.
--
-- Idempotent: if entries no longer contain `embedding`, the EXISTS guard
-- is false and the row is left alone. Re-running is a no-op.

UPDATE user_profiles
SET positive_anchors = COALESCE(
  (
    SELECT jsonb_agg(entry - 'embedding')
    FROM jsonb_array_elements(positive_anchors) entry
  ),
  '[]'::jsonb
)
WHERE positive_anchors IS NOT NULL
  AND jsonb_typeof(positive_anchors) = 'array'
  AND jsonb_array_length(positive_anchors) > 0
  AND EXISTS (
    SELECT 1 FROM jsonb_array_elements(positive_anchors) e
    WHERE e ? 'embedding'
  );

UPDATE user_profiles
SET negative_anchors = COALESCE(
  (
    SELECT jsonb_agg(entry - 'embedding')
    FROM jsonb_array_elements(negative_anchors) entry
  ),
  '[]'::jsonb
)
WHERE negative_anchors IS NOT NULL
  AND jsonb_typeof(negative_anchors) = 'array'
  AND jsonb_array_length(negative_anchors) > 0
  AND EXISTS (
    SELECT 1 FROM jsonb_array_elements(negative_anchors) e
    WHERE e ? 'embedding'
  );
