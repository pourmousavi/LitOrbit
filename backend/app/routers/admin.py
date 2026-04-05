import logging
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import get_settings
from app.database import get_db
from app.models.journal_config import JournalConfig
from app.models.pipeline_run import PipelineRun
from app.models.user_profile import UserProfile

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

    # Create user in Supabase Auth via Admin API (sends invite email automatically)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/auth/v1/admin/generate_link",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
                "Content-Type": "application/json",
            },
            json={
                "type": "invite",
                "email": req.email,
                "data": {"full_name": req.full_name},
            },
        )

    if resp.status_code not in (200, 201):
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        logger.error(f"Supabase invite failed: {resp.status_code} {detail}")
        raise HTTPException(status_code=502, detail=f"Failed to create auth user: {resp.status_code}")

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

    # Send the invite email via Resend/SMTP
    action_link = auth_data.get("action_link")
    if action_link:
        try:
            await _send_invite_email(req.email, req.full_name, action_link, settings)
        except Exception as e:
            logger.warning(f"Failed to send invite email to {req.email}: {e}")

    return {"id": user_id, "status": "invited", "email": req.email}


async def _send_invite_email(email: str, full_name: str, action_link: str, settings: Any) -> None:
    """Send an invite email with the Supabase magic link."""
    subject = "You're invited to LitOrbit"
    html = f"""
    <div style="font-family: monospace; max-width: 500px; margin: 0 auto; padding: 40px 20px;">
        <h2 style="margin-bottom: 24px;">Welcome to LitOrbit</h2>
        <p>Hi {full_name},</p>
        <p>You've been invited to join LitOrbit, a research intelligence platform.</p>
        <p>Click the link below to set your password and get started:</p>
        <p style="margin: 24px 0;">
            <a href="{action_link}" style="background: #6366f1; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; display: inline-block;">
                Accept Invitation
            </a>
        </p>
        <p style="color: #888; font-size: 12px;">This link will expire in 24 hours.</p>
    </div>
    """

    if settings.resend_api_key:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from,
                    "to": [email],
                    "subject": subject,
                    "html": html,
                },
            )
    elif settings.smtp_user and settings.smtp_password:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
        msg["To"] = email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, email, msg.as_string())


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

    # Delete from Supabase Auth
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(
            f"{settings.supabase_url}/auth/v1/admin/users/{user_id}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
            },
        )
    if resp.status_code not in (200, 204):
        logger.warning(f"Failed to delete auth user {user_id}: {resp.status_code}")

    # Delete from user_profiles
    await db.delete(profile)
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
                results = await run_digests(
                    session,
                    frequency=req.frequency,
                    skip_day_check=True,
                )
                logger.info(f"Manual digest run: {results}")
        except Exception as e:
            logger.exception(f"Manual digest run failed: {e}")

    background_tasks.add_task(_run)
    return {"status": "triggered", "frequency": req.frequency or "all"}


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
