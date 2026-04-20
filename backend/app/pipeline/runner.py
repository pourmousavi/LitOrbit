import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_score import PaperScore
from app.models.user_profile import UserProfile
from app.models.journal_config import JournalConfig
from app.models.pipeline_run import PipelineRun
from app.services.discovery.ieee import fetch_all_ieee_journals
from app.services.discovery.scopus import fetch_all_scopus_journals
from app.services.discovery.rss import fetch_all_rss_journals
from app.services.discovery.deduplicator import deduplicate_papers
from app.services.ranking.prefilter import prefilter_papers
from app.services.ranking.scorer import score_paper_for_user
from app.services.ranking.embedder import (
    embed_texts,
    prepare_paper_text,
    cosine_similarity,
    knn_max_similarity,
)
from app.services.summariser import generate_summary

logger = logging.getLogger(__name__)


async def get_active_journals(db: AsyncSession) -> list[dict]:
    """Load active journal configs from DB."""
    result = await db.execute(
        select(JournalConfig).where(JournalConfig.is_active == True)
    )
    journals = result.scalars().all()
    return [
        {
            "name": j.name,
            "publisher": j.publisher,
            "source_type": j.source_type,
            "source_identifier": j.source_identifier,
        }
        for j in journals
    ]


async def get_all_users(db: AsyncSession) -> list[dict]:
    """Load all user profiles from DB."""
    result = await db.execute(select(UserProfile))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "full_name": u.full_name,
            "interest_keywords": u.interest_keywords or [],
            "interest_categories": u.interest_categories or [],
            # DEPRECATED: interest_vector replaced by positive_anchors; kept for back-compat
            "interest_vector": u.interest_vector or {},
            "category_weights": u.category_weights or {},
            "scoring_prompt": u.scoring_prompt,
            "positive_anchors": u.positive_anchors or [],
            "negative_anchors": u.negative_anchors or [],
        }
        for u in users
    ]


async def get_existing_dois(db: AsyncSession) -> set[str]:
    """Get all DOIs already stored or previously deleted."""
    from app.models.deleted_paper import DeletedPaper

    result = await db.execute(select(Paper.doi).where(Paper.doi.isnot(None)))
    dois = {row[0] for row in result.all()}

    # Also exclude DOIs of papers the user has deleted
    deleted_result = await db.execute(select(DeletedPaper.doi).where(DeletedPaper.doi.isnot(None)))
    dois.update(row[0] for row in deleted_result.all())

    return dois


async def get_existing_titles(db: AsyncSession) -> set[str]:
    """Get normalised titles of all papers in the database (for no-DOI dedup)."""
    from app.models.deleted_paper import DeletedPaper

    result = await db.execute(select(Paper.title).where(Paper.title.isnot(None)))
    titles = {row[0].lower().strip() for row in result.all()}

    deleted_result = await db.execute(select(DeletedPaper.title).where(DeletedPaper.title.isnot(None)))
    titles.update(row[0].lower().strip() for row in deleted_result.all())

    return titles


async def save_papers(db: AsyncSession, papers: list[dict[str, Any]]) -> int:
    """Save new papers to the database. Returns count of papers saved."""
    saved = 0
    for paper_data in papers:
        paper = Paper(
            id=uuid.uuid4(),
            doi=paper_data.get("doi"),
            title=paper_data["title"],
            authors=paper_data.get("authors", []),
            abstract=paper_data.get("abstract"),
            journal=paper_data.get("journal", ""),
            journal_source=paper_data.get("journal_source", ""),
            published_date=_parse_date(paper_data.get("published_date")),
            online_date=_parse_date(paper_data.get("online_date")),
            early_access=paper_data.get("early_access", False),
            url=paper_data.get("url"),
            keywords=paper_data.get("keywords", []),
        )
        db.add(paper)
        saved += 1

    await db.commit()
    return saved


