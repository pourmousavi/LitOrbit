# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LitOrbit is an academic research intelligence platform that monitors 13+ journals, discovers papers, ranks them by personalized relevance using AI, generates summaries and podcast audio, and delivers digests via web dashboard and email. Multi-user, multi-research-group.

## Common Commands

### Frontend (from `frontend/`)
```bash
npm run dev          # Start Vite dev server (localhost:5173)
npm run build        # TypeScript check + Vite build
npm run lint         # ESLint
npm run test         # Vitest (single run)
npm run test:watch   # Vitest (watch mode)
```

### Backend (from `backend/`)
```bash
uvicorn app.main:app --reload --port 8000   # Dev server
pytest tests/ -v                             # All tests
pytest tests/test_ranking.py -v              # Single test file
pytest tests/test_ranking.py::test_name -v   # Single test
python scripts/run_pipeline.py               # Manually trigger pipeline
```

### Backend test dependencies
```bash
pip install -r requirements-dev.txt   # includes requirements.txt + pytest + pytest-asyncio
pip install aiosqlite                 # needed for in-memory SQLite test DB
```

### Database migrations
This repo does **not** use Alembic CLI. Migrations are plain SQL files in
`backend/alembic/versions/` (the directory name is a historical artefact),
auto-applied on every Render deploy by `backend/run_migrations.py`. A
`_migrations` tracking table records which files have run, so re-applying
is safe.

