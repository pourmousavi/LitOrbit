-- Phase 4.2: allow digest_logs.paper_id to be NULL so we can write a
-- "send marker" row when an email digest goes out with zero papers
-- (shared papers / news only). Without this, _already_ran_today() in
-- digest_runner.py has no row to find on the next run and the same
-- email gets re-sent if curl --retry hits /run-scheduled again.
ALTER TABLE digest_logs ALTER COLUMN paper_id DROP NOT NULL;