async def save_scores(
    db: AsyncSession,
    paper_id: uuid.UUID,
    scores: list[dict[str, Any]],
) -> int:
    """Save relevance scores for a paper across all users."""
    saved = 0
    for score_data in scores:
        score = PaperScore(
            id=uuid.uuid4(),
            paper_id=paper_id,
            user_id=uuid.UUID(score_data["user_id"]),
            relevance_score=score_data["score"],
            score_reasoning=score_data.get("reasoning"),
        )
        db.add(score)
        saved += 1
    await db.commit()
    return saved


async def embed_unembedded_papers(db: AsyncSession) -> dict[str, Any]:
    """Embed all papers that don't have embeddings yet.

    Returns dict with counts and quota status.
    """
    import sys
    from sqlalchemy import or_, text as sa_text

    # Debug: count papers with NULL embedding directly via raw SQL
    raw_count = await db.execute(sa_text(
        "SELECT count(*) FROM papers WHERE embedding IS NULL"
    ))
    null_count = raw_count.scalar()

    raw_total = await db.execute(sa_text("SELECT count(*) FROM papers"))
    total_count = raw_total.scalar()

    # Check what values the embedding column actually contains
    sample = await db.execute(sa_text(
        "SELECT id, embedding IS NULL as is_null, "
        "jsonb_typeof(embedding) as etype, "
        "CASE WHEN embedding IS NOT NULL THEN length(embedding::text) ELSE 0 END as elen "
        "FROM papers LIMIT 5"
    ))
    sample_rows = sample.all()
    sample_info = [
        f"{row[0]}:null={row[1]},type={row[2]},len={row[3]}"
        for row in sample_rows
    ]

    # Log to stderr (Render always captures this)
    debug_msg = (
        f"[EMBED] null_embedding={null_count}/{total_count} "
        f"samples=[{'; '.join(sample_info)}]"
    )
    print(debug_msg, file=sys.stderr, flush=True)
    logger.warning(debug_msg)  # WARNING level guaranteed to show

    # First, fix existing data: convert JSONB null to SQL NULL
    fix_result = await db.execute(sa_text(
        "UPDATE papers SET embedding = NULL "
        "WHERE embedding IS NOT NULL AND jsonb_typeof(embedding) = 'null'"
    ))
    fixed = fix_result.rowcount
    if fixed:
        await db.commit()
        logger.warning(f"[EMBED] Fixed {fixed} papers with JSONB null → SQL NULL")

    result = await db.execute(
        select(Paper).where(Paper.embedding.is_(None))
    )
    papers = result.scalars().all()

    logger.warning(f"[EMBED] ORM query returned {len(papers)} unembedded papers")

    if not papers:
        # Include debug info in the return so it shows in the Admin UI run log
        return {
            "embedded": 0, "skipped": 0, "quota_exhausted": False,
            "debug": f"null={null_count}/{total_count}, samples={sample_info[:3]}",
        }

    texts = [prepare_paper_text(p.title, p.abstract or "") for p in papers]

    try:
        embeddings = await embed_texts(texts)
    except Exception as e:
        logger.error(f"Embedding failed (non-quota error): {e}")
        return {"embedded": 0, "skipped": len(papers), "quota_exhausted": False, "error": str(e)}

    embedded = 0
    skipped = 0
    quota_exhausted = False

    for paper, embedding in zip(papers, embeddings):
        if embedding is not None:
            paper.embedding = embedding
            embedded += 1
        else:
            skipped += 1
            quota_exhausted = True

    await db.commit()

    if quota_exhausted:
        logger.warning(
            f"Embedding quota exhausted: {embedded} embedded, {skipped} skipped. "
            f"Skipped papers will use keyword fallback for scoring."
        )
    else:
        logger.info(f"Embedded {embedded} papers")

    return {"embedded": embedded, "skipped": skipped, "quota_exhausted": quota_exhausted}


