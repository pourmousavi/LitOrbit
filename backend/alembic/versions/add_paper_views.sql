-- Track which papers each user has opened in the feed
CREATE TABLE IF NOT EXISTS paper_views (
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    viewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, paper_id)
);
CREATE INDEX IF NOT EXISTS idx_paper_views_user ON paper_views(user_id);
