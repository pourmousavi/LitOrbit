-- Default digest_podcast_enabled to false for new users.
-- Flip existing non-admin users to false (admin keeps their setting).
ALTER TABLE user_profiles
    ALTER COLUMN digest_podcast_enabled SET DEFAULT false;

UPDATE user_profiles
    SET digest_podcast_enabled = false
    WHERE role != 'admin';
