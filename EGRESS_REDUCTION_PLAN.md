# Supabase Egress Reduction Plan

## Background

In April–May 2026 the LitOrbit Supabase project blew through the free-tier
egress quota (14.97 GB used vs. the 5 GB limit) and entered the Supabase
"grace period." Investigation showed the egress is not from data volume — the
database is ~60 MB total — but from per-row payload bloat being shipped over
the wire on every read.

The two main contributors:

1. **`papers.embedding` is a 3,072-dim vector stored as JSONB** (~37 kB per
   row). Every `SELECT papers.*` on a list/feed endpoint pulls this even
   though the frontend never reads it back.
2. **`user_profiles.positive_anchors` and `negative_anchors` are JSONB
   arrays where each entry duplicates `papers.embedding`** (the snapshotted
   embedding of every paper the user rated). With the 100-anchor cap on each
   side, the primary user's profile row is **~7.4 MB** — and gets fetched
   ~900 times per cycle = ~6.6 GB of egress from one table.

The full investigation lives in the conversation transcript that produced
this plan.

## Solution: 4 PRs, smallest blast radius first

The fix is staged so each PR ships independently and the app keeps working
between phases. PR 1 alone moves us from ~15 GB / cycle to ~1–2 GB / cycle,
comfortably under the free-tier ceiling. PRs 2A–3 are the long-term
hardening that pays off when the corpus grows past ~5,000 papers.

---

## ☑ PR 1 — Defer heavy columns + drop anchor-embedding duplication

**Status:** in progress (this is the urgent one to land before grace
period expires).

**What it does:**
- `Paper.embedding`, `ReferencePaper.embedding`, `NewsItem.embedding` become
  `deferred=True` on the ORM model. List/feed/detail queries no longer pull
  the 37 kB jsonb blob. The few code paths that actually need the embedding
  (pipeline scorer, news dedup, cross-link compute, news ingest scoring)
  add explicit `.options(undefer(...))`.
- `user_profiles.positive_anchors` / `negative_anchors` entries no longer
  include the duplicated `embedding` field. They now only store
  `{paper_id, source, weight, added_at, tags}`. The pipeline scorer JOINs
  `papers` (and `reference_papers` for `source="reference"`) by paper_id at
  scoring time to fetch embeddings, builds an in-memory `paper_id → embedding`
  lookup, and passes it to `knn_max_similarity`.
- One idempotent migration strips the `embedding` field from existing
  anchor entries.

**Files touched:**
- `backend/app/models/paper.py`, `reference_paper.py`, `news_item.py` —
  `deferred=True` on embedding column
- `backend/app/services/ranking/embedder.py` — `knn_max_similarity`
  signature gains optional `embedding_lookup` parameter (backwards
  compatible — falls back to `anchor["embedding"]` if not supplied)
- `backend/app/pipeline/runner.py` — fetch embeddings via JOIN, pass lookup
  dict, `undefer()` on the scoring SELECT
- `backend/app/services/cross_link_compute.py` — `undefer()` on all 4
  selects
- `backend/app/services/news_dedup_service.py` — `undefer()` on candidates
- `backend/app/services/news_ingest.py` — `undefer()` on unscored items
  query
- `backend/app/routers/ratings.py` — drop `embedding` from anchor entry,
  drop `paper.embedding` fetch
- `backend/app/routers/reference_papers.py` — drop `embedding` from anchor
  entry, project-only query for list endpoint
- `backend/scripts/backfill_anchors.py` — drop `embedding` from anchor entry
- `backend/alembic/versions/phase4_01_strip_anchor_embeddings.sql` — new
  idempotent migration

**Egress impact:** ~80% reduction (≈ 6.6 GB from `user_profiles` + ~3 GB
from `papers` SELECTs disappear immediately).

**Risks:**
- During the deploy window (migration applied → old server still serving),
  a user rating in that ~30 s gap could write a fresh anchor entry with
  `embedding` populated. Self-heals on next mutation. Worst case: one row
  re-bloats by ~37 kB until next rating. Acceptable.
- `knn_max_similarity` legacy path (`anchor["embedding"]`) still works,
  so test suite that pre-loads anchors with `embedding` field unchanged.

