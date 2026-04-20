import json
import logging
import uuid
from datetime import datetime, timezone
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

logger = logging.getLogger(__name__)

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
            "What was wrong with this paper?",
            [
                "Wrong topic / out of scope",
                "Right topic, weak paper",
                "Too basic / I already know this",
                "Just not for me right now",
            ],
        )
    elif 4 <= rating_value <= 6:
        return (
            "What kept it from scoring higher?",
            [
                "Adjacent topic, not quite my focus",
                "Interesting but methodology is weak",
                "Too review-y / not enough novelty",
                "Skip",
            ],
        )
    elif 7 <= rating_value <= 8:
        return (
            "What drew you to this paper?",
            [
                "The methodology / technique",
                "The application domain",
                "Both equally",
                "Skip",
            ],
        )
    else:  # 9-10
        return (
            "Great find — how should we use this?",
            [
                "Promote to my reference papers",
                "Extra-weight positive anchor",
                "Tag as methods gem",
                "Tag as application gem",
            ],
        )


def feedback_to_anchor_spec(rating: int, feedback_type: str | None) -> dict | None:
    """Derive anchor specification from a rating + optional feedback_type.

    Returns None (no anchor), {"remove": True}, or a spec dict with
    polarity, weight, tags, promote_to_reference keys.
    """
    if 1 <= rating <= 3:
        if feedback_type is None:
            return {"polarity": "negative", "weight": 1.0, "tags": [], "promote_to_reference": False}
        if feedback_type == "Wrong topic / out of scope":
            return {"polarity": "negative", "weight": 1.0, "tags": [], "promote_to_reference": False}
        if feedback_type == "Too basic / I already know this":
            return {"polarity": "negative", "weight": 0.3, "tags": [], "promote_to_reference": False}
        if feedback_type in ("Right topic, weak paper", "Just not for me right now"):
            return {"remove": True}
        return {"polarity": "negative", "weight": 1.0, "tags": [], "promote_to_reference": False}
    elif 4 <= rating <= 6:
        if feedback_type is None:
            return None
        if feedback_type == "Adjacent topic, not quite my focus":
            return {"polarity": "negative", "weight": 0.3, "tags": [], "promote_to_reference": False}
        return None
    elif 7 <= rating <= 8:
        if feedback_type is None or feedback_type == "Skip":
            return {"polarity": "positive", "weight": 1.0, "tags": [], "promote_to_reference": False}
        if feedback_type == "The methodology / technique":
            return {"polarity": "positive", "weight": 1.0, "tags": ["methods"], "promote_to_reference": False}
        if feedback_type == "The application domain":
            return {"polarity": "positive", "weight": 1.0, "tags": ["applications"], "promote_to_reference": False}
        if feedback_type == "Both equally":
            return {"polarity": "positive", "weight": 1.0, "tags": ["methods", "applications"], "promote_to_reference": False}
        return {"polarity": "positive", "weight": 1.0, "tags": [], "promote_to_reference": False}
    else:  # 9-10
        if feedback_type is None:
            return {"polarity": "positive", "weight": 1.5, "tags": [], "promote_to_reference": False}
        if feedback_type == "Promote to my reference papers":
            return {"polarity": "positive", "weight": 1.0, "tags": [], "promote_to_reference": True}
        if feedback_type == "Extra-weight positive anchor":
            return {"polarity": "positive", "weight": 2.0, "tags": [], "promote_to_reference": False}
        if feedback_type == "Tag as methods gem":
            return {"polarity": "positive", "weight": 1.5, "tags": ["methods"], "promote_to_reference": False}
        if feedback_type == "Tag as application gem":
            return {"polarity": "positive", "weight": 1.5, "tags": ["applications"], "promote_to_reference": False}
        return {"polarity": "positive", "weight": 1.5, "tags": [], "promote_to_reference": False}


MAX_ANCHORS_PER_LIST = 100