async def score_and_summarise_papers(
    db: AsyncSession,
    run: PipelineRun,
) -> dict[str, int]:
    """Run prefilter, scoring, and summarisation on unprocessed papers.

    Returns dict with counts.
    """
    # Get all users for scoring
    users = await get_all_users(db)
    if not users:
        logger.warning("No users found, skipping scoring")
        return {"prefiltered": 0, "scored": 0, "summarised": 0}

    # Build set of existing (paper_id, user_id) score pairs to avoid re-scoring
    existing_scores_q = select(PaperScore.paper_id, PaperScore.user_id)
    existing_scores_result = await db.execute(existing_scores_q)
    existing_score_pairs: set[tuple] = {
        (row[0], row[1]) for row in existing_scores_result.all()
    }

    all_papers_result = await db.execute(select(Paper))
    all_papers = all_papers_result.scalars().all()

    # Find papers that need scoring for at least one user
    user_ids = {uuid.UUID(u["id"]) for u in users}
    papers_needing_scores = []
    for p in all_papers:
        missing_users = {uid for uid in user_ids if (p.id, uid) not in existing_score_pairs}
        if missing_users:
            papers_needing_scores.append(p)

    if not papers_needing_scores:
        logger.info("No papers need scoring for any user")
        return {"prefiltered": 0, "scored": 0, "summarised": 0}

    logger.info(f"{len(papers_needing_scores)} papers need scoring for at least one user")

    # Convert to dicts for scoring
    paper_dicts = [
        {
            "id": str(p.id),
            "title": p.title,
            "abstract": p.abstract or "",
            "authors": p.authors,
            "journal": p.journal,
            "keywords": p.keywords or [],
            "embedding": p.embedding,
        }
        for p in papers_needing_scores
    ]

    DEFAULT_SIMILARITY_THRESHOLD = 0.50
    DEFAULT_NEGATIVE_ANCHOR_LAMBDA = 0.5

    # Per-user filtering: k-NN max-over-anchors if available, keyword fallback otherwise
    # Build a map of user_id -> papers to score for that user (excluding already-scored pairs)
    user_papers_map: dict[str, list[dict]] = {}
    keyword_fallback_count = 0
    embedding_filter_count = 0

    # Load admin-managed platform-scope keywords and thresholds from system_settings
    from app.models.system_settings import SystemSettings
    settings_row = (await db.execute(select(SystemSettings).where(SystemSettings.id == 1))).scalar_one_or_none()
    platform_keywords = (settings_row.platform_keywords if settings_row and settings_row.platform_keywords else None)
    threshold = settings_row.similarity_threshold if settings_row else DEFAULT_SIMILARITY_THRESHOLD
    lam = settings_row.negative_anchor_lambda if settings_row else DEFAULT_NEGATIVE_ANCHOR_LAMBDA

    # Keyword-filtered papers (computed once, used as fallback)
    keyword_filtered = prefilter_papers(paper_dicts, keywords=platform_keywords)
    keyword_filtered_ids = {p["id"] for p in keyword_filtered}

    for user in users:
        uid = uuid.UUID(user["id"])
        positive_anchors = user.get("positive_anchors") or []
        negative_anchors = user.get("negative_anchors") or []
        has_anchors = bool(positive_anchors) or bool(negative_anchors)

        # Only include papers this user hasn't scored yet
        user_unscored = [pd for pd in paper_dicts if (uuid.UUID(pd["id"]), uid) not in existing_score_pairs]
        if not user_unscored:
            continue

        if has_anchors:
            # k-NN max-over-anchors filter with negative anchor penalty.
            # Personal-keyword escape hatch preserved from the old centroid path.
            user_kw_ids: set[str] = set()
            user_kws = user.get("interest_keywords") or []
            if user_kws:
                from app.services.ranking.prefilter import prefilter_papers as _pf
                user_kw_ids = {p["id"] for p in _pf(user_unscored, keywords=user_kws)}

            matched = []
            for pd in user_unscored:
                paper_emb = pd.get("embedding")
                if isinstance(paper_emb, list) and len(paper_emb) > 0:
                    max_pos, best_pos_id, _ = knn_max_similarity(paper_emb, positive_anchors)
                    max_neg, best_neg_id, _ = knn_max_similarity(paper_emb, negative_anchors)
                    effective = max_pos - lam * max_neg
                    passed_semantic = effective >= threshold

                    if passed_semantic:
                        pd_copy = {**pd, "cosine_similarity": round(max_pos, 4), "cosine_negative": round(max_neg, 4)}
                        matched.append(pd_copy)
                    elif pd["id"] in user_kw_ids:
                        # Personal-keyword escape hatch
                        pd_copy = {**pd, "cosine_similarity": round(max_pos, 4), "cosine_negative": round(max_neg, 4)}
                        matched.append(pd_copy)
                elif pd["id"] in keyword_filtered_ids:
                    # Paper has no embedding — fall back to platform-scope keyword match
                    matched.append(pd)
                elif pd["id"] in user_kw_ids:
                    matched.append(pd)
            user_papers_map[user["id"]] = matched
            embedding_filter_count += 1
        else:
            # No anchors — use keyword fallback (only unscored papers)
            user_papers_map[user["id"]] = [pd for pd in user_unscored if pd["id"] in keyword_filtered_ids]
            keyword_fallback_count += 1

    logger.info(
        f"Filtering: {embedding_filter_count} users with embedding filter, "
        f"{keyword_fallback_count} users with keyword fallback"
    )

    scored_count = 0
    summarised_count = 0
    import json as json_module
    import asyncio as aio

    BATCH_SIZE = 5

    # Collect all (paper, user) pairs to score, then dedupe per paper
    # Track which papers need scoring for which users
    all_scores: dict[str, list[dict]] = {}  # paper_id -> list of score dicts

    from app.services.gemini_client import make_genai_client
    _client = make_genai_client()

    # Finalize any implicit transaction left open by earlier SELECTs and return
    # the connection to the pool BEFORE the long LLM scoring phase. Doing this
    # while the connection is still alive avoids a later cleanup-on-dead-conn
    # crash if Supabase's pooler reaps it during the idle gap. The next DB op
    # will auto-begin a new transaction with a fresh, pre-pinged checkout.
    await db.commit()

    for user in users:
        user_papers = user_papers_map.get(user["id"], [])
        if not user_papers:
            continue

        for i in range(0, len(user_papers), BATCH_SIZE):
            batch = user_papers[i:i + BATCH_SIZE]

            async def _score(pd: dict, u: dict = user) -> tuple[str, dict]:
                result = await score_paper_for_user(pd, u, _client, u.get("scoring_prompt"))
                return pd["id"], {
                    "user_id": u["id"],
                    "score": result["score"],
                    "reasoning": result["reasoning"],
                    "error": result.get("error", False),
                }

            results = await aio.gather(*[_score(pd) for pd in batch])

            for paper_id_str, score_data in results:
                all_scores.setdefault(paper_id_str, []).append(score_data)
                scored_count += 1

    # Save all scores and determine which papers to summarise
    papers_to_summarise = []
    paper_dict_map = {pd["id"]: pd for pd in paper_dicts}

    for paper_id_str, scores in all_scores.items():
        paper_id = uuid.UUID(paper_id_str)
        # Filter out errored scores — do not persist them; they'll be retried next run
        valid_scores = [s for s in scores if not s.get("error") and s.get("score") is not None]
        errored = [s for s in scores if s.get("error")]
        for e in errored:
            logger.warning(
                f"Scorer error for paper {paper_id_str[:8]} user {e['user_id'][:8]}: {e['reasoning']}"
            )
        if valid_scores:
            await save_scores(db, paper_id, valid_scores)
        non_none_scores = [s["score"] for s in valid_scores if s["score"] is not None]
        max_score = max(non_none_scores) if non_none_scores else 0
        if max_score >= 5.0:
            papers_to_summarise.append((paper_dict_map[paper_id_str], paper_id))
        logger.info(f"Saved scores for paper {paper_id_str[:8]}...: max_score={max_score:.1f} ({len(errored)} errored)")
        # Commit per paper so the connection is returned to the pool between writes
        # rather than held across the whole scoring-save phase.
        await db.commit()

    total_papers_with_scores = len(all_scores)
    logger.info(f"Scored {scored_count} (paper, user) pairs across {total_papers_with_scores} papers")

    # Phase 2: Summarise qualifying papers in batches.
    # Run LLM calls *without* holding a DB connection, then write results sequentially.
    async def _summarise_llm_only(paper_dict: dict) -> dict | None:
        return await generate_summary(paper_dict)

    for i in range(0, len(papers_to_summarise), BATCH_SIZE):
        batch = papers_to_summarise[i:i + BATCH_SIZE]

        # Finalize any open implicit txn and release the conn to the pool BEFORE
        # the long LLM gather, while the conn is still alive. See note above the
        # scoring loop for the rationale.
        await db.commit()

        summaries = await aio.gather(*[_summarise_llm_only(pd) for pd, _pid in batch])

        # Now do brief DB writes
        batch_written = 0
        for (_pd, paper_id), summary in zip(batch, summaries):
            if not summary:
                continue
            paper_obj = await db.get(Paper, paper_id)
            if paper_obj:
                paper_obj.summary = json_module.dumps(summary)
                paper_obj.categories = summary.get("categories", [])
                paper_obj.summary_generated_at = datetime.now(timezone.utc)
                batch_written += 1
        await db.commit()
        summarised_count += batch_written
        logger.info(f"Summarised batch {i // BATCH_SIZE + 1}: {batch_written}/{len(batch)}")

    return {
        "prefiltered": total_papers_with_scores,
        "scored": scored_count,
        "summarised": summarised_count,
        "embedding_users": embedding_filter_count,
        "keyword_fallback_users": keyword_fallback_count,
    }


