-- Lock down all public tables from PostgREST (anon/authenticated roles).
-- The backend connects as the `postgres` superuser, which BYPASSES RLS,
-- so enabling RLS with no policies denies external API access while
-- leaving the FastAPI backend fully functional.
ALTER TABLE IF EXISTS public.papers             ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.journal_config     ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.pipeline_runs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.reference_papers   ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.collection_papers  ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.collections        ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.digest_logs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.paper_views        ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.digest_runs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.paper_favorites    ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.deleted_papers     ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.system_settings    ENABLE ROW LEVEL SECURITY;