async def apply_anchor_update(
    db: AsyncSession,
    user_id: uuid.UUID,
    paper_id: uuid.UUID,
    spec: dict | None,
) -> None:
    """Apply an anchor specification to the user's anchor sets.

    If spec is None: no-op.
    If spec == {"remove": True}: remove anchor from both lists.
    Otherwise: upsert into the appropriate list based on polarity.
    """
    if spec is None:
        return

    result = await db.execute(
        select(UserProfile).where(UserProfile.id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return

    paper_id_str = str(paper_id)
    positive = list(profile.positive_anchors or [])
    negative = list(profile.negative_anchors or [])

    if spec.get("remove"):
        positive = [a for a in positive if a.get("paper_id") != paper_id_str]
        negative = [a for a in negative if a.get("paper_id") != paper_id_str]
        profile.positive_anchors = positive
        profile.negative_anchors = negative
        await db.commit()
        return

    # Fetch paper embedding
    paper_result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = paper_result.scalar_one_or_none()
    if not paper or not paper.embedding:
        logger.warning(f"Paper {paper_id} has no embedding, skipping anchor update")
        return

    # Handle promote_to_reference
    if spec.get("promote_to_reference"):
        from app.models.reference_paper import ReferencePaper
        from sqlalchemy import func as sa_func
        from app.routers.reference_papers import MAX_REFERENCE_PAPERS, _recompute_profile_embedding

        count_result = await db.execute(
            select(sa_func.count()).where(ReferencePaper.user_id == user_id)
        )
        ref_count = count_result.scalar() or 0
        if ref_count >= MAX_REFERENCE_PAPERS:
            raise HTTPException(
                status_code=409,
                detail="Reference papers full — please remove one before promoting another.",
            )

        # Add as reference paper
        ref_paper = ReferencePaper(
            id=uuid.uuid4(),
            user_id=user_id,
            title=paper.title,
            abstract=paper.abstract,
            doi=paper.doi,
            source="promoted",
            embedding=paper.embedding,
        )
        db.add(ref_paper)
        await db.commit()
        # Recompute profile (this also updates positive_anchors with source="reference")
        await _recompute_profile_embedding(db, user_id)
        return

    polarity = spec["polarity"]
    target = positive if polarity == "positive" else negative
    opposite = negative if polarity == "positive" else positive

    # Remove from opposite list if present
    opposite[:] = [a for a in opposite if a.get("paper_id") != paper_id_str]

    # Upsert into target list
    now_iso = datetime.now(timezone.utc).isoformat()
    existing_idx = None
    for i, a in enumerate(target):
        if a.get("paper_id") == paper_id_str:
            existing_idx = i
            break

    entry = {
        "paper_id": paper_id_str,
        "embedding": paper.embedding,
        "source": "rating",
        "weight": spec["weight"],
        "added_at": target[existing_idx].get("added_at", now_iso) if existing_idx is not None else now_iso,
        "tags": spec["tags"],
    }
    if existing_idx is not None:
        entry["updated_at"] = now_iso
        target[existing_idx] = entry
    else:
        # Enforce cap
        if len(target) >= MAX_ANCHORS_PER_LIST:
            # Evict oldest with weight < 1.0 first, then oldest overall
            evict_idx = None
            for i, a in enumerate(target):
                if a.get("source") == "reference":
                    continue
                if a.get("weight", 1.0) < 1.0:
                    if evict_idx is None or a.get("added_at", "") < target[evict_idx].get("added_at", ""):
                        evict_idx = i
            if evict_idx is None:
                # No low-weight entries; evict oldest overall (non-reference)
                for i, a in enumerate(target):
                    if a.get("source") == "reference":
                        continue
                    if evict_idx is None or a.get("added_at", "") < target[evict_idx].get("added_at", ""):
                        evict_idx = i
            if evict_idx is not None:
                target.pop(evict_idx)
        target.append(entry)

    profile.positive_anchors = positive
    profile.negative_anchors = negative
    await db.commit()


async def update_category_weights(
    db: AsyncSession,
    user_id: str,
    paper_categories: list[str],
    rating_value: int,
) -> None:
    """Update user's category_weights based on rating.

    Increment category weight by (rating - 5) * 0.1.
    Normalise to stay in [-1.0, 1.0].

    Note: this writes to ``category_weights`` (the human-readable field powering
    the Interest Profile chart), NOT ``interest_vector`` (which holds the
    reference-paper embedding centroid used by the pipeline pre-filter).
    """
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    weights = dict(user.category_weights) if user.category_weights else {}
    delta = (rating_value - 5) * 0.1

    for cat in paper_categories:
        current = weights.get(cat, 0.0)
        new_val = max(-1.0, min(1.0, current + delta))
        weights[cat] = round(new_val, 3)

    user.category_weights = weights
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
    await update_category_weights(db, user_id, paper.categories or [], req.rating)

    # Update anchor sets based on rating + feedback
    spec = feedback_to_anchor_spec(req.rating, req.feedback_type)
    try:
        await apply_anchor_update(db, uuid.UUID(user_id), paper_id, spec)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Anchor update failed for rating on paper {paper_id}: {e}")

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

    # Re-derive and apply anchor update with the new feedback
    spec = feedback_to_anchor_spec(rating.rating, feedback_type)
    try:
        await apply_anchor_update(db, uuid.UUID(user["id"]), rating.paper_id, spec)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Anchor update failed for feedback on rating {rating_id}: {e}")

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
