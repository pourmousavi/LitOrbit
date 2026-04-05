-- System settings table (single-row config for admin-controlled limits)
CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    max_podcasts_per_user_per_month INTEGER NOT NULL DEFAULT 20,
    digest_podcast_enabled_global BOOLEAN NOT NULL DEFAULT TRUE,
    max_papers_per_digest INTEGER NOT NULL DEFAULT 5,
    updated_at TIMESTAMPTZ DEFAULT now()
);
INSERT INTO system_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

-- User activity tracking columns
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0;

-- Podcast listen tracking columns
ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS listen_count INTEGER DEFAULT 0;
ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS last_listened_at TIMESTAMPTZ;
