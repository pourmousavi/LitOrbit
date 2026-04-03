-- Add podcast prompt and voice settings to user_profiles
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS single_voice_prompt TEXT;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS dual_voice_prompt TEXT;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS single_voice_id VARCHAR;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS dual_voice_alex_id VARCHAR;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS dual_voice_sam_id VARCHAR;
