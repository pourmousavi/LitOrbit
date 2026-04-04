import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models.user_profile import UserProfile

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class ProfileUpdate(BaseModel):
    interest_keywords: list[str] | None = None
    interest_categories: list[str] | None = None
    podcast_preference: str | None = None
    email_digest_enabled: bool | None = None
    digest_frequency: str | None = None
    digest_podcast_enabled: bool | None = None
    digest_podcast_voice_mode: str | None = None
    digest_top_papers: int | None = None
    scoring_prompt: str | None = None
    single_voice_prompt: str | None = None
    dual_voice_prompt: str | None = None
    single_voice_id: str | None = None
    dual_voice_alex_id: str | None = None
    dual_voice_sam_id: str | None = None


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
        "podcast_preference": profile.podcast_preference,
        "email_digest_enabled": profile.email_digest_enabled,
        "digest_frequency": profile.digest_frequency,
        "digest_podcast_enabled": profile.digest_podcast_enabled,
        "digest_podcast_voice_mode": profile.digest_podcast_voice_mode,
        "digest_top_papers": profile.digest_top_papers,
        "scoring_prompt": profile.scoring_prompt,
        "single_voice_prompt": profile.single_voice_prompt,
        "dual_voice_prompt": profile.dual_voice_prompt,
        "single_voice_id": profile.single_voice_id,
        "dual_voice_alex_id": profile.dual_voice_alex_id,
        "dual_voice_sam_id": profile.dual_voice_sam_id,
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
    if req.digest_podcast_enabled is not None:
        profile.digest_podcast_enabled = req.digest_podcast_enabled
    if req.digest_podcast_voice_mode is not None:
        profile.digest_podcast_voice_mode = req.digest_podcast_voice_mode
    if req.digest_top_papers is not None:
        profile.digest_top_papers = req.digest_top_papers if req.digest_top_papers > 0 else None
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

    await db.commit()
    return {"status": "updated"}


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
