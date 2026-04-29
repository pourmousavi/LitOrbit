-- Follow-up to enable_rls_lockdown.sql: lock down tables added by the
-- news_phase* and phase* migrations that PostgREST is still exposing.
-- Backend uses the `postgres` superuser (BYPASSES RLS), and the frontend
-- only uses supabase-js for auth, so enabling RLS with no policies
-- denies external API access while leaving the app fully functional.
ALTER TABLE IF EXISTS public.news_sources        ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.news_items          ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.news_clusters       ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.news_ingest_runs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.relevance_anchors   ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.user_interactions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.scoring_signals     ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.content_cross_links ENABLE ROW LEVEL SECURITY;
