-- Phase 3.2: opt-in flag to route a news source's fetches through the
-- Cloudflare Worker proxy (scripts/news-fetch-proxy-worker.js). Used when
-- the publisher's WAF blocks Render's egress IP (e.g. SiteGround sgcaptcha).
ALTER TABLE news_sources
    ADD COLUMN IF NOT EXISTS use_proxy boolean NOT NULL DEFAULT false;
