-- Split the dual-purpose interest_vector field into two:
--   * interest_vector  — embedding centroid (already in use by pipeline pre-filter)
--   * category_weights — human-readable {category_name: weight} from user ratings
--
-- Backfill any existing interest_vector that contains string keys (i.e. category
-- names rather than embedding indices) into category_weights so the chart keeps
-- working for users who only have rating-based data.

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS category_weights JSONB DEFAULT '{}'::jsonb;

-- Backfill: if interest_vector is a JSON OBJECT whose keys look like category
-- names (non-numeric), copy it into category_weights and clear interest_vector
-- so the pipeline isn't tricked into treating category dicts as an embedding.
-- Skip rows where interest_vector is a JSON array (embedding centroid) or any
-- non-object type — those are already in the correct shape.
UPDATE user_profiles
SET category_weights = interest_vector,
    interest_vector  = '{}'::jsonb
WHERE interest_vector IS NOT NULL
  AND jsonb_typeof(interest_vector) = 'object'
  AND interest_vector <> '{}'::jsonb
  AND NOT EXISTS (
    SELECT 1
    FROM jsonb_object_keys(interest_vector) AS k
    WHERE k ~ '^[0-9]+$'
  );
