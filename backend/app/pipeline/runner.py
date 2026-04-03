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
from app.services.ranking.scorer import score_paper_for_all_users
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


async def score_and_summarise_papers(
    db: AsyncSession,
    run: PipelineRun,
) -> dict[str, int]:
    """Run prefilter, scoring, and summarisation on unprocessed papers.

    Returns dict with counts.
    """
    # Get all papers that haven't been scored yet
    scored_paper_ids_q = select(PaperScore.paper_id).distinct()
    scored_ids_result = await db.execute(scored_paper_ids_q)
    scored_paper_ids = {row[0] for row in scored_ids_result.all()}

    all_papers_result = await db.execute(select(Paper))
    all_papers = all_papers_result.scalars().all()

    unscored = [p for p in all_papers if p.id not in scored_paper_ids]
    if not unscored:
        logger.info("No unscored papers to process")
        return {"prefiltered": 0, "scored": 0, "summarised": 0}

    # Convert to dicts for prefilter
    paper_dicts = [
        {
            "id": str(p.id),
            "title": p.title,
            "abstract": p.abstract or "",
            "authors": p.authors,
            "journal": p.journal,
            "keywords": p.keywords or [],
        }
        for p in unscored
    ]

    # Prefilter
    filtered = prefilter_papers(paper_dicts)
    logger.info(f"Prefilter: {len(filtered)}/{len(paper_dicts)} papers passed")

    # Get users for scoring
    users = await get_all_users(db)
    if not users:
        logger.warning("No users found, skipping scoring")
        return {"prefiltered": len(filtered), "scored": 0, "summarised": 0}

    scored_count = 0
    summarised_count = 0
    import json as json_module
    import asyncio as aio

    BATCH_SIZE = 5  # Process 5 papers concurrently

    async def _score_one(paper_dict: dict) -> tuple[dict, list[dict], float]:
        """Score a single paper for all users. Returns (paper_dict, scores, max_score)."""
        scores = await score_paper_for_all_users(paper_dict, users)
        max_score = max(s["score"] for s in scores) if scores else 0
        return paper_dict, scores, max_score

    async def _summarise_one(paper_dict: dict, paper_id: uuid.UUID) -> bool:
        """Generate summary for one paper. Returns True if successful."""
        summary = await generate_summary(paper_dict)
        if summary:
            paper_obj = await db.get(Paper, paper_id)
            if paper_obj:
                paper_obj.summary = json_module.dumps(summary)
                paper_obj.categories = summary.get("categories", [])
                paper_obj.summary_generated_at = datetime.now(timezone.utc)
                return True
        return False

    # Phase 1: Score all papers in batches
    papers_to_summarise = []
    for i in range(0, len(filtered), BATCH_SIZE):
        batch = filtered[i:i + BATCH_SIZE]
        results = await aio.gather(*[_score_one(p) for p in batch])

        for paper_dict, scores, max_score in results:
            paper_id = uuid.UUID(paper_dict["id"])
            await save_scores(db, paper_id, scores)
            scored_count += 1
            if max_score >= 5.0:
                papers_to_summarise.append((paper_dict, paper_id))
            logger.info(f"Scored paper {scored_count}/{len(filtered)}: max_score={max_score:.1f}")

    await db.commit()

    # Phase 2: Summarise qualifying papers in batches
    for i in range(0, len(papers_to_summarise), BATCH_SIZE):
        batch = papers_to_summarise[i:i + BATCH_SIZE]
        results = await aio.gather(*[_summarise_one(pd, pid) for pd, pid in batch])
        summarised_count += sum(1 for r in results if r)
        await db.commit()
        logger.info(f"Summarised batch {i // BATCH_SIZE + 1}: {sum(1 for r in results if r)}/{len(batch)}")

    return {"prefiltered": len(filtered), "scored": scored_count, "summarised": summarised_count}


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

        # Run prefilter → scorer → summariser
        ai_results = await score_and_summarise_papers(db, run)

        run.status = "success"
        run.completed_at = datetime.now(timezone.utc)
        run.run_log = [
            {"step": "discovery", "ieee": len(ieee_journals), "scopus": len(scopus_journals), "rss": len(rss_journals)},
            {"step": "raw_papers", "count": len(all_papers)},
            {"step": "dedup", "unique": len(unique_papers)},
            {"step": "saved", "count": saved_count},
            {"step": "prefilter", "passed": ai_results["prefiltered"]},
            {"step": "scoring", "scored": ai_results["scored"]},
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
