# LitOrbit — Step-by-Step Deployment Guide

## Step 1: Set Up Supabase Database

1. Go to https://supabase.com and sign in
2. Click **New Project** — name it `litorbit`, choose a region close to Adelaide (e.g. Southeast Asia)
3. Save the **project password** — you'll need it
4. Once created, go to **Settings → API** and copy:
   - `Project URL` → this is your `SUPABASE_URL`
   - `anon public` key → this is your `SUPABASE_ANON_KEY`
   - `service_role` key → this is your `SUPABASE_SERVICE_ROLE_KEY`

5. Go to **SQL Editor** and paste the full schema below. Run it:

```sql
-- Users (managed by Supabase Auth, extended here)
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  full_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'researcher',
  email TEXT NOT NULL,
  interest_keywords TEXT[] DEFAULT '{}',
  interest_categories TEXT[] DEFAULT '{}',
  interest_vector JSONB DEFAULT '{}',
  podcast_preference TEXT DEFAULT 'single',
  email_digest_enabled BOOLEAN DEFAULT true,
  digest_frequency TEXT DEFAULT 'weekly',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Papers
CREATE TABLE papers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doi TEXT UNIQUE,
  title TEXT NOT NULL,
  authors TEXT[] NOT NULL,
  abstract TEXT,
  full_text TEXT,
  journal TEXT NOT NULL,
  journal_source TEXT NOT NULL,
  published_date DATE,
  early_access BOOLEAN DEFAULT false,
  url TEXT,
  pdf_path TEXT,
  categories TEXT[] DEFAULT '{}',
  summary TEXT,
  summary_generated_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Per-user relevance scores
CREATE TABLE paper_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
  user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
  relevance_score FLOAT NOT NULL,
  score_reasoning TEXT,
  scored_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(paper_id, user_id)
);

-- User ratings and feedback
CREATE TABLE ratings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
  user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
  rating INTEGER CHECK (rating BETWEEN 1 AND 10),
  feedback_type TEXT,
  feedback_note TEXT,
  rated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(paper_id, user_id)
);

-- Podcasts
CREATE TABLE podcasts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
  user_id UUID REFERENCES user_profiles(id),
  voice_mode TEXT NOT NULL DEFAULT 'single',
  script TEXT,
  audio_path TEXT,
  duration_seconds INTEGER,
  generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Shares from admin/researcher to other researchers
CREATE TABLE shares (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
  shared_by UUID REFERENCES user_profiles(id),
  shared_with UUID REFERENCES user_profiles(id),
  annotation TEXT,
  podcast_id UUID REFERENCES podcasts(id),
  is_read BOOLEAN DEFAULT false,
  shared_at TIMESTAMPTZ DEFAULT NOW()
);

-- Journal configuration (admin-controlled)
CREATE TABLE journal_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  publisher TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_identifier TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline run logs
CREATE TABLE pipeline_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  papers_discovered INTEGER DEFAULT 0,
  papers_filtered INTEGER DEFAULT 0,
  papers_processed INTEGER DEFAULT 0,
  error_message TEXT,
  run_log JSONB DEFAULT '[]'
);

-- Row Level Security policies
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE podcasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE shares ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users own their scores" ON paper_scores
  USING (user_id = auth.uid());
CREATE POLICY "Users own their ratings" ON ratings
  USING (user_id = auth.uid());
CREATE POLICY "Users see shares addressed to them" ON shares
  USING (shared_with = auth.uid() OR shared_by = auth.uid());
```

6. Go to **Authentication → Users** and create your admin account:
   - Click **Add User → Create New User**
   - Email: your email, set a password
   - After creating, copy the user's **UUID**

7. Go to **SQL Editor** and insert your admin profile:

```sql
INSERT INTO user_profiles (id, full_name, role, email, interest_keywords, interest_categories)
VALUES (
  'YOUR-UUID-HERE',
  'Ali Pourmousavi',
  'admin',
  'your@email.com',
  ARRAY['battery', 'BESS', 'energy storage', 'electricity market', 'power system', 'forecasting', 'machine learning'],
  ARRAY['energy storage', 'power systems', 'electricity markets', 'renewable energy']
);
```

---

## Step 2: Deploy Backend on Render

1. Go to https://render.com and sign in
2. Click **New → Web Service**
3. Connect your GitHub repo `pourmousavi/LitOrbit`
4. Configure:
   - **Name:** `litorbit-api`
   - **Root Directory:** `backend`
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add each one:

