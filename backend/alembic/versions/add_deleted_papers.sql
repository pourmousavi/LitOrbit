CREATE TABLE IF NOT EXISTS deleted_papers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doi VARCHAR,
    title TEXT NOT NULL,
    deleted_at TIMESTAMPTZ DEFAULT now()
);