def _parse_date(date_str: str | None):
    """Parse a date string to a date object."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


async def run_discovery_pipeline(db: AsyncSession) -> dict[str, Any]:
    """Run the full paper discovery pipeline.

    Returns:
        Summary dict with counts and status.
    """
    # Sweep orphaned runs left as 'running' by previous processes that died
    # before reaching the except/cleanup block (e.g. GH Actions timeout, OOM,
    # forced cancel). Anything still 'running' after 30 min is considered dead
    # (the pipeline + digest timeout budget is ~9 min).
    orphan_cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    orphan_result = await db.execute(
        select(PipelineRun).where(
            PipelineRun.status == "running",
            PipelineRun.started_at < orphan_cutoff,
        )
    )
    orphans = orphan_result.scalars().all()
    for orphan in orphans:
        orphan.status = "failed"
        orphan.completed_at = datetime.now(timezone.utc)
        orphan.error_message = "Orphaned run — process died before cleanup (auto-marked failed on next pipeline start)"
    if orphans:
        logger.warning(f"Auto-marked {len(orphans)} orphaned pipeline run(s) as failed")
        await db.commit()

    run = PipelineRun(
        id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        status="running",
        run_log=[],
    )
    db.add(run)
    await db.commit()

    try:
        # Load journal configs
        journals = await get_active_journals(db)
        if not journals:
            logger.warning("No active journals configured")
            run.status = "failed"
            run.error_message = "No active journals configured"
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"status": "failed", "error": "No active journals configured"}

        ieee_journals = [j for j in journals if j["source_type"] == "ieee_api"]
        scopus_journals = [j for j in journals if j["source_type"] == "scopus_api"]
        rss_journals = [j for j in journals if j["source_type"] == "rss"]

        logger.info(f"Fetching from {len(ieee_journals)} IEEE, {len(scopus_journals)} Scopus, {len(rss_journals)} RSS journals")

        # Discover papers from all sources
        all_papers: list[dict[str, Any]] = []

        if ieee_journals:
            ieee_papers = await fetch_all_ieee_journals(ieee_journals)
            all_papers.extend(ieee_papers)
            logger.info(f"IEEE: {len(ieee_papers)} papers")

        if scopus_journals:
            scopus_papers = await fetch_all_scopus_journals(scopus_journals)
            all_papers.extend(scopus_papers)
            logger.info(f"Scopus: {len(scopus_papers)} papers")

        if rss_journals:
            rss_papers = await fetch_all_rss_journals(rss_journals)
            all_papers.extend(rss_papers)
            logger.info(f"RSS: {len(rss_papers)} papers")

        run.papers_discovered = len(all_papers)

        # Filter junk entries (TOCs, covers, ads, etc.)
        from app.services.discovery.deduplicator import filter_junk_papers
        pre_filter_count = len(all_papers)
        all_papers = filter_junk_papers(all_papers)
        junk_removed = pre_filter_count - len(all_papers)
        if junk_removed:
            run.run_log.append({"step": "junk_filter", "removed": junk_removed})

        # Deduplicate
        existing_dois = await get_existing_dois(db)
        existing_titles = await get_existing_titles(db)
        unique_papers = deduplicate_papers(all_papers, existing_dois, existing_titles)
        run.papers_filtered = len(unique_papers)

        logger.info(f"After dedup: {len(unique_papers)} unique new papers (from {len(all_papers)} raw)")

        # Save to database
        saved_count = await save_papers(db, unique_papers)
        run.papers_processed = saved_count

        # Embed papers that don't have embeddings yet
        embed_results = await embed_unembedded_papers(db)

        # Run per-user filtering → scorer → summariser
        ai_results = await score_and_summarise_papers(db, run)

        # Build embedding log message
        embed_message = None
        if embed_results.get("error"):
            embed_message = (
                f"Embedding failed: {embed_results['error']}. "
                f"{embed_results['skipped']} papers were not embedded and will use "
                f"keyword fallback for scoring."
            )
        elif embed_results["quota_exhausted"]:
            embed_message = (
                f"Gemini Embedding API daily limit (~1000 requests) reached. "
                f"{embed_results['skipped']} papers were not embedded and will use "
                f"keyword fallback for scoring. They will be embedded on the next "
                f"pipeline run when quota resets. No action needed unless this happens "
                f"regularly — consider reducing journal count or upgrading Gemini plan."
            )

        run.status = "success"
        run.completed_at = datetime.now(timezone.utc)
        run.run_log = [
            {"step": "discovery", "ieee": len(ieee_journals), "scopus": len(scopus_journals), "rss": len(rss_journals)},
            {"step": "raw_papers", "count": len(all_papers)},
            {"step": "dedup", "unique": len(unique_papers)},
            {"step": "saved", "count": saved_count},
            {"step": "embedding", "embedded": embed_results["embedded"], "skipped": embed_results["skipped"], "quota_exhausted": embed_results["quota_exhausted"], "message": embed_message or embed_results.get("debug")},
            {"step": "scoring", "scored": ai_results["scored"], "embedding_users": ai_results.get("embedding_users", 0), "keyword_fallback_users": ai_results.get("keyword_fallback_users", 0)},
            {"step": "prefilter", "passed": ai_results["prefiltered"]},
            {"step": "summarisation", "summarised": ai_results["summarised"]},
        ]
        await db.commit()

        summary = {
            "status": "success",
            "papers_discovered": len(all_papers),
            "papers_after_dedup": len(unique_papers),
            "papers_saved": saved_count,
            **ai_results,
        }
        logger.info(f"Pipeline complete: {summary}")
        return summary

    except BaseException as e:
        # BaseException catches CancelledError (raised by asyncio.wait_for on
        # timeout) in addition to regular exceptions.  Without this, a timeout
        # leaves PipelineRun.status stuck as "running" forever because
        # CancelledError is a BaseException, not an Exception in Python 3.9+.
        is_cancel = isinstance(e, (asyncio.CancelledError,))
        if is_cancel:
            logger.warning(f"Pipeline cancelled (likely timeout): {e}")
        else:
            logger.exception("Pipeline failed")
        run.status = "failed"
        run.error_message = (
            "Pipeline timed out (cancelled by scheduler)"
            if is_cancel
            else str(e)
        )
        run.completed_at = datetime.now(timezone.utc)
        try:
            await db.commit()
        except Exception:
            pass  # best-effort cleanup; session may be broken after cancel
        if is_cancel:
            raise  # re-raise so asyncio.wait_for translates to TimeoutError
        return {"status": "failed", "error": str(e)}
