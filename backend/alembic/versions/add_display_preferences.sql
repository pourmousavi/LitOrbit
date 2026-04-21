-- Add display preference columns to user_profiles (synced across devices).
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS show_pulse_card boolean NOT NULL DEFAULT true;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS show_nav_badge boolean NOT NULL DEFAULT true;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS show_sidebar_stat boolean NOT NULL DEFAULT true;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS show_weekly_toast boolean NOT NULL DEFAULT true;
