-- Add news_item_id to podcasts table for news item podcasts
ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS news_item_id uuid REFERENCES news_items(id) ON DELETE CASCADE;
