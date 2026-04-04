-- Migration: Add digest_runs table for tracking digest run progress
-- Similar to pipeline_runs, tracks status, timing, and step-by-step logs

CREATE TABLE IF NOT EXISTS digest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    frequency VARCHAR NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR NOT NULL,
    users_total INTEGER DEFAULT 0,
    users_sent INTEGER DEFAULT 0,
    users_skipped INTEGER DEFAULT 0,
    users_failed INTEGER DEFAULT 0,
    error_message TEXT,
    run_log JSONB DEFAULT '[]'::jsonb
);

-- Also add digest_day column if not yet present
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS digest_day VARCHAR DEFAULT 'monday';
