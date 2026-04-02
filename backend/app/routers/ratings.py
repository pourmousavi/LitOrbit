import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.rating import Rating
from app.models.paper import Paper
from app.models.user_profile import UserProfile

router = APIRouter(prefix="/api/v1/ratings", tags=["ratings"])


class RatingRequest(BaseModel):
    paper_id: str
    rating: int = Field(ge=1, le=10)
    feedback_type: str | None = None
    feedback_note: str | None = None


class RatingResponse(BaseModel):
    rating_id: str
    follow_up_question: str | None = None
    follow_up_options: list[str] | None = None


def get_follow_up(rating_value: int) -> tuple[str | None, list[str] | None]:
    """Return follow-up question and options based on rating value."""
    if 1 <= rating_value <= 3:
        return (
            "Was this paper irrelevant to your field entirely, or relevant area but poor quality/contribution?",
            ["Irrelevant field", "Poor quality", "Too basic", "Already knew this"],
        )
    elif 4 <= rating_value <= 6:
        return None, None
    elif 7 <= rating_value <= 8:
        return (
            "What interested you most about this paper?",
            ["The methodology", "The application domain", "The dataset/results", "The theoretical contribution"],
        )
    else:  # 9-10
        return (
            "Would you like us to find related work?",
            ["Find papers citing this", "Find papers by same authors", "Both", "No thanks"],
        )


async def update_interest_vector(
    db: AsyncSession,
    user_id: str,
    paper_categories: list[str],
    rating_value: int,
) -> None:
    """Update user's interest vector based on rating.

    Increment category weight by (rating - 5) * 0.1.
    Normalise to stay in [-1.0, 1.0].
    """
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    vector = dict(user.interest_vector) if user.interest_vector else {}
    delta = (rating_value - 5) * 0.1

    for cat in paper_categories:
        current = vector.get(cat, 0.0)
        new_val = max(-1.0, min(1.0, current + delta))
        vector[cat] = round(new_val, 3)

    user.interest_vector = vector
    await db.commit()


@router.post("", response_model=RatingResponse)
async def submit_rating(
    req: RatingRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RatingResponse:
    """Submit or update a rating for a paper."""
    user_id = user["id"]
    paper_id = uuid.UUID(req.paper_id)

    # Verify paper exists
    paper_result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = paper_result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Upsert rating
    existing = await db.execute(
        select(Rating).where(Rating.paper_id == paper_id, Rating.user_id == uuid.UUID(user_id))
    )
    rating_obj = existing.scalar_one_or_none()

    if rating_obj:
        rating_obj.rating = req.rating
        rating_obj.feedback_type = req.feedback_type
        rating_obj.feedback_note = req.feedback_note
    else:
        rating_obj = Rating(
            id=uuid.uuid4(),
            paper_id=paper_id,
            user_id=uuid.UUID(user_id),
            rating=req.rating,
            feedback_type=req.feedback_type,
            feedback_note=req.feedback_note,
        )
        db.add(rating_obj)

    await db.commit()

    # Update interest vector
    await update_interest_vector(db, user_id, paper.categories or [], req.rating)

    # Get follow-up
    question, options = get_follow_up(req.rating)

    return RatingResponse(
        rating_id=str(rating_obj.id),
        follow_up_question=question,
        follow_up_options=options,
    )


@router.post("/{rating_id}/feedback")
async def submit_feedback(
    rating_id: str,
    feedback_type: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit follow-up feedback for a rating."""
    result = await db.execute(
        select(Rating).where(
            Rating.id == uuid.UUID(rating_id),
            Rating.user_id == uuid.UUID(user["id"]),
        )
    )
    rating = result.scalar_one_or_none()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")

    rating.feedback_type = feedback_type
    await db.commit()
    return {"status": "ok"}


@router.get("/history")
async def get_rating_history(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get the current user's rating history."""
    result = await db.execute(
        select(Rating, Paper.title, Paper.journal)
        .join(Paper, Rating.paper_id == Paper.id)
        .where(Rating.user_id == uuid.UUID(user["id"]))
        .order_by(Rating.rated_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(r.id),
            "paper_id": str(r.paper_id),
            "paper_title": title,
            "paper_journal": journal,
            "rating": r.rating,
            "feedback_type": r.feedback_type,
            "rated_at": r.rated_at.isoformat() if r.rated_at else None,
        }
        for r, title, journal in rows
    ]
