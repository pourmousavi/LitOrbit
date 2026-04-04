-- Migration: Add podcast RSS feed support to user_profiles
-- Allows users to expose their digest podcasts as a standard RSS feed
-- that can be added to any podcast app (Pocket Casts, Overcast, AntennaPod, etc.)

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS podcast_feed_enabled BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS podcast_feed_token VARCHAR UNIQUE,
    ADD COLUMN IF NOT EXISTS podcast_feed_title TEXT,
    ADD COLUMN IF NOT EXISTS podcast_feed_description TEXT,
    ADD COLUMN IF NOT EXISTS podcast_feed_author VARCHAR,
    ADD COLUMN IF NOT EXISTS podcast_feed_cover_url TEXT;