**Verification after deploy:**
```sql
-- Should show kB-scale instead of MB-scale
SELECT email,
       pg_size_pretty(pg_column_size(positive_anchors)::bigint) AS pos,
       pg_size_pretty(pg_column_size(negative_anchors)::bigint) AS neg
FROM user_profiles;

-- Confirm embedding key is gone from anchors
SELECT positive_anchors -> 0 FROM user_profiles
WHERE positive_anchors IS NOT NULL AND jsonb_array_length(positive_anchors) > 0;
```
Then trigger a manual pipeline run via admin endpoint and confirm scoring
still produces non-zero `cosine_similarity` values.

---

## ☐ PR 2A — Add pgvector extension + dual-write `embedding_v` column

**Goal:** Land the pgvector column type alongside the existing JSONB column,
without disturbing readers. Sets up for PR 2B to flip readers atomically.

**Why dual-column rather than in-place ALTER:** `run_migrations.py` has a 5 s
client-side timeout and marks files applied even on timeout (per CLAUDE.md
gotcha). An in-place `ALTER COLUMN ... TYPE vector(1536)` against ~700 rows
should run fast, but if it times out we're left with a half-converted column
and no automatic retry. Dual-column with a backfill keeps each step
independently retriable.

**Changes:**
- `backend/requirements.txt` — add `pgvector>=0.3.0`
- `backend/app/models/types.py` — add `Vector1536` TypeDecorator that maps to
  `pgvector.sqlalchemy.Vector(1536)` on Postgres and falls back to `Text`
  (storing JSON) on SQLite. Mirrors the existing `JSONB` TypeDecorator
  pattern so the in-memory test suite keeps working without pgvector.
- `backend/app/database.py` — register the asyncpg pgvector codec on every
  fresh connection via `event.listens_for(engine.sync_engine, "connect")`.
  pgvector's docs show the pattern.
- `backend/app/models/paper.py`, `reference_paper.py`, `news_item.py`,
  `relevance_anchor.py` — keep `embedding: JSONB(deferred=True)`; add
  sibling `embedding_v: Vector1536(deferred=True)`.
- `backend/app/services/ranking/embedder.py` — set `EMBEDDING_DIMS = 1536`
  and add `output_dimensionality=1536` to the Gemini API call.
- All write sites where code does `paper.embedding = vec` also set
  `paper.embedding_v = vec`.
- Readers (scorer, cross-link, dedup, news scorer) keep reading `embedding`
  for now — no behaviour change in this PR.

**Migration (idempotent):**
```sql
-- File: backend/alembic/versions/phase4_02_pgvector_setup.sql
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE papers            ADD COLUMN IF NOT EXISTS embedding_v vector(1536);
ALTER TABLE reference_papers  ADD COLUMN IF NOT EXISTS embedding_v vector(1536);
ALTER TABLE news_items        ADD COLUMN IF NOT EXISTS embedding_v vector(1536);
ALTER TABLE relevance_anchors ADD COLUMN IF NOT EXISTS embedding_v vector(1536);
```

**Backfill (run after deploy, separate script):**

`backend/scripts/backfill_embedding_v.py` — for every row with
`embedding IS NOT NULL AND embedding_v IS NULL`, take the first 1536
entries of the JSONB array, L2-renormalize, write to `embedding_v`.

**Why client-side truncate works:** `gemini-embedding-001` is trained with
Matryoshka Representation Learning. The first N dimensions form a
self-contained sub-embedding. Cosine between two truncated-and-renormalized
1536-dim vectors is internally consistent and very close to the cosine of
two natively-embedded 1536-dim vectors. No re-call to the Gemini API
required.

**Risks:**
- pgvector codec must register on every fresh asyncpg connection or
  unknown-type errors at SELECT time. Use `event.listens_for(...)` with
  `insert=True` so it runs first.

**Egress impact:** 0 — readers still on the JSONB column. PR 2B is where
the savings land.

**Rollback:** `ALTER TABLE ... DROP COLUMN embedding_v;` on each table.
Revert the code. The legacy `embedding` JSONB column is untouched.

---

## ☐ PR 2B — Switch readers to `embedding_v`, drop the JSONB column

**Goal:** Stop reading the 37 kB JSONB blob. Reads now hit the ~6 kB
pgvector binary.

**Prerequisite:** PR 2A deployed and `embedding_v` fully backfilled.
Verify with `SELECT count(*) FROM papers WHERE embedding IS NOT NULL AND embedding_v IS NULL;`
returns 0 across all four tables (papers, reference_papers, news_items,
relevance_anchors).

**Changes:**
- In all four models: rename the `embedding_v` attribute to `embedding`
  (so the canonical name now points at the pgvector column). Delete the
  old JSONB attribute.
