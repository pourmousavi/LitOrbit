-- Phase 3.1: link scoring signals to the pipeline run that produced them,
-- so the admin UI can list which papers were rejected per run/per user.
ALTER TABLE scoring_signals
    ADD COLUMN IF NOT EXISTS pipeline_run_id uuid
    REFERENCES pipeline_runs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_scoring_signal_run_user
    ON scoring_signals(pipeline_run_id, user_id);
