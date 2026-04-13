import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.share import Share
from app.models.paper import Paper
from app.models.podcast import Podcast
from app.models.user_profile import UserProfile

router = APIRouter(prefix="/api/v1/shares", tags=["shares"])


class ShareRequest(BaseModel):
    paper_id: str | None = None
    shared_with: str  # user ID
    annotation: str | None = None
    podcast_id: str | None = None


@router.post("")
async def create_share(
    req: ShareRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Share a paper and/or podcast with another user."""
    if not req.paper_id and not req.podcast_id:
        raise HTTPException(status_code=400, detail="Must provide paper_id or podcast_id")

    # Verify paper exists (if provided)
    if req.paper_id:
        paper = await db.execute(select(Paper).where(Paper.id == uuid.UUID(req.paper_id)))
        if not paper.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Paper not found")

    # Verify podcast exists (if provided)
    if req.podcast_id:
        podcast = await db.execute(select(Podcast).where(Podcast.id == uuid.UUID(req.podcast_id)))
        if not podcast.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Podcast not found")

    # Verify target user exists
    target = await db.execute(select(UserProfile).where(UserProfile.id == uuid.UUID(req.shared_with)))
    if not target.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Target user not found")

    share = Share(
        id=uuid.uuid4(),
        paper_id=uuid.UUID(req.paper_id) if req.paper_id else None,
        shared_by=uuid.UUID(user["id"]),
        shared_with=uuid.UUID(req.shared_with),
        annotation=req.annotation,
        podcast_id=uuid.UUID(req.podcast_id) if req.podcast_id else None,
    )
    db.add(share)
    await db.commit()

    return {"id": str(share.id), "status": "shared"}


@router.get("/inbox")
async def get_inbox(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get papers/podcasts shared with the current user."""
    result = await db.execute(
        select(Share, Paper, Podcast, UserProfile)
        .outerjoin(Paper, Share.paper_id == Paper.id)
        .outerjoin(Podcast, Share.podcast_id == Podcast.id)
        .join(UserProfile, Share.shared_by == UserProfile.id)
        .where(Share.shared_with == uuid.UUID(user["id"]))
        .order_by(Share.shared_at.desc())
    )
    rows = result.all()
    items = []
    for share, paper, podcast, sharer in rows:
        item: dict[str, Any] = {
            "id": str(share.id),
            "sharer_name": sharer.full_name,
            "annotation": share.annotation,
            "is_read": share.is_read,
            "shared_at": share.shared_at.isoformat() if share.shared_at else None,
        }
        if paper:
            item["paper"] = {
                "id": str(paper.id),
                "title": paper.title,
                "journal": paper.journal,
                "authors": paper.authors,
                "abstract": paper.abstract,
                "relevance_score": None,
            }
        if podcast:
            item["podcast"] = {
                "id": str(podcast.id),
                "title": podcast.title or podcast.paper_id and "Paper podcast" or "Digest podcast",
                "podcast_type": podcast.podcast_type,
                "voice_mode": podcast.voice_mode,
                "duration_seconds": podcast.duration_seconds,
                "audio_path": podcast.audio_path,
            }
        items.append(item)
    return items


@router.get("/sent")
async def get_sent(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get papers shared by the current user."""
    result = await db.execute(
        select(Share, Paper, UserProfile)
        .join(Paper, Share.paper_id == Paper.id)
        .join(UserProfile, Share.shared_with == UserProfile.id)
        .where(Share.shared_by == uuid.UUID(user["id"]))
        .order_by(Share.shared_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(share.id),
            "paper": {
                "id": str(paper.id),
                "title": paper.title,
                "journal": paper.journal,
            },
            "recipient_name": recipient.full_name,
            "annotation": share.annotation,
            "is_read": share.is_read,
            "shared_at": share.shared_at.isoformat() if share.shared_at else None,
        }
        for share, paper, recipient in rows
    ]


@router.patch("/{share_id}/read")
async def mark_as_read(
    share_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a share as read."""
    result = await db.execute(
        select(Share).where(
            Share.id == uuid.UUID(share_id),
            Share.shared_with == uuid.UUID(user["id"]),
        )
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")

    share.is_read = True
    await db.commit()
    return {"status": "ok"}