To add a migration: drop a new `*.sql` file into `backend/alembic/versions/`.
Files run in alphabetical filename order — name new ones with a sortable
prefix (existing prefixes: `phase1_*`, `phase2_*`, `phase3_*`, `news_phase*`,
or descriptive like `add_*.sql`). Make every statement idempotent
(`ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) since the runner
marks files as applied even if they timed out.

To apply locally against the configured `DATABASE_URL`:
```bash
cd backend && python run_migrations.py
```

### Docker (from root)
```bash
docker-compose up    # Start both backend (:8000) and frontend (:5173)
```

## Architecture

### Two-service monorepo
- **`backend/`** — FastAPI (Python, async), Supabase PostgreSQL via asyncpg + SQLAlchemy 2.0
- **`frontend/`** — React 19 + TypeScript, Vite, Tailwind CSS v4, Zustand stores, React Query

### Pipeline (backend/app/pipeline/runner.py)
The core daily pipeline runs as a multi-stage process:
1. **Discover** — Fetch from IEEE Xplore API, Scopus API, and RSS feeds
2. **Deduplicate** — Cross-source dedup (`services/discovery/deduplicator.py`)
3. **Pre-filter** — Keyword-based filtering via Claude Haiku (`services/ranking/prefilter.py`)
4. **Embed** — Text embeddings for semantic matching (`services/ranking/embedder.py`)
5. **Score** — Per-user relevance scoring with k-NN anchor gating (`services/ranking/scorer.py`)
6. **Summarize** — Claude Sonnet generates summaries (`services/summariser.py`)
7. **Podcast** — Script generation + Edge TTS multi-voice audio (`services/podcast.py`)
8. **Digest** — HTML email via Resend/SMTP (`services/email_digest.py`)

Triggered daily via GitHub Actions cron (`.github/workflows/pipeline.yml`) or manually via admin endpoint.

The cron hits `POST /api/v1/admin/pipeline/run-scheduled` (header-secret
auth). The endpoint is **idempotent** — if a `PipelineRun` is already
in-flight (`status='running'`, started < 30 min ago) it returns
`{"status": "already_running", ...}` immediately, so curl `--retry`
on transient edge errors won't spawn duplicates. Successful triggers
return a **streaming `application/x-ndjson` body** that emits a
heartbeat line every ~25 s while the (often >30 min) job runs and a
final `{"event": "complete", ...}` line on finish. The streaming
shape exists to keep Cloudflare/Render edge proxies from idle-timing
out the long synchronous request — the previous shape produced 502s
after ~13 min of silence and triggered duplicate retries.

### News Pipeline
Separate ingestion pipeline for industry news:
- **Sources** — Configurable per-user news sources (`services/news_sources_service.py`)
- **Scrape** — Web scraping and content extraction (`services/news_scraper_service.py`)
- **Score** — LLM-based relevance scoring (`services/news_scorer.py`)
- **Dedup** — Clustering similar news items (`services/news_dedup_service.py`)
- **Ingest** — Orchestrates the news pipeline (`services/news_ingest.py`)

### Backend routing
All API routers in `backend/app/routers/`. Key ones: `papers.py`, `feed.py`, `unified_feed.py`, `ratings.py`, `podcasts.py`, `admin.py`, `news.py`, `collections.py`, `engagement.py`, `reference_papers.py`, `shares.py`, `users.py`. Auth via Supabase JWT (`app/auth.py`).

### Frontend state
- **Zustand stores** in `src/stores/` — auth, player, UI, pulse settings, scholarLib
- **React Query hooks** in `src/hooks/` — `usePapers`, `useFeed`, `useProfile`, `usePodcast`, `useNewsItem`, `useEngagement`, `useReferencePapers`
- **API client** in `src/lib/api.ts` — Axios instance with auth interceptor

### Database
- PostgreSQL on Supabase (auth + storage + DB)
- Raw SQL migration files in `backend/alembic/versions/`, applied by
  `backend/run_migrations.py` on Render deploy (see "Database migrations" above)
- Models in `backend/app/models/` — `Paper`, `UserProfile`, `PaperScore`, `Rating`, `Podcast`, `NewsItem`, `NewsSource`, `NewsCluster`, `Collection`, `ReferencePaper`, `RelevanceAnchor`, `Share`, `DigestLog`, `DigestRun`, `PipelineRun`, `ScoringSignal`, etc.
- Tests use in-memory SQLite via aiosqlite (see `backend/tests/conftest.py`)

### AI model usage
- **Claude Haiku** — Fast scoring/pre-filtering
- **Claude Sonnet** — Summaries, podcast scripts
- **Google Gemini** — Fallback scorer (proxied via Cloudflare Worker for geo-restrictions)
- **Edge TTS** — Multi-voice podcast audio synthesis
- **Voyage AI** — Text embeddings for semantic matching

### Key Services
- `services/relevance_service.py` — Anchor-based semantic relevance scoring
- `services/cross_link_compute.py` — Cross-linking between papers and news
- `services/retention_purge.py` — Data retention and cleanup
- `services/pdf_processor.py` — PDF extraction and processing
- `services/storage.py` — Supabase storage integration
- `services/digest_runner.py` — Digest orchestration
- `services/digest_podcast.py` — Podcast generation for digests

### Deployment
- **Backend** → Render (Python, Oregon region for Gemini compatibility)
- **Frontend** → Vercel
- **CI/CD** → GitHub Actions: `deploy.yml` runs tests on push to main, `pipeline.yml` runs daily discovery

### Cloudflare Workers (egress proxies)

The backend runs from Render's Oregon datacenter, whose IPs are blocked
or geo-restricted by some upstream services. We route around this with
small per-purpose Cloudflare Workers that fetch from CF's edge IPs
instead. Both follow the same path-prefix-secret auth pattern: the
backend stores `<worker-url>/<secret>` as one env var; the worker
validates the first path segment matches its `PROXY_SHARED_SECRET`.

**Existing workers (single-file, deployed via dashboard):**
- `scripts/gemini-proxy-worker.js` — bypasses Google's geo-restriction
  on Render IPs. Backend env var: `GEMINI_API_BASE`.
- `scripts/news-fetch-proxy-worker.js` — bypasses publisher WAFs that
  challenge datacenter IPs (e.g. SiteGround `sgcaptcha`) for news RSS
  fetches and article scraping. Backend env var: `NEWS_FETCH_PROXY_BASE`.
  Used opt-in per news source via `NewsSource.use_proxy`. Hostname
  allowlist in the worker prevents open-relay abuse.

**Adding a new news source whose WAF blocks Render:**
1. Edit `scripts/news-fetch-proxy-worker.js` → add the publisher's
   hostname (and `www.<host>` if applicable) to `ALLOWED_HOSTS`.
2. CF Dashboard → the existing `litorbit-news-fetch` worker → paste the
   updated file contents over the editor → Deploy.
3. LitOrbit admin → News Sources → tick **Use proxy** on the source →
   Save → click **Test** to confirm.

**Deploying a new worker from scratch** is documented in the header
comment of each `*-worker.js` file (CF dashboard → Create → Worker →
"Start with Hello World!" → paste contents → add the
`PROXY_SHARED_SECRET` secret → set the corresponding `*_BASE` env var on
Render with `<worker-url>/<secret>`).

## Known gotchas

- **News ingest runs can still wedge in `status="running"`** if the
  FastAPI process is killed hard enough that the `try/finally`
  lifecycle write in `ingest_all_enabled_sources` doesn't get to
  execute (e.g. SIGKILL, OOM-killed worker, Render dyno cycle mid
  await). The next `ingest_all_enabled_sources` call sweeps anything
  `status='running'` older than 30 min and marks it `failed` (mirrors
  `runner.py:574` for `PipelineRun`). For an immediate cleanup without
  waiting for the next ingest, run via Supabase SQL editor:
  ```sql
  UPDATE news_ingest_runs
  SET status = 'failed',
      completed_at = now(),
      error_message = 'abandoned'
  WHERE status = 'running'
    AND started_at < now() - interval '30 minutes';
  ```
- **Dedup tests must use relative dates.** `assign_cluster` only
  considers candidate items within `DEDUP_WINDOW_DAYS=7` of now.
  Hardcoded `published_at=datetime(YYYY, M, D, ...)` fixtures silently
  expire once the wall clock crosses the boundary. Use
  `datetime.now(tz) - timedelta(hours=N)` instead. See
  `tests/test_news_dedup.py`.
- **Migration files must be idempotent.** `run_migrations.py` marks a
  file as applied even on timeout, so a non-idempotent `ALTER TABLE`
  that half-runs will leave the schema broken with no retry. Always use
  `IF NOT EXISTS` / `IF EXISTS` guards.

## Git Workflow

Push directly to `main`, no feature branches.

## Behavioral Guidelines

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