| Key | Value |
|---|---|
| `SUPABASE_URL` | (from Step 1) |
| `SUPABASE_ANON_KEY` | (from Step 1) |
| `SUPABASE_SERVICE_ROLE_KEY` | (from Step 1) |
| `IEEE_API_KEY` | (your key) |
| `SCOPUS_API_KEY` | (your key) |
| `ANTHROPIC_API_KEY` | (your key) |
| `SMTP_USER` | (your Gmail, if ready) |
| `SMTP_PASSWORD` | (Gmail app password, if ready) |
| `ENVIRONMENT` | `production` |
| `FRONTEND_URL` | (leave blank for now, fill after Vercel deploy) |

6. Click **Create Web Service** — wait for it to deploy
7. Once live, note the URL (e.g. `https://litorbit-api.onrender.com`)
8. Test it: visit `https://litorbit-api.onrender.com/health` — should return `{"status": "healthy"}`

---

## Step 3: Deploy Frontend on Vercel

1. Go to https://vercel.com and sign in
2. Click **Add New → Project**
3. Import your GitHub repo `pourmousavi/LitOrbit`
4. Configure:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Vite
5. Under **Environment Variables**, add:

| Key | Value |
|---|---|
| `VITE_SUPABASE_URL` | (same Supabase URL from Step 1) |
| `VITE_SUPABASE_ANON_KEY` | (same anon key from Step 1) |
| `VITE_API_URL` | `https://litorbit-api.onrender.com` (from Step 2) |

6. Click **Deploy** — wait for build
7. Once live, note the URL (e.g. `https://litorbit.vercel.app`)

---

## Step 4: Update Backend CORS

Go back to **Render dashboard → litorbit-api → Environment**:

- Set `FRONTEND_URL` to your Vercel URL (e.g. `https://litorbit.vercel.app`)
- Render will auto-redeploy

---

## Step 5: Set GitHub Actions Secrets

The daily pipeline now runs **inside the Render backend** (Singapore region — needed because GitHub-hosted runners frequently land in regions where the Gemini free API returns `FAILED_PRECONDITION: User location is not supported`). The GitHub Actions workflow only fires a scheduled HTTPS trigger, so it just needs two secrets.

Go to your repo https://github.com/pourmousavi/LitOrbit → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|---|---|
| `LITORBIT_API_URL` | Your Render API base URL, e.g. `https://litorbit-api.onrender.com` |
| `PIPELINE_TRIGGER_SECRET` | Same value as the `PIPELINE_TRIGGER_SECRET` env var on Render |

To grab the Render value: Render dashboard → `litorbit-api` → **Environment** → reveal `PIPELINE_TRIGGER_SECRET` (auto-generated by `render.yaml`). Copy/paste it into the GitHub secret with the **same** name.

All the previous pipeline secrets (`IEEE_API_KEY`, `SCOPUS_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `SUPABASE_*`, `SMTP_*`, `RESEND_API_KEY`) now only need to live on **Render**, not in GitHub Actions.

---

## Step 6: Test the Full Flow

1. Open your Vercel URL in a browser
2. Log in with the admin account you created in Step 1
3. You should see the Feed page (empty initially)
4. Go to **Admin → Pipeline → Run Pipeline Now** to trigger discovery
5. Wait 1-2 minutes, then refresh the Feed — papers should appear
6. Click a paper to see the detail panel with AI summary
7. Rate a paper — the feedback dialog should appear
8. Generate a podcast — click Generate, wait 30-60s, then play

---

## Gmail App Password (for email digests)

If you want email digests working:

1. Go to https://myaccount.google.com/apppasswords
2. You need 2-factor auth enabled on your Google account
3. Generate an app password for "Mail"
4. Use that 16-character password as `SMTP_PASSWORD`
5. Use your Gmail address as `SMTP_USER`

---

## Troubleshooting

### Backend returns 500 errors
- Check Render logs for the specific error
- Most common: missing environment variables — double-check all are set

### Frontend shows "Loading..." forever
- Check browser console for errors
- Verify `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are correct
- Verify the Supabase project is running

### Login fails
- Ensure the user exists in Supabase Auth
- Ensure a matching `user_profiles` row exists with the same UUID
- Check that the Supabase anon key is correct

### Pipeline finds no papers
- Check Admin → Pipeline tab for error messages
- IEEE API: key may still be "waiting" for activation
- Scopus API: verify the key works (most likely cause of empty results)
- Check Render logs for detailed API responses

### Podcast generation fails
- Requires `ANTHROPIC_API_KEY` for script generation
- Edge TTS is free and should work without keys
- Check Render logs for the specific error

### CORS errors in browser
- Ensure `FRONTEND_URL` on Render matches your exact Vercel URL
- Include the protocol (`https://`) and no trailing slash
