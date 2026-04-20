-- News Extension Phase 1: content_cross_links table
-- Computed paper <-> news semantic similarity links.

CREATE TABLE IF NOT EXISTS content_cross_links (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_content_type   text NOT NULL CHECK (source_content_type IN ('paper','news')),
    source_content_id     uuid NOT NULL,
    target_content_type   text NOT NULL CHECK (target_content_type IN ('paper','news')),
    target_content_id     uuid NOT NULL,
    similarity            numeric NOT NULL,
    computed_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT no_self_link CHECK (
        NOT (source_content_type = target_content_type AND source_content_id = target_content_id)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS content_cross_links_unique_idx
    ON content_cross_links (source_content_type, source_content_id, target_content_type, target_content_id);
CREATE INDEX IF NOT EXISTS content_cross_links_lookup_idx
    ON content_cross_links (source_content_type, source_content_id, similarity DESC);
