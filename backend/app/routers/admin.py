import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models.journal_config import JournalConfig
from app.models.pipeline_run import PipelineRun

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# --- Journal Config ---

class JournalCreate(BaseModel):
    name: str
    publisher: str
    source_type: str
    source_identifier: str
    is_active: bool = True


class JournalUpdate(BaseModel):
    name: str | None = None
    source_identifier: str | None = None
    is_active: bool | None = None


@router.get("/journals")
async def list_journals(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(select(JournalConfig).order_by(JournalConfig.name))
    journals = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "name": j.name,
            "publisher": j.publisher,
            "source_type": j.source_type,
            "source_identifier": j.source_identifier,
            "is_active": j.is_active,
        }
        for j in journals
    ]


@router.post("/journals")
async def add_journal(
    req: JournalCreate,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    journal = JournalConfig(
        id=uuid.uuid4(),
        name=req.name,
        publisher=req.publisher,
        source_type=req.source_type,
        source_identifier=req.source_identifier,
        is_active=req.is_active,
    )
    db.add(journal)
    await db.commit()
    return {"id": str(journal.id), "status": "created"}


@router.patch("/journals/{journal_id}")
async def update_journal(
    journal_id: str,
    req: JournalUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(JournalConfig).where(JournalConfig.id == uuid.UUID(journal_id)))
    journal = result.scalar_one_or_none()
    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found")

    if req.name is not None:
        journal.name = req.name
    if req.source_identifier is not None:
        journal.source_identifier = req.source_identifier
    if req.is_active is not None:
        journal.is_active = req.is_active

    await db.commit()
    return {"status": "updated"}


@router.delete("/journals/{journal_id}")
async def delete_journal(
    journal_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(JournalConfig).where(JournalConfig.id == uuid.UUID(journal_id)))
    journal = result.scalar_one_or_none()
    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found")
    await db.delete(journal)
    await db.commit()
    return {"status": "deleted"}


# --- Pipeline ---

@router.get("/pipeline/runs")
async def list_pipeline_runs(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(50)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "status": r.status,
            "papers_discovered": r.papers_discovered,
            "papers_filtered": r.papers_filtered,
            "papers_processed": r.papers_processed,
            "error_message": r.error_message,
            "run_log": r.run_log,
        }
        for r in runs
    ]


@router.post("/pipeline/trigger")
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a manual pipeline run."""
    async def _run():
        from app.database import init_db, async_session_factory
        from app.pipeline.runner import run_discovery_pipeline
        import logging
        logger = logging.getLogger(__name__)

        try:
            if async_session_factory is None:
                init_db()
            if async_session_factory is None:
                return
            async with async_session_factory() as session:
                result = await run_discovery_pipeline(session)
                logger.info(f"Manual pipeline run: {result}")
        except Exception as e:
            logger.exception(f"Manual pipeline run failed: {e}")

    background_tasks.add_task(_run)
    return {"status": "triggered"}


# --- Delete batch ---

@router.delete("/pipeline/runs/{run_id}/papers")
async def delete_run_papers(
    run_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete all papers from a specific pipeline run."""
    from app.models.paper import Paper

    result = await db.execute(select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id)))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.started_at:
        raise HTTPException(status_code=400, detail="Run has no start time")

    end_time = run.completed_at or run.started_at
    paper_result = await db.execute(
        select(Paper).where(
            Paper.created_at >= run.started_at,
            Paper.created_at <= end_time,
        )
    )
    from app.models.deleted_paper import DeletedPaper

    papers = paper_result.scalars().all()
    count = len(papers)
    for p in papers:
        db.add(DeletedPaper(id=uuid.uuid4(), doi=p.doi, title=p.title))
        await db.delete(p)
    # Mark run as deleted
    run.status = "deleted"
    run.error_message = f"{count} papers deleted"
    await db.commit()
    return {"status": "deleted", "papers_deleted": count}


# --- Re-score ---

