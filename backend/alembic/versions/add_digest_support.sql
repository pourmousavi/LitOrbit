-- Migration: Add digest support
-- - DigestLog table to track papers sent in digests (prevents duplicates)
-- - UserProfile: digest podcast preferences
-- - Podcast: support digest-type podcasts (multi-paper, no single paper_id)

-- 1. Create digest_logs table
CREATE TABLE IF NOT EXISTS digest_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    digest_type VARCHAR NOT NULL,  -- 'daily' | 'weekly'
    podcast_id UUID REFERENCES podcasts(id) ON DELETE SET NULL,
    sent_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_digest_logs_user_id ON digest_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_digest_logs_paper_id ON digest_logs(paper_id);

-- 2. Add digest podcast settings to user_profiles
ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS digest_podcast_enabled BOOLEAN DEFAULT true,
    ADD COLUMN IF NOT EXISTS digest_podcast_voice_mode VARCHAR DEFAULT 'dual',
    ADD COLUMN IF NOT EXISTS digest_top_papers INTEGER;

-- 3. Update podcasts table for digest support
-- Make paper_id nullable (digest podcasts span multiple papers)
ALTER TABLE podcasts ALTER COLUMN paper_id DROP NOT NULL;

-- Add podcast_type column
ALTER TABLE podcasts
    ADD COLUMN IF NOT EXISTS podcast_type VARCHAR DEFAULT 'paper' NOT NULL,
    ADD COLUMN IF NOT EXISTS title TEXT;
