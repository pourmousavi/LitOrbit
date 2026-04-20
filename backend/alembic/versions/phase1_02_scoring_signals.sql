-- Phase 1 Chunk 4: scoring signal logging for threshold tuning

CREATE TABLE IF NOT EXISTS scoring_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    max_positive_sim DOUBLE PRECISION NOT NULL,
    max_negative_sim DOUBLE PRECISION NOT NULL,
    effective_score DOUBLE PRECISION NOT NULL,
    threshold_used DOUBLE PRECISION NOT NULL,
    lambda_used DOUBLE PRECISION NOT NULL,
    prefilter_matched BOOLEAN NOT NULL,
    passed_gate BOOLEAN NOT NULL,
    llm_score DOUBLE PRECISION,
    llm_errored BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (paper_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_scoring_signal_user_created
    ON scoring_signals (user_id, created_at DESC);
