-- Phase 2.3: track WHY a paper was rejected (k-NN gate vs negative keywords vs other)
ALTER TABLE scoring_signals ADD COLUMN rejected_by text;
-- values: NULL (passed), "knn_gate", "negative_title", "abstract_quality" (Chunk 3), "no_embedding"
