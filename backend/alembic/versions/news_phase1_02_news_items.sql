-- News Extension Phase 1: news_items table
-- Stores individual news articles ingested from RSS feeds.

CREATE TABLE IF NOT EXISTS news_items (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id              uuid NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
    url                    text NOT NULL UNIQUE,
    canonical_url          text,
    guid                   text,
    title                  text NOT NULL,
    excerpt                text,
    full_text              text,
    full_text_scraped_at   timestamptz,
    author                 text,
    published_at           timestamptz NOT NULL,
    tags                   text[] DEFAULT '{}',
    categories             text[] DEFAULT '{}',
    embedding              jsonb,
    relevance_score        numeric,
    primary_cluster_id     uuid,
    is_cluster_primary     boolean NOT NULL DEFAULT true,
    retention_until        timestamptz,
    scholarlib_ref_id      text,
    created_at             timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS news_items_guid_source_idx
    ON news_items (source_id, guid) WHERE guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS news_items_published_idx     ON news_items (published_at DESC);
CREATE INDEX IF NOT EXISTS news_items_relevance_idx     ON news_items (relevance_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS news_items_source_pub_idx    ON news_items (source_id, published_at DESC);
CREATE INDEX IF NOT EXISTS news_items_primary_idx       ON news_items (is_cluster_primary) WHERE is_cluster_primary;
