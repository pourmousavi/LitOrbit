-- Add ownership tracking to papers (nullable for existing pipeline-created papers)
ALTER TABLE papers ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES user_profiles(id);
