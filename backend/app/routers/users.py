import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models.user_profile import UserProfile
from app.services.settings import get_system_settings

_FEED_FIELDS = (
    "podcast_feed_enabled",
    "podcast_feed_token",
    "podcast_feed_title",
    "podcast_feed_description",
    "podcast_feed_author",
    "podcast_feed_cover_url",
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class ProfileUpdate(BaseModel):
    interest_keywords: list[str] | None = None
    interest_categories: list[str] | None = None
    podcast_preference: str | None = None
    email_digest_enabled: bool | None = None
    digest_frequency: str | None = None
    digest_day: str | None = None
    digest_podcast_enabled: bool | None = None
    digest_podcast_voice_mode: str | None = None
    digest_top_papers: int | None = None
    podcast_digest_enabled: bool | None = None
    podcast_digest_frequency: str | None = None
    podcast_digest_day: str | None = None
    podcast_digest_top_papers: int | None = None
    podcast_digest_voice_mode: str | None = None
    scoring_prompt: str | None = None
    single_voice_prompt: str | None = None
    dual_voice_prompt: str | None = None
    single_voice_id: str | None = None
    dual_voice_alex_id: str | None = None
    dual_voice_sam_id: str | None = None
    podcast_feed_enabled: bool | None = None
    podcast_feed_title: str | None = None
    podcast_feed_description: str | None = None
    podcast_feed_author: str | None = None
    podcast_feed_cover_url: str | None = None


@router.get("/limits")
async def get_user_limits(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get system-level limits relevant to the current user."""
    s = await get_system_settings(db)
    return {
        "max_papers_per_digest": s.max_papers_per_digest,
        "max_podcasts_per_user_per_month": s.max_podcasts_per_user_per_month,
    }


@router.get("/me")
async def get_my_profile(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the current user's profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == uuid.UUID(user["id"]))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "id": str(profile.id),
        "full_name": profile.full_name,
        "role": profile.role,
        "email": profile.email,
        "interest_keywords": profile.interest_keywords,
        "interest_categories": profile.interest_categories,
        "interest_vector": profile.interest_vector,
        "category_weights": profile.category_weights,
        "podcast_preference": profile.podcast_preference,
        "email_digest_enabled": profile.email_digest_enabled,
        "digest_frequency": profile.digest_frequency,
        "digest_day": profile.digest_day,
        "digest_podcast_enabled": profile.digest_podcast_enabled,
        "digest_podcast_voice_mode": profile.digest_podcast_voice_mode,
        "digest_top_papers": profile.digest_top_papers,
        "podcast_digest_enabled": profile.podcast_digest_enabled,
        "podcast_digest_frequency": profile.podcast_digest_frequency,
        "podcast_digest_day": profile.podcast_digest_day,
        "podcast_digest_top_papers": profile.podcast_digest_top_papers,
        "podcast_digest_voice_mode": profile.podcast_digest_voice_mode,
        "scoring_prompt": profile.scoring_prompt,
        "single_voice_prompt": profile.single_voice_prompt,
        "dual_voice_prompt": profile.dual_voice_prompt,
        "single_voice_id": profile.single_voice_id,
        "dual_voice_alex_id": profile.dual_voice_alex_id,
        "dual_voice_sam_id": profile.dual_voice_sam_id,
        "podcast_feed_enabled": profile.podcast_feed_enabled,
        "podcast_feed_token": profile.podcast_feed_token,
        "podcast_feed_title": profile.podcast_feed_title,
        "podcast_feed_description": profile.podcast_feed_description,
        "podcast_feed_author": profile.podcast_feed_author,
        "podcast_feed_cover_url": profile.podcast_feed_cover_url,
    }


@router.patch("/me")
async def update_my_profile(
    req: ProfileUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update the current user's profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == uuid.UUID(user["id"]))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if req.interest_keywords is not None:
        profile.interest_keywords = req.interest_keywords
    if req.interest_categories is not None:
        profile.interest_categories = req.interest_categories
    if req.podcast_preference is not None:
        profile.podcast_preference = req.podcast_preference
    if req.email_digest_enabled is not None:
        profile.email_digest_enabled = req.email_digest_enabled
    if req.digest_frequency is not None:
        profile.digest_frequency = req.digest_frequency
    if req.digest_day is not None:
        valid_days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        if req.digest_day.lower() in valid_days:
            profile.digest_day = req.digest_day.lower()
    if req.digest_podcast_enabled is not None:
        profile.digest_podcast_enabled = req.digest_podcast_enabled
    if req.digest_podcast_voice_mode is not None:
        profile.digest_podcast_voice_mode = req.digest_podcast_voice_mode
    if req.digest_top_papers is not None:
        sys_settings = await get_system_settings(db)
        capped = min(req.digest_top_papers, sys_settings.max_papers_per_digest)
        profile.digest_top_papers = capped if capped > 0 else None
    # Standalone podcast digest settings
    if req.podcast_digest_enabled is not None:
        profile.podcast_digest_enabled = req.podcast_digest_enabled
    if req.podcast_digest_frequency is not None:
        profile.podcast_digest_frequency = req.podcast_digest_frequency
    if req.podcast_digest_day is not None:
        valid_days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        if req.podcast_digest_day.lower() in valid_days:
            profile.podcast_digest_day = req.podcast_digest_day.lower()
    if req.podcast_digest_top_papers is not None:
        sys_settings = await get_system_settings(db)
        capped = min(req.podcast_digest_top_papers, sys_settings.max_papers_per_digest)
        profile.podcast_digest_top_papers = capped if capped > 0 else None
    if req.podcast_digest_voice_mode is not None:
        profile.podcast_digest_voice_mode = req.podcast_digest_voice_mode
    if req.scoring_prompt is not None:
        profile.scoring_prompt = req.scoring_prompt if req.scoring_prompt.strip() else None
    if req.single_voice_prompt is not None:
        profile.single_voice_prompt = req.single_voice_prompt if req.single_voice_prompt.strip() else None
    if req.dual_voice_prompt is not None:
        profile.dual_voice_prompt = req.dual_voice_prompt if req.dual_voice_prompt.strip() else None
    if req.single_voice_id is not None:
        profile.single_voice_id = req.single_voice_id if req.single_voice_id.strip() else None
    if req.dual_voice_alex_id is not None:
        profile.dual_voice_alex_id = req.dual_voice_alex_id if req.dual_voice_alex_id.strip() else None
    if req.dual_voice_sam_id is not None:
        profile.dual_voice_sam_id = req.dual_voice_sam_id if req.dual_voice_sam_id.strip() else None

    # Podcast feed settings
    if req.podcast_feed_enabled is not None:
        profile.podcast_feed_enabled = req.podcast_feed_enabled
        # Auto-generate a feed token when enabling for the first time
        if req.podcast_feed_enabled and not profile.podcast_feed_token:
            profile.podcast_feed_token = str(uuid.uuid4())
    if req.podcast_feed_title is not None:
        profile.podcast_feed_title = req.podcast_feed_title.strip() or None
    if req.podcast_feed_description is not None:
        profile.podcast_feed_description = req.podcast_feed_description.strip() or None
    if req.podcast_feed_author is not None:
        profile.podcast_feed_author = req.podcast_feed_author.strip() or None
    if req.podcast_feed_cover_url is not None:
        profile.podcast_feed_cover_url = req.podcast_feed_cover_url.strip() or None

    await db.commit()
    return {"status": "updated"}


@router.post("/login-event")
async def record_login_event(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a login event: update last_login_at, increment login_count, set accepted_at on first login."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == uuid.UUID(user["id"]))
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.last_login_at = datetime.now(timezone.utc)
        profile.login_count = (profile.login_count or 0) + 1
        if not profile.accepted_at:
            profile.accepted_at = datetime.now(timezone.utc)
        await db.commit()
    return {"status": "ok"}


@router.get("")
async def list_users(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all users (admin only)."""
    result = await db.execute(select(UserProfile).order_by(UserProfile.full_name))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "full_name": u.full_name,
            "role": u.role,
            "email": u.email,
        }
        for u in users
    ]
