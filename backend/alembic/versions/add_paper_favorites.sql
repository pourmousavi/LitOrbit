-- Per-user "save for later" / favorite shortcut for papers
CREATE TABLE IF NOT EXISTS paper_favorites (
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    favorited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, paper_id)
);
CREATE INDEX IF NOT EXISTS idx_paper_favorites_user ON paper_favorites(user_id);
