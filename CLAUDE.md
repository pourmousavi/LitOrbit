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

### Database migrations (from `backend/`)
```bash
alembic upgrade head                          # Apply all migrations
alembic revision --autogenerate -m "message"  # Create new migration
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
- 36 Alembic migrations in `backend/alembic/versions/`
- Models in `backend/app/models/` — `Paper`, `UserProfile`, `PaperScore`, `Rating`, `Podcast`, `NewsItem`, `NewsSource`, `NewsCluster`, `Collection`, `ReferencePaper`, `RelevanceAnchor`, `Share`, `DigestLog`, `DigestRun`, `PipelineRun`, etc.
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