- `backend/app/services/ranking/embedder.py` — `cosine_similarity(a, b)`
  unchanged (still operates on `list[float]`). The TypeDecorator's
  `process_result_value` returns `list(value)` from the pgvector binary,
  so all consumer code is unchanged.

**Migration (idempotent, atomic via DO blocks):**
```sql
-- File: backend/alembic/versions/phase4_03_drop_old_embedding_jsonb.sql
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='papers' AND column_name='embedding_v')
     AND EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name='papers' AND column_name='embedding'
                   AND data_type='jsonb')
  THEN
    ALTER TABLE papers DROP COLUMN embedding;
    ALTER TABLE papers RENAME COLUMN embedding_v TO embedding;
  END IF;
END $$;
-- ...same for reference_papers, news_items, relevance_anchors
```

**Critical deploy timing:** Render's flow is `build → run_migrations →
new server replaces old`. There is a brief window where the migration
has run but the OLD server is still serving — that server tries to read
`embedding` as JSONB but it's now a `vector` type, causing asyncpg
unknown-type errors. To minimize risk:
- Merge PR 2B right after the daily cron pipeline completes, so there are
  ~23 hours before the next run.
- The window between migration apply and new server live is typically
  ~30 s on Render. User-facing list endpoints don't read `embedding`
  (it's deferred) so most traffic is unaffected.

**Egress impact:** Final ~10% — the scoring/dedup/cross-link paths that
legitimately need embeddings transfer ~6 kB instead of ~37 kB per row.

**Rollback:** Painful. Need to re-add the JSONB column and re-populate
from a Supabase backup. Mitigation: keep `embedding_v` populated for
at least one full pipeline cycle before flipping, so there's a known-good
state to recover.

---

## ☐ PR 3 — Cleanup pass

**Goal:** Remove dual-write code paths now that the JSONB column is gone.

**Changes:**
- `backend/app/routers/admin.py:1176` — the `Paper.embedding == {}` and
  `Paper.embedding == []` comparisons in the alerts endpoint don't make
  sense for a vector type. Simplify to `Paper.embedding.is_(None)`.
- `backend/scripts/reembed_corpus.py` — the `embedding_task_type` sweep
  is no longer relevant. Either delete or repurpose for "re-embed at
  1536-dim natively" (optional, since truncated 1536 ≈ native 1536).
- `CLAUDE.md` — update the "Database" and "AI model usage" sections to
  mention pgvector and 1536-dim embeddings.

**Egress impact:** 0 — pure cleanup.

**Risks:** None.

---

## Out of scope (flagged for separate follow-ups)

- **Connection pool tuning.** `pg_stat_statements` showed 34k+
  `pgbouncer.get_auth(...)` calls — a separate problem (likely SQLAlchemy's
  `pool_pre_ping=True` plus session-mode pooling adding round-trips).
  Worth investigating after egress is back under control.
- **Frontend caching of `user_profiles`.** React Query already caches but
  the profile query may be re-fetching too often. Tune `staleTime` —
  separate frontend PR.
- **`news_clusters.centroid_embedding`** still JSONB. Small per-cluster,
  low priority. Migrate when convenient.
- **HNSW/IVFFlat indexes on pgvector columns.** Not needed at ~545
  papers; revisit at 5,000+.

---

## Pre-deploy verification queries

Useful baselines before each PR ships:

```sql
-- Per-user anchor sizes (confirms PR 1 worked when re-run after deploy)
SELECT email,
       jsonb_array_length(coalesce(positive_anchors, '[]'::jsonb)) AS pos_count,
       jsonb_array_length(coalesce(negative_anchors, '[]'::jsonb)) AS neg_count,
       pg_size_pretty(pg_column_size(positive_anchors)::bigint) AS pos_bytes,
       pg_size_pretty(pg_column_size(negative_anchors)::bigint) AS neg_bytes
FROM user_profiles;

-- Top egress queries since last reset
SELECT calls, rows,
       pg_size_pretty((shared_blks_hit + shared_blks_read) * 8192) AS buffers,
       left(regexp_replace(query, '\s+', ' ', 'g'), 220) AS query
FROM pg_stat_statements
ORDER BY rows DESC
LIMIT 10;

-- Per-table TOAST / data-size breakdown
SELECT n.nspname AS schema, c.relname AS table,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total,
       pg_size_pretty(pg_relation_size(c.oid)) AS heap,
       c.reltuples::bigint AS approx_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 15;
```
