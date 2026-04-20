-- Phase 2.4: record abstract quality check result on each paper
ALTER TABLE papers ADD COLUMN abstract_quality_flag text;
CREATE INDEX IF NOT EXISTS ix_papers_abstract_quality_flag ON papers(abstract_quality_flag)
    WHERE abstract_quality_flag IS NOT NULL AND abstract_quality_flag != 'ok';
