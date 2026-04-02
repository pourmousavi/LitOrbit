# LitOrbit

Private, multi-user academic research intelligence platform for a university research group. Automatically monitors 13 academic journals, discovers new papers, ranks them by personalised relevance per user, generates AI summaries and podcast audio, and delivers digests via a web dashboard and email.

## Architecture

```
SCHEDULER (GitHub Actions cron — 06:00 ACST daily)
        │
        ▼
DISCOVERY ENGINE (RSS + IEEE Xplore API + Scopus API)
        │
        ▼
PRE-FILTER (keyword match — reduces 50+ → ~20 relevant)
        │
        ▼
CLAUDE API ENGINE (per-user scoring + summaries + podcast scripts)
        │
        ▼
EDGE TTS (single or dual voice MP3 podcasts)
        │
        ▼
SUPABASE (PostgreSQL + Auth + Storage)
        │
        ▼
WEB APP (FastAPI backend + React frontend)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, TypeScript, Tailwind CSS v4, React Query, Zustand |
| Backend | FastAPI, SQLAlchemy, Python 3.11+ |
| Database | Supabase (PostgreSQL + Auth + Storage) |
| AI | Anthropic Claude (Haiku for scoring, Sonnet for summaries/podcasts) |
| TTS | Microsoft Edge TTS (free, multi-voice) |
| Hosting | Render (backend), Vercel (frontend) |
| Scheduler | GitHub Actions cron |

## Features

- **Paper Discovery** — IEEE Xplore, Scopus, RSS feeds across 13 journals
- **AI Relevance Scoring** — per-user scores based on interest profiles
- **AI Summaries** — structured summaries (research gap, methodology, findings, relevance)
- **Podcast Generation** — single voice or dual voice (conversational) audio summaries
- **Rating & Feedback Loop** — rate papers, get follow-up questions, auto-learn preferences
- **Paper Sharing** — share papers with annotations between lab members
- **PDF Upload** — upload full-text PDFs for richer summaries, DOI lookup via Unpaywall
- **Email Digests** — weekly/daily HTML digests with top papers
- **Admin Panel** — journal config, user management, pipeline monitoring, keyword management

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- A Supabase project (free tier works)

### 1. Clone and install

```bash
git clone https://github.com/pourmousavi/LitOrbit.git
cd LitOrbit
```

### 2. Backend setup

```bash
cd backend
cp .env.example .env
# Edit .env with your API keys (see Environment Variables below)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 3. Frontend setup

```bash
cd frontend
cp .env.example .env
# Edit .env with your Supabase URL and anon key
npm install
npm run dev
```

### 4. Run with Docker (alternative)

```bash
docker-compose up
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (for pipeline) |
| `IEEE_API_KEY` | IEEE Xplore API key (from developer.ieee.org) |
| `SCOPUS_API_KEY` | Elsevier Scopus API key (from dev.elsevier.com) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `SMTP_USER` | Gmail address for sending digests |
| `SMTP_PASSWORD` | Gmail app password |
| `SECRET_KEY` | Random secret for app security |
| `FRONTEND_URL` | Frontend URL (for CORS) |

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anonymous key |
| `VITE_API_URL` | Backend API URL |

## Monitored Journals (13)

| Journal | Source |
|---|---|
| Nature Energy | RSS |
| Joule | Scopus |
| Patterns | Scopus |
| IEEE Trans. Power Systems | IEEE Xplore |
| IEEE Trans. Sustainable Energy | IEEE Xplore |
| IEEE Trans. Smart Grid | IEEE Xplore |
| IEEE Trans. Industrial Informatics | IEEE Xplore |
| IEEE Trans. Energy Markets, Policy & Regulation | IEEE Xplore |
| Applied Energy | Scopus |
| eTransportation | Scopus |
| Energy | Scopus |
| Journal of Energy Storage | Scopus |
| Journal of Power Sources | Scopus |

## How To

### Add a new journal

1. Go to Admin Panel → Journals tab
2. Click Add and provide name, publisher, source type, and identifier
3. The next pipeline run will include the new journal

### Trigger the pipeline manually

- **Web:** Admin Panel → Pipeline tab → "Run Pipeline Now"
- **GitHub:** Actions tab → "LitOrbit Daily Pipeline" → "Run workflow"
- **CLI:** `python scripts/run_pipeline.py`

### Add new users

1. Create the user in Supabase Auth dashboard
2. Insert a matching row in `user_profiles` table with their interest keywords
3. Or have the admin seed their profile from the Admin Panel → Users tab

## GitHub Actions Secrets

Add these in Settings → Secrets → Actions:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `IEEE_API_KEY`
- `SCOPUS_API_KEY`
- `ANTHROPIC_API_KEY`
- `SMTP_USER`
- `SMTP_PASSWORD`

## Running Tests

```bash
# Backend
cd backend && python -m pytest tests/ -v

# Frontend
cd frontend && npm run test
```

## Deployment

### Backend (Render)

1. Connect the GitHub repo to Render
2. Use `render.yaml` for service configuration
3. Set all environment variables in the Render dashboard
4. Auto-deploys on push to `main`

### Frontend (Vercel)

1. Connect the GitHub repo to Vercel
2. Set root directory to `frontend`
3. Set `VITE_API_URL` to your Render backend URL
4. Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`
5. Auto-deploys on push to `main`
