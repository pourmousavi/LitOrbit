-- Add timezone column for day-of-week digest scheduling
ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS digest_timezone VARCHAR NOT NULL DEFAULT 'Australia/Adelaide';
