-- Remove per_source_min_relevance from news_sources.
-- All primary news items are now LLM-scored regardless of embedding relevance.
ALTER TABLE news_sources DROP COLUMN IF EXISTS per_source_min_relevance;
