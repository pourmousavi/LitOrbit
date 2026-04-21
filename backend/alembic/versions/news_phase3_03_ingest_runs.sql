-- News ingest runs tracking (mirrors pipeline_runs for papers)
CREATE TABLE IF NOT EXISTS news_ingest_runs (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at         timestamptz NOT NULL DEFAULT now(),
    completed_at       timestamptz,
    status             text NOT NULL DEFAULT 'running',
    items_new          integer NOT NULL DEFAULT 0,
    items_skipped      integer NOT NULL DEFAULT 0,
    items_embedded     integer NOT NULL DEFAULT 0,
    items_scored       integer NOT NULL DEFAULT 0,
    items_errors       integer NOT NULL DEFAULT 0,
    sources_total      integer NOT NULL DEFAULT 0,
    sources_succeeded  integer NOT NULL DEFAULT 0,
    sources_failed     integer NOT NULL DEFAULT 0,
    error_message      text,
    run_log            jsonb NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS news_ingest_runs_started_idx ON news_ingest_runs (started_at DESC);

-- Add ingest_run_id FK to news_items
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS ingest_run_id uuid REFERENCES news_ingest_runs(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS news_items_ingest_run_idx ON news_items (ingest_run_id) WHERE ingest_run_id IS NOT NULL;
