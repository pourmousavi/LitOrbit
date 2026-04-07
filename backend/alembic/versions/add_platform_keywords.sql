-- Phase 1: persist platform-scope keywords (formerly MASTER_KEYWORDS) in DB
-- so admin edits survive restarts. Seeded from the hardcoded list in
-- backend/app/services/ranking/prefilter.py.

ALTER TABLE system_settings
  ADD COLUMN IF NOT EXISTS platform_keywords JSONB NOT NULL DEFAULT '[]'::jsonb;

UPDATE system_settings
SET platform_keywords = '[
  "battery","BESS","energy storage","lithium","degradation",
  "state of charge","SOC","SOH",
  "power system","grid","transmission","distribution",
  "frequency","voltage","stability",
  "electricity market","NEM","FCAS","ancillary services",
  "market clearing","dispatch","bidding",
  "solar","wind","renewable","photovoltaic","PV",
  "forecasting","machine learning","deep learning","neural network",
  "prediction","optimization","reinforcement learning",
  "electric vehicle","EV","charging","V2G",
  "MILP","convex","stochastic","robust optimization",
  "model predictive control","MPC"
]'::jsonb
WHERE id = 1 AND (platform_keywords IS NULL OR platform_keywords = '[]'::jsonb);
