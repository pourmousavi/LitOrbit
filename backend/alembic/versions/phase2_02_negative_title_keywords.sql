-- Phase 2.2: admin-curated hard-reject keywords (title-only)
ALTER TABLE system_settings ADD COLUMN negative_title_keywords jsonb NOT NULL DEFAULT '[]'::jsonb;

-- Seed with a conservative, biomedical-focused starter list.
-- Admins edit via the Admin UI afterwards.
UPDATE system_settings SET negative_title_keywords = '[
    "tumor", "tumour", "cancer", "oncology", "carcinoma", "melanoma",
    "antibody", "antigen", "cytokine", "immunoassay",
    "crystallography", "crystallisation", "crystallization",
    "enzyme kinetics", "enzymatic",
    "polymerase", "ribosome", "mitochondria",
    "pharmacokinetics", "pharmacology",
    "clinical trial", "clinical outcome",
    "DNA sequencing", "RNA sequencing", "proteomics", "metabolomics",
    "drug delivery", "drug discovery"
]'::jsonb WHERE id = 1;
