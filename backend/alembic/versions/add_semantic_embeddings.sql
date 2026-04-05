-- Add embedding column to papers for semantic search
ALTER TABLE papers ADD COLUMN IF NOT EXISTS embedding JSONB;

-- Reference papers table: users upload papers to define their research profile
CREATE TABLE IF NOT EXISTS reference_papers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    abstract TEXT,
    doi VARCHAR,
    source VARCHAR NOT NULL,  -- 'pdf_upload', 'doi_lookup', 'manual'
    embedding JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reference_papers_user_id ON reference_papers(user_id);
