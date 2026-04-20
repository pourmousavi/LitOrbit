-- Add max podcast duration setting (admin-level and per-user)
ALTER TABLE system_settings
  ADD COLUMN IF NOT EXISTS max_podcast_duration_minutes INTEGER NOT NULL DEFAULT 20;

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS podcast_digest_max_minutes INTEGER;
