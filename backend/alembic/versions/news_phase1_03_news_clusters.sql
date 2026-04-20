-- News Extension Phase 1: news_clusters table + FK from news_items
-- Groups near-duplicate news articles covering the same story.

CREATE TABLE IF NOT EXISTS news_clusters (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    primary_item_id      uuid REFERENCES news_items(id) ON DELETE SET NULL,
    centroid_embedding   jsonb,
    member_count         int NOT NULL DEFAULT 1,
    first_seen_at        timestamptz NOT NULL DEFAULT now(),
    last_updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Add FK from news_items.primary_cluster_id -> news_clusters.id
-- (Column already exists from previous migration, just needs the constraint)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'news_items_cluster_fk'
    ) THEN
        ALTER TABLE news_items
            ADD CONSTRAINT news_items_cluster_fk
            FOREIGN KEY (primary_cluster_id) REFERENCES news_clusters(id) ON DELETE SET NULL;
    END IF;
END $$;
