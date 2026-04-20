-- Phase 2.1: track which embedding space each vector is in
ALTER TABLE papers ADD COLUMN embedding_task_type text;
ALTER TABLE reference_papers ADD COLUMN embedding_task_type text;

-- Index to speed up "find unconverted papers" queries during the sweep
CREATE INDEX IF NOT EXISTS ix_papers_embedding_task_type ON papers(embedding_task_type)
    WHERE embedding IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_reference_papers_embedding_task_type ON reference_papers(embedding_task_type)
    WHERE embedding IS NOT NULL;