@router.post("/rescore/{run_id}")
async def rescore_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-score papers from a specific pipeline run."""
    from sqlalchemy import delete
    from app.models.paper import Paper
    from app.models.paper_score import PaperScore

    # Get the run to find its time window
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id)))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.started_at:
        raise HTTPException(status_code=400, detail="Run has no start time")

    # Find papers created during this run's window
    end_time = run.completed_at or run.started_at
    paper_ids_result = await db.execute(
        select(Paper.id).where(
            Paper.created_at >= run.started_at,
            Paper.created_at <= end_time,
        )
    )
    paper_ids = [row[0] for row in paper_ids_result.all()]

    if not paper_ids:
        return {"status": "no_papers", "message": "No papers found for this run"}

    # Delete existing scores for these papers
    count = 0
    for pid in paper_ids:
        del_result = await db.execute(delete(PaperScore).where(PaperScore.paper_id == pid))
        count += del_result.rowcount
    await db.commit()

    async def _run():
        from app.database import init_db, async_session_factory
        from app.pipeline.runner import score_and_summarise_papers
        import logging
        logger = logging.getLogger(__name__)
        try:
            if async_session_factory is None:
                init_db()
            async with async_session_factory() as session:
                result = await score_and_summarise_papers(session, run)
                logger.info(f"Re-score for run {run_id} complete: {result}")
        except Exception as e:
            logger.exception(f"Re-score for run {run_id} failed: {e}")

    background_tasks.add_task(_run)
    return {"status": "triggered", "papers_count": len(paper_ids), "scores_deleted": count}


# --- Storage usage ---

@router.get("/storage-usage")
async def get_storage_usage(
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict:
    """Get Supabase Storage usage for the podcasts bucket."""
    import httpx
    from app.config import get_settings
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.supabase_url}/storage/v1/object/list/podcasts",
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "apikey": settings.supabase_service_role_key,
                    "Content-Type": "application/json",
                },
                json={"prefix": "", "limit": 1000},
            )
        if resp.status_code != 200:
            return {"used_bytes": 0, "used_mb": 0, "limit_mb": 1000, "file_count": 0}

        files = resp.json()
        total_bytes = sum(f.get("metadata", {}).get("size", 0) for f in files if isinstance(f, dict))
        return {
            "used_bytes": total_bytes,
            "used_mb": round(total_bytes / (1024 * 1024), 1),
            "limit_mb": 1000,
            "file_count": len(files),
            "warning": total_bytes > 800 * 1024 * 1024,  # Warn at 80%
        }
    except Exception:
        return {"used_bytes": 0, "used_mb": 0, "limit_mb": 1000, "file_count": 0}


# --- Global Keywords ---

class KeywordsUpdate(BaseModel):
    keywords: list[str]


@router.get("/keywords")
async def get_keywords(
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict:
    from app.services.ranking.prefilter import MASTER_KEYWORDS
    return {"keywords": MASTER_KEYWORDS}


@router.put("/keywords")
async def update_keywords(
    req: KeywordsUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict:
    from app.services.ranking import prefilter
    prefilter.MASTER_KEYWORDS = req.keywords
    return {"status": "updated", "count": len(req.keywords)}


# --- Digest ---

class DigestTrigger(BaseModel):
    frequency: str | None = None  # "daily" | "weekly" | None (both)


@router.post("/digest/trigger")
async def trigger_digest(
    req: DigestTrigger,
    background_tasks: BackgroundTasks,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict:
    """Manually trigger digest emails for all eligible users."""

    async def _run():
        from app.database import init_db, async_session_factory
        from app.services.digest_runner import run_digests
        import logging
        logger = logging.getLogger(__name__)

        try:
            if async_session_factory is None:
                init_db()
            if async_session_factory is None:
                return
            async with async_session_factory() as session:
                results = run_digests(session, frequency=req.frequency)
                # run_digests is async
                import asyncio
                if asyncio.iscoroutine(results):
                    results = await results
                logger.info(f"Manual digest run: {results}")
        except Exception as e:
            logger.exception(f"Manual digest run failed: {e}")

    background_tasks.add_task(_run)
    return {"status": "triggered", "frequency": req.frequency or "all"}
