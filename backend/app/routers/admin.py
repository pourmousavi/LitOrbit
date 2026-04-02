import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
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
