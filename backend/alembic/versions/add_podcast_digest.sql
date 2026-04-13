-- Standalone podcast digest: independent scheduling from email digest
ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS podcast_digest_enabled BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS podcast_digest_frequency VARCHAR DEFAULT 'weekly',
    ADD COLUMN IF NOT EXISTS podcast_digest_day VARCHAR DEFAULT 'monday',
    ADD COLUMN IF NOT EXISTS podcast_digest_top_papers INTEGER,
    ADD COLUMN IF NOT EXISTS podcast_digest_voice_mode VARCHAR DEFAULT 'dual';

-- Track which product created a digest_log entry (email vs standalone podcast)
ALTER TABLE digest_logs
    ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'email';

-- Track which product a digest_run belongs to
ALTER TABLE digest_runs
    ADD COLUMN IF NOT EXISTS run_type VARCHAR DEFAULT 'email';
