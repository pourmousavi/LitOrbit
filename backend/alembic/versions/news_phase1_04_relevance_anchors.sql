-- News Extension Phase 1: relevance_anchors table
-- Shared anchor set for scoring both papers and news.
-- Replaces per-user JSONB anchor arrays with a unified table.

CREATE TABLE IF NOT EXISTS relevance_anchors (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_content_type   text NOT NULL CHECK (source_content_type IN ('paper','news')),
    source_content_id     uuid NOT NULL,
    label                 text NOT NULL,
    notes                 text,
    embedding             jsonb NOT NULL,
    weight                numeric NOT NULL DEFAULT 1.0 CHECK (weight BETWEEN 0 AND 3),
    enabled               boolean NOT NULL DEFAULT true,
    created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS relevance_anchors_enabled_idx
    ON relevance_anchors (enabled) WHERE enabled;
