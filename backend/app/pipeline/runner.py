import logging
import uuid
from datetime import datetime, timezone
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
            "interest_vector": u.interest_vector or {},
            "scoring_prompt": u.scoring_prompt,
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
    result = await db.execute(
        select(Paper).where(Paper.embedding.is_(None))
    )
    papers = result.scalars().all()

    if not papers:
        logger.info("No unembedded papers to process")
        return {"embedded": 0, "skipped": 0, "quota_exhausted": False}

    texts = [prepare_paper_text(p.title, p.abstract or "") for p in papers]
    embeddings = await embed_texts(texts)

    embedded = 0
    skipped = 0
    quota_exhausted = False

    for paper, embedding in zip(papers, embeddings):
        if embedding is not None:
            paper.embedding = embedding
            embedded += 1
        else:
            skipped += 1
            quota_exhausted = True  # None means quota/rate issue

    await db.commit()

    if quota_exhausted:
        logger.warning(
            f"Embedding quota issue: {embedded} embedded, {skipped} skipped. "
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

    SIMILARITY_THRESHOLD = 0.35

    # Per-user filtering: embedding similarity if available, keyword fallback otherwise
    # Build a map of user_id -> papers to score for that user (excluding already-scored pairs)
    user_papers_map: dict[str, list[dict]] = {}
    keyword_fallback_count = 0
    embedding_filter_count = 0

    # Keyword-filtered papers (computed once, used as fallback)
    keyword_filtered = prefilter_papers(paper_dicts)
    keyword_filtered_ids = {p["id"] for p in keyword_filtered}

    for user in users:
        uid = uuid.UUID(user["id"])
        profile_embedding = user.get("interest_vector")
        # interest_vector is a list when populated, empty dict {} when not
        has_profile = isinstance(profile_embedding, list) and len(profile_embedding) > 0

        # Only include papers this user hasn't scored yet
        user_unscored = [pd for pd in paper_dicts if (uuid.UUID(pd["id"]), uid) not in existing_score_pairs]
        if not user_unscored:
            continue

        if has_profile:
            # Embedding-based per-user filter
            matched = []
            for pd in user_unscored:
                paper_emb = pd.get("embedding")
                if isinstance(paper_emb, list) and len(paper_emb) > 0:
                    sim = cosine_similarity(profile_embedding, paper_emb)
                    if sim >= SIMILARITY_THRESHOLD:
                        pd_copy = {**pd, "cosine_similarity": round(sim, 4)}
                        matched.append(pd_copy)
                elif pd["id"] in keyword_filtered_ids:
                    # Paper has no embedding — fall back to keyword match
                    matched.append(pd)
            user_papers_map[user["id"]] = matched
            embedding_filter_count += 1
        else:
            # No profile embedding — use keyword fallback (only unscored papers)
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

    from google import genai as _genai
    from app.config import get_settings as _get_settings
    _settings = _get_settings()
    _client = _genai.Client(api_key=_settings.gemini_api_key)

    for user in users:
        user_papers = user_papers_map.get(user["id"], [])
        if not user_papers:
            continue

        for i in range(0, len(user_papers), BATCH_SIZE):
            batch = user_papers[i:i + BATCH_SIZE]

            async def _score(pd: dict, u: dict = user) -> tuple[str, dict]:
                result = await score_paper_for_user(pd, u, _client, u.get("scoring_prompt"))
                return pd["id"], {"user_id": u["id"], "score": result["score"], "reasoning": result["reasoning"]}

            results = await aio.gather(*[_score(pd) for pd in batch])

            for paper_id_str, score_data in results:
                all_scores.setdefault(paper_id_str, []).append(score_data)
                scored_count += 1

    # Save all scores and determine which papers to summarise
    papers_to_summarise = []
    paper_dict_map = {pd["id"]: pd for pd in paper_dicts}

    for paper_id_str, scores in all_scores.items():
        paper_id = uuid.UUID(paper_id_str)
        await save_scores(db, paper_id, scores)
        max_score = max(s["score"] for s in scores) if scores else 0
        if max_score >= 5.0:
            papers_to_summarise.append((paper_dict_map[paper_id_str], paper_id))
        logger.info(f"Saved scores for paper {paper_id_str[:8]}...: max_score={max_score:.1f}")

    await db.commit()

    total_papers_with_scores = len(all_scores)
    logger.info(f"Scored {scored_count} (paper, user) pairs across {total_papers_with_scores} papers")

    # Phase 2: Summarise qualifying papers in batches
    async def _summarise_one(paper_dict: dict, paper_id: uuid.UUID) -> bool:
        summary = await generate_summary(paper_dict)
        if summary:
            paper_obj = await db.get(Paper, paper_id)
            if paper_obj:
                paper_obj.summary = json_module.dumps(summary)
                paper_obj.categories = summary.get("categories", [])
                paper_obj.summary_generated_at = datetime.now(timezone.utc)
                return True
        return False

    for i in range(0, len(papers_to_summarise), BATCH_SIZE):
        batch = papers_to_summarise[i:i + BATCH_SIZE]
        results = await aio.gather(*[_summarise_one(pd, pid) for pd, pid in batch])
        summarised_count += sum(1 for r in results if r)
        await db.commit()
        logger.info(f"Summarised batch {i // BATCH_SIZE + 1}: {sum(1 for r in results if r)}/{len(batch)}")

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

        # Deduplicate
        existing_dois = await get_existing_dois(db)
        unique_papers = deduplicate_papers(all_papers, existing_dois)
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
        if embed_results["quota_exhausted"]:
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
            {"step": "embedding", "embedded": embed_results["embedded"], "skipped": embed_results["skipped"], "quota_exhausted": embed_results["quota_exhausted"], "message": embed_message},
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

    except Exception as e:
        logger.exception("Pipeline failed")
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "failed", "error": str(e)}
