-- News Extension: add LLM score and summary columns to news_items
-- llm_score is the 1-10 Gemini score (same scale as paper_scores.relevance_score)
-- summary is a JSON object with key_points, relevance, suggested_action

ALTER TABLE news_items ADD COLUMN IF NOT EXISTS llm_score numeric;
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS llm_score_reasoning text;
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS summary text;
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS summary_generated_at timestamptz;
