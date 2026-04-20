import logging
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import get_settings
from app.database import get_db
from app.models.journal_config import JournalConfig
from app.models.pipeline_run import PipelineRun
from app.models.user_profile import UserProfile
from app.services.settings import get_system_settings

logger = logging.getLogger(__name__)

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
    publisher: str | None = None
    source_type: str | None = None
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
    if req.publisher is not None:
        journal.publisher = req.publisher
    if req.source_type is not None:
        journal.source_type = req.source_type
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


# --- User Management ---

class UserInvite(BaseModel):
    email: str
    full_name: str
    role: str = "researcher"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None


@router.post("/users/invite")
async def invite_user(
    req: UserInvite,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Invite a new user: creates Supabase Auth user + user_profiles row atomically."""
    settings = get_settings()

    if req.role not in ("admin", "researcher"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'researcher'")

    # Check if email already exists in user_profiles
    existing = await db.execute(
        select(UserProfile).where(UserProfile.email == req.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    # Create user in Supabase Auth via invite (Supabase sends the email)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/auth/v1/invite",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
                "Content-Type": "application/json",
            },
            json={
                "email": req.email,
                "data": {"full_name": req.full_name},
            },
        )

    if resp.status_code not in (200, 201):
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        logger.error(f"Supabase invite failed: {resp.status_code} {detail}")
        raise HTTPException(status_code=502, detail=f"Failed to invite user: {resp.status_code}")

    auth_data = resp.json()
    user_id = auth_data.get("id")
    if not user_id:
        raise HTTPException(status_code=502, detail="Supabase did not return a user ID")

    # Create matching user_profiles row
    profile = UserProfile(
        id=uuid.UUID(user_id),
        full_name=req.full_name,
        email=req.email,
        role=req.role,
    )
    db.add(profile)
    await db.commit()

    return {"id": user_id, "status": "invited", "email": req.email}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    req: UserUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a user's profile (name, role)."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == uuid.UUID(user_id))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    if req.full_name is not None:
        profile.full_name = req.full_name
    if req.role is not None:
        if req.role not in ("admin", "researcher"):
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'researcher'")
        profile.role = req.role

    await db.commit()
    return {"status": "updated"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a user from both user_profiles and Supabase Auth."""
    if admin["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(
        select(UserProfile).where(UserProfile.id == uuid.UUID(user_id))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete from user_profiles FIRST (FK constraint: auth.users referenced by user_profiles)
    await db.delete(profile)
    await db.commit()

    # Then delete from Supabase Auth
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.delete(
            f"{settings.supabase_url}/auth/v1/admin/users/{user_id}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
            },
        )
        if resp.status_code not in (200, 204, 404):
            logger.warning(f"Profile deleted but auth user cleanup failed for {user_id}: {resp.status_code}")

    return {"status": "deleted"}


# --- System Settings ---

class SystemSettingsUpdate(BaseModel):
    max_podcasts_per_user_per_month: int | None = None
    digest_podcast_enabled_global: bool | None = None
    max_papers_per_digest: int | None = None
    max_podcast_duration_minutes: int | None = None


@router.get("/settings")
async def get_settings_endpoint(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get current system settings (usage limits)."""
    s = await get_system_settings(db)
    return {
        "max_podcasts_per_user_per_month": s.max_podcasts_per_user_per_month,
        "digest_podcast_enabled_global": s.digest_podcast_enabled_global,
        "max_papers_per_digest": s.max_papers_per_digest,
        "max_podcast_duration_minutes": s.max_podcast_duration_minutes,
    }


@router.put("/settings")
async def update_settings_endpoint(
    req: SystemSettingsUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update system settings (usage limits)."""
    s = await get_system_settings(db)
    if req.max_podcasts_per_user_per_month is not None:
        s.max_podcasts_per_user_per_month = max(0, req.max_podcasts_per_user_per_month)
    if req.digest_podcast_enabled_global is not None:
        s.digest_podcast_enabled_global = req.digest_podcast_enabled_global
    if req.max_papers_per_digest is not None:
        s.max_papers_per_digest = max(1, req.max_papers_per_digest)
    if req.max_podcast_duration_minutes is not None:
        s.max_podcast_duration_minutes = max(1, min(60, req.max_podcast_duration_minutes))
    await db.commit()
    return {"status": "updated"}


# --- Thresholds ---

class ThresholdsUpdate(BaseModel):
    similarity_threshold: float = Field(ge=0.0, le=1.0)
    negative_anchor_lambda: float = Field(ge=0.0, le=2.0)


@router.get("/thresholds")
async def get_thresholds(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get current similarity threshold and negative anchor lambda."""
    s = await get_system_settings(db)
    return {
        "similarity_threshold": s.similarity_threshold,
        "negative_anchor_lambda": s.negative_anchor_lambda,
    }


@router.put("/thresholds")
async def update_thresholds(
    req: ThresholdsUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update similarity threshold and negative anchor lambda."""
    s = await get_system_settings(db)
    s.similarity_threshold = req.similarity_threshold
    s.negative_anchor_lambda = req.negative_anchor_lambda
    await db.commit()
    return {"status": "updated"}


# --- User Stats ---

@router.get("/users/stats")
async def get_user_stats(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all users with activity stats."""
    from app.models.rating import Rating
    from app.models.podcast import Podcast
    from app.models.collection import Collection
    from app.models.share import Share
    from app.models.digest_log import DigestLog

    # Correlated subqueries for each stat
    ratings_sq = (
        select(func.count()).where(Rating.user_id == UserProfile.id)
        .correlate(UserProfile).scalar_subquery()
    )
    podcasts_sq = (
        select(func.count()).where(Podcast.user_id == UserProfile.id, Podcast.audio_path.isnot(None))
        .correlate(UserProfile).scalar_subquery()
    )
    listens_sq = (
        select(func.coalesce(func.sum(Podcast.listen_count), 0))
        .where(Podcast.user_id == UserProfile.id)
        .correlate(UserProfile).scalar_subquery()
    )
    collections_sq = (
        select(func.count()).where(Collection.created_by == UserProfile.id)
        .correlate(UserProfile).scalar_subquery()
    )
    shares_sq = (
        select(func.count()).where(Share.shared_by == UserProfile.id)
        .correlate(UserProfile).scalar_subquery()
    )
    digests_sq = (
        select(func.count(func.distinct(func.date(DigestLog.sent_at))))
        .where(DigestLog.user_id == UserProfile.id)
        .correlate(UserProfile).scalar_subquery()
    )
    last_rating_sq = (
        select(func.max(Rating.rated_at)).where(Rating.user_id == UserProfile.id)
        .correlate(UserProfile).scalar_subquery()
    )
    last_podcast_sq = (
        select(func.max(Podcast.generated_at)).where(Podcast.user_id == UserProfile.id)
        .correlate(UserProfile).scalar_subquery()
    )

    result = await db.execute(
        select(
            UserProfile,
            ratings_sq.label("ratings_count"),
            podcasts_sq.label("podcasts_generated"),
            listens_sq.label("podcasts_listened"),
            collections_sq.label("collections_count"),
            shares_sq.label("shares_sent"),
            digests_sq.label("digests_received"),
            last_rating_sq.label("last_rating_at"),
            last_podcast_sq.label("last_podcast_at"),
        ).order_by(UserProfile.full_name)
    )
    rows = result.all()

    users = []
    for row in rows:
        u = row[0]
        last_rating = row.last_rating_at
        last_podcast = row.last_podcast_at
        last_active = None
        if last_rating and last_podcast:
            last_active = max(last_rating, last_podcast)
        elif last_rating:
            last_active = last_rating
        elif last_podcast:
            last_active = last_podcast

        users.append({
            "id": str(u.id),
            "full_name": u.full_name,
            "role": u.role,
            "email": u.email,
            "invited_at": u.created_at.isoformat() if u.created_at else None,
            "accepted_at": u.accepted_at.isoformat() if u.accepted_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "login_count": u.login_count or 0,
            "ratings_count": row.ratings_count or 0,
            "podcasts_generated": row.podcasts_generated or 0,
            "podcasts_listened": row.podcasts_listened or 0,
            "collections_count": row.collections_count or 0,
            "shares_sent": row.shares_sent or 0,
            "digests_received": row.digests_received or 0,
            "last_active": last_active.isoformat() if last_active else None,
        })
    return users


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


@router.post("/pipeline/run-scheduled")
async def run_scheduled_pipeline(
    x_pipeline_secret: str | None = Header(default=None),
) -> dict:
    """Header-secret-auth endpoint for external schedulers (e.g. GitHub Actions
    cron) to trigger the full daily run: discovery pipeline + digest emails.

    Authenticates via the ``X-Pipeline-Secret`` header against the
    ``PIPELINE_TRIGGER_SECRET`` env var. Runs synchronously so the process
    stays alive until all work completes (prevents Render free-tier shutdown).
    """
    settings = get_settings()
    expected = settings.pipeline_trigger_secret
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Pipeline trigger secret not configured on server",
        )
    if not x_pipeline_secret or x_pipeline_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid pipeline secret")

    import asyncio

    from app import database as db_module
    from app.pipeline.runner import run_discovery_pipeline
    from app.services.digest_runner import run_digests

    if db_module.async_session_factory is None:
        db_module.init_db()
    if db_module.async_session_factory is None:
        raise HTTPException(status_code=503, detail="No DB session factory")

    # The pipeline includes discovery (~2 min), embedding (~2 min), and
    # scoring + summarisation.  Scoring is rate-limited to 9 RPM by Gemini's
    # free tier, so 170 papers × N users can legitimately take 30-40 min.
    # A tight timeout here just cancels the scoring mid-flight, leaving
    # papers unscored and PipelineRun stuck.  Give it a generous budget;
    # curl --max-time in the GitHub Actions workflow is the outer guard.
    PIPELINE_TIMEOUT = 2700  # 45 minutes for discovery + scoring
    DIGEST_TIMEOUT = 900     # 15 minutes for digests (TTS generation can be slow)

    # --- 1. Run discovery pipeline ---
    pipeline_result = {}
    try:
        async with db_module.async_session_factory() as session:
            pipeline_result = await asyncio.wait_for(
                run_discovery_pipeline(session),
                timeout=PIPELINE_TIMEOUT,
            )
            logger.info(f"Scheduled pipeline run: {pipeline_result}")
    except TimeoutError:
        logger.error(f"Scheduled pipeline timed out after {PIPELINE_TIMEOUT}s")
        pipeline_result = {"status": "failed", "error": f"Pipeline timed out after {PIPELINE_TIMEOUT}s"}
    except Exception as e:
        logger.exception(f"Scheduled pipeline failed: {e}")
        pipeline_result = {"status": "failed", "error": str(e)}

    # --- 2. Always run digests (independent of pipeline outcome) ---
    digest_summary = {}
    try:
        async with db_module.async_session_factory() as session:
            digest_results = await asyncio.wait_for(
                run_digests(session),
                timeout=DIGEST_TIMEOUT,
            )
            sent = sum(1 for r in digest_results if r.get("sent"))
            logger.info(f"Scheduled digest: {sent}/{len(digest_results)} emails sent")
            digest_summary = {"sent": sent, "total": len(digest_results)}
    except TimeoutError:
        logger.error(f"Scheduled digest timed out after {DIGEST_TIMEOUT}s")
        digest_summary = {"error": f"Digest timed out after {DIGEST_TIMEOUT}s"}
    except Exception as e:
        logger.exception(f"Scheduled digest failed: {e}")
        digest_summary = {"error": str(e)}

    return {
        "pipeline": pipeline_result,
        "digest": digest_summary,
    }


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
    if run.status == "deleted":
        raise HTTPException(status_code=400, detail="This batch has already been deleted")
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

    # Collect DOIs and titles to clear from deleted_papers too,
    # so these papers can be re-fetched by future pipeline runs.
    dois_to_clear = [p.doi for p in papers if p.doi]
    titles_to_clear = [p.title.lower().strip() for p in papers if p.title]

    for p in papers:
        await db.delete(p)

    # Also remove from deleted_papers so dedup won't block re-fetch
    if dois_to_clear:
        await db.execute(
            DeletedPaper.__table__.delete().where(DeletedPaper.doi.in_(dois_to_clear))
        )
    if titles_to_clear:
        await db.execute(
            DeletedPaper.__table__.delete().where(
                func.lower(func.trim(DeletedPaper.title)).in_(titles_to_clear)
            )
        )

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
    if run.status == "deleted":
        raise HTTPException(status_code=400, detail="Cannot re-score a deleted batch")
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


# --- Knowledge base stats ---

@router.get("/kb-stats")
async def get_kb_stats(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get knowledge base statistics."""
    from app.models.paper import Paper
    from app.models.paper_score import PaperScore

    total_papers = (await db.execute(select(func.count()).select_from(Paper))).scalar()
    scored_papers = (await db.execute(
        select(func.count(func.distinct(PaperScore.paper_id)))
    )).scalar()
    total_runs = (await db.execute(
        select(func.count()).select_from(PipelineRun)
    )).scalar()
    successful_runs = (await db.execute(
        select(func.count()).select_from(PipelineRun).where(PipelineRun.status == "success")
    )).scalar()
    latest_run = (await db.execute(
        select(PipelineRun.completed_at)
        .where(PipelineRun.status == "success")
        .order_by(PipelineRun.completed_at.desc())
        .limit(1)
    )).scalar()

    return {
        "total_papers": total_papers,
        "scored_papers": scored_papers,
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "last_fetch": latest_run.isoformat() if latest_run else None,
    }


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
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict:
    settings = await get_system_settings(db)
    keywords = settings.platform_keywords
    if not keywords:
        # First-run fallback before migration seed has populated the row
        from app.services.ranking.prefilter import MASTER_KEYWORDS
        keywords = MASTER_KEYWORDS
    return {"keywords": keywords}


@router.put("/keywords")
async def update_keywords(
    req: KeywordsUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict:
    settings = await get_system_settings(db)
    settings.platform_keywords = req.keywords
    await db.commit()
    return {"status": "updated", "count": len(req.keywords)}


# --- Digest ---

class DigestTrigger(BaseModel):
    frequency: str | None = None  # "daily" | "weekly" | None (both)
    product: str = "all"  # "email" | "podcast" | "all"


@router.post("/digest/trigger")
async def trigger_digest(
    req: DigestTrigger,
    background_tasks: BackgroundTasks,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict:
    """Manually trigger digests for all eligible users."""

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
                results = await run_digests(
                    session,
                    frequency=req.frequency,
                    skip_day_check=True,
                    product=req.product,
                )
                logger.info(f"Manual digest run: {results}")
        except Exception as e:
            logger.exception(f"Manual digest run failed: {e}")

    background_tasks.add_task(_run)
    return {"status": "triggered", "frequency": req.frequency or "all", "product": req.product}


@router.get("/digest/runs")
async def list_digest_runs(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List recent digest runs with status and progress."""
    from app.models.digest_run import DigestRun

    result = await db.execute(
        select(DigestRun).order_by(DigestRun.started_at.desc()).limit(20)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "frequency": r.frequency,
            "run_type": getattr(r, "run_type", "email"),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "status": r.status,
            "users_total": r.users_total,
            "users_sent": r.users_sent,
            "users_skipped": r.users_skipped,
            "users_failed": r.users_failed,
            "error_message": r.error_message,
            "run_log": r.run_log,
        }
        for r in runs
    ]


# --- Embedding Alerts & Backfill ---

@router.get("/alerts")
async def get_alerts(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return active system alerts (embedding quota, unembedded papers, etc.)."""
    from app.models.paper import Paper
    from app.services.ranking.embedder import get_quota_status

    alerts = []

    # 1. Count unembedded papers
    from sqlalchemy import or_
    unembedded_result = await db.execute(
        select(func.count()).select_from(Paper).where(
            or_(Paper.embedding.is_(None), Paper.embedding == {}, Paper.embedding == [])
        )
    )
    unembedded_count = unembedded_result.scalar() or 0

    # 2. Only show embedding error/quota alerts if papers still need embeddings
    if unembedded_count > 0:
        # Check latest pipeline run for embedding issues
        latest_run = await db.execute(
            select(PipelineRun)
            .where(PipelineRun.status == "success")
            .order_by(PipelineRun.started_at.desc())
            .limit(1)
        )
        run_obj = latest_run.scalar_one_or_none()
        if run_obj and run_obj.run_log:
            for step in run_obj.run_log:
                if isinstance(step, dict) and step.get("step") == "embedding" and step.get("message"):
                    is_quota = step.get("quota_exhausted", False)
                    alerts.append({
                        "severity": "warning",
                        "title": "Embedding Quota Exhausted" if is_quota else "Embedding Error",
                        "message": step["message"],
                        "action": "backfill-embeddings",
                        "run_id": str(run_obj.id),
                        "run_at": run_obj.started_at.isoformat() if run_obj.started_at else None,
                    })
                    break

        alerts.append({
            "severity": "info",
            "title": "Papers Without Embeddings",
            "message": (
                f"{unembedded_count} paper(s) lack semantic embeddings. These papers use "
                f"keyword fallback for relevance scoring, which is less accurate. "
                f"Run backfill to generate embeddings, or they will be embedded on "
                f"the next pipeline run."
            ),
            "action": "backfill-embeddings",
            "count": unembedded_count,
        })

    # 3. Current quota status
    quota = get_quota_status()
    if quota["daily_remaining"] < 100:
        alerts.append({
            "severity": "info",
            "title": "Embedding Quota Running Low",
            "message": (
                f"{quota['daily_remaining']} embedding requests remaining today "
                f"(used {quota['daily_used']}/{quota['daily_limit']}). "
                f"Quota resets at midnight."
            ),
        })

    return alerts


@router.post("/backfill-embeddings")
async def backfill_embeddings(
    background_tasks: BackgroundTasks,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict:
    """Trigger embedding backfill for papers missing embeddings."""

    async def _run():
        from app.database import init_db, async_session_factory
        from app.pipeline.runner import embed_unembedded_papers
        import logging
        _logger = logging.getLogger(__name__)

        try:
            if async_session_factory is None:
                init_db()
            if async_session_factory is None:
                return
            async with async_session_factory() as session:
                result = await embed_unembedded_papers(session)
                _logger.info(f"Backfill embeddings: {result}")
        except Exception as e:
            _logger.exception(f"Backfill embeddings failed: {e}")

    background_tasks.add_task(_run)
    return {"status": "triggered"}
