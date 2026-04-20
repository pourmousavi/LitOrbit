-- News Extension Phase 1: user_interactions table
-- Cross-cutting event tracking for both papers and news.

CREATE TABLE IF NOT EXISTS user_interactions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    content_type   text NOT NULL CHECK (content_type IN ('paper','news')),
    content_id     uuid NOT NULL,
    event_type     text NOT NULL CHECK (event_type IN (
                        'viewed','rated','starred','marked_read',
                        'sent_to_scholarlib','included_in_digest','listened'
                   )),
    event_value    jsonb,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_interactions_user_time_idx
    ON user_interactions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS user_interactions_content_idx
    ON user_interactions (content_type, content_id);
CREATE UNIQUE INDEX IF NOT EXISTS user_interactions_toggle_idx
    ON user_interactions (user_id, content_type, content_id, event_type)
    WHERE event_type IN ('starred','marked_read','sent_to_scholarlib','included_in_digest','listened');
