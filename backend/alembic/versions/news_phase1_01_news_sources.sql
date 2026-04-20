-- News Extension Phase 1: news_sources table
-- Stores RSS feed source configurations for news ingestion.

CREATE TABLE IF NOT EXISTS news_sources (
    id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                      text NOT NULL UNIQUE,
    feed_url                  text NOT NULL,
    website_url               text NOT NULL,
    authority_weight          numeric NOT NULL DEFAULT 1.0
                              CHECK (authority_weight BETWEEN 0 AND 2),
    enabled                   boolean NOT NULL DEFAULT true,
    per_source_daily_cap      int NOT NULL DEFAULT 5,
    per_source_min_relevance  numeric NOT NULL DEFAULT 0.30,
    last_fetched_at           timestamptz,
    last_fetch_status         text,
    last_fetch_error          text,
    created_at                timestamptz NOT NULL DEFAULT now(),
    updated_at                timestamptz NOT NULL DEFAULT now()
);

-- Seed initial sources (NEM/BESS focused)
INSERT INTO news_sources (name, feed_url, website_url, authority_weight) VALUES
 ('RenewEconomy',            'https://reneweconomy.com.au/feed/',             'https://reneweconomy.com.au/',            1.20),
 ('Energy-Storage.News',     'https://www.energy-storage.news/feed/',         'https://www.energy-storage.news/',        1.15),
 ('PV Magazine Australia',   'https://www.pv-magazine-australia.com/feed/',   'https://www.pv-magazine-australia.com/',  1.10),
 ('Utility Magazine',        'https://utilitymagazine.com.au/feed/',          'https://utilitymagazine.com.au/',         1.00)
ON CONFLICT (name) DO NOTHING;
