-- Allow shares without a paper (podcast-only shares).
ALTER TABLE shares ALTER COLUMN paper_id DROP NOT NULL;
