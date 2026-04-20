"""News-specific API routes: detail view, actions, admin source management."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models.news_item import NewsItem
from app.models.news_source import NewsSource
from app.models.news_cluster import NewsCluster
from app.services import news_sources_service

router = APIRouter(prefix="/api/v1", tags=["news"])


@router.get("/admin/news-debug")
async def news_debug(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Debug endpoint: count news items by state."""
    from sqlalchemy import func as sa_func

    total = (await db.execute(select(sa_func.count(NewsItem.id)))).scalar() or 0
    primary = (await db.execute(
        select(sa_func.count(NewsItem.id)).where(NewsItem.is_cluster_primary == True)
    )).scalar() or 0
    with_embedding = (await db.execute(
        select(sa_func.count(NewsItem.id)).where(NewsItem.embedding.isnot(None))
    )).scalar() or 0
    sources_count = (await db.execute(
        select(sa_func.count(NewsSource.id))
    )).scalar() or 0
    enabled_sources = (await db.execute(
        select(sa_func.count(NewsSource.id)).where(NewsSource.enabled == True)
    )).scalar() or 0

    # Sample a few items
    sample_result = await db.execute(
        select(NewsItem.id, NewsItem.title, NewsItem.is_cluster_primary, NewsItem.relevance_score, NewsItem.source_id)
        .order_by(NewsItem.created_at.desc())
        .limit(5)
    )
    samples = [
        {"id": str(r[0]), "title": r[1][:60], "is_primary": r[2], "score": float(r[3]) if r[3] else None, "source_id": str(r[4])}
        for r in sample_result.all()
    ]

    return {
        "total_news_items": total,
        "is_cluster_primary_true": primary,
        "with_embedding": with_embedding,
        "news_sources": sources_count,
        "enabled_sources": enabled_sources,
        "recent_samples": samples,
    }


# --- News actions ---

@router.post("/news/{item_id}/star")
async def star_news(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.user_interaction import UserInteraction
    user_id = uuid.UUID(user["id"])
    nid = uuid.UUID(item_id)
    existing = await db.execute(
        select(UserInteraction).where(
            UserInteraction.user_id == user_id,
            UserInteraction.content_type == "news",
            UserInteraction.content_id == nid,
            UserInteraction.event_type == "starred",
        )
    )
    if not existing.scalar_one_or_none():
        db.add(UserInteraction(
            user_id=user_id, content_type="news", content_id=nid, event_type="starred"
        ))
        # Extend retention indefinitely for starred items
        item = await db.get(NewsItem, nid)
        if item:
            item.retention_until = None
        await db.commit()
    return {"status": "starred"}


@router.post("/news/{item_id}/unstar")
async def unstar_news(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.user_interaction import UserInteraction
    from sqlalchemy import delete
    user_id = uuid.UUID(user["id"])
    nid = uuid.UUID(item_id)
    await db.execute(
        delete(UserInteraction).where(
            UserInteraction.user_id == user_id,
            UserInteraction.content_type == "news",
            UserInteraction.content_id == nid,
            UserInteraction.event_type == "starred",
        )
    )
    await db.commit()
    return {"status": "unstarred"}


class NewsRateBody(BaseModel):
    rating: int = Field(ge=1, le=10)
    feedback_type: str | None = None


def _news_follow_up(rating: int) -> tuple[str | None, list[str] | None]:
    """Return follow-up question and options based on news rating value."""
    if 1 <= rating <= 3:
        return (
            "What was wrong with this article?",
            ["Wrong topic / irrelevant", "Already knew this", "Low quality source", "Just not useful"],
        )
    elif 4 <= rating <= 6:
        return (
            "What kept it from scoring higher?",
            ["Adjacent topic", "Too shallow", "Old news / already covered", "Skip"],
        )
    elif 7 <= rating <= 8:
        return (
            "What made this article useful?",
            ["Market / policy insight", "Technology development", "Relevant to my research", "Skip"],
        )
    else:
        return (
            "Great article — what should we do?",
            ["Promote to news anchor", "Save for reference", "Share with lab", "Skip"],
        )


@router.post("/news/{item_id}/rate")
async def rate_news(
    item_id: str,
    body: NewsRateBody,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.user_interaction import UserInteraction
    from sqlalchemy import delete as sa_delete
    user_id = uuid.UUID(user["id"])
    nid = uuid.UUID(item_id)

    # Upsert: delete existing, insert new
    await db.execute(
        sa_delete(UserInteraction).where(
            UserInteraction.user_id == user_id,
            UserInteraction.content_type == "news",
            UserInteraction.content_id == nid,
            UserInteraction.event_type == "rated",
        )
    )
    interaction = UserInteraction(
        user_id=user_id, content_type="news", content_id=nid,
        event_type="rated", event_value={"rating": body.rating, "feedback_type": body.feedback_type},
    )
    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)

    question, options = _news_follow_up(body.rating)
    return {
        "rating_id": str(interaction.id),
        "follow_up_question": question,
        "follow_up_options": options,
    }


@router.post("/news/{item_id}/rate-feedback")
async def submit_news_feedback(
    item_id: str,
    feedback_type: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit follow-up feedback for a news rating."""
    from app.models.user_interaction import UserInteraction
    user_id = uuid.UUID(user["id"])
    nid = uuid.UUID(item_id)

    result = await db.execute(
        select(UserInteraction).where(
            UserInteraction.user_id == user_id,
            UserInteraction.content_type == "news",
            UserInteraction.content_id == nid,
            UserInteraction.event_type == "rated",
        )
    )
    interaction = result.scalar_one_or_none()
    if not interaction:
        raise HTTPException(status_code=404, detail="Rating not found")

    event_value = dict(interaction.event_value or {})
    event_value["feedback_type"] = feedback_type
    interaction.event_value = event_value
    await db.commit()
    return {"status": "ok"}


@router.post("/news/{item_id}/mark_read")
async def mark_read_news(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.user_interaction import UserInteraction
    user_id = uuid.UUID(user["id"])
    nid = uuid.UUID(item_id)
    existing = await db.execute(
        select(UserInteraction).where(
            UserInteraction.user_id == user_id,
            UserInteraction.content_type == "news",
            UserInteraction.content_id == nid,
            UserInteraction.event_type == "marked_read",
        )
    )
    if not existing.scalar_one_or_none():
        db.add(UserInteraction(
            user_id=user_id, content_type="news", content_id=nid, event_type="marked_read"
        ))
        await db.commit()
    return {"status": "marked_read"}


@router.get("/news/{item_id}/my-rating")
async def get_my_news_rating(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.user_interaction import UserInteraction
    user_id = uuid.UUID(user["id"])
    nid = uuid.UUID(item_id)
    result = await db.execute(
        select(UserInteraction).where(
            UserInteraction.user_id == user_id,
            UserInteraction.content_type == "news",
            UserInteraction.content_id == nid,
            UserInteraction.event_type == "rated",
        )
    )
    interaction = result.scalar_one_or_none()
    if interaction and interaction.event_value:
        return {"rating": interaction.event_value.get("rating")}
    return {"rating": None}


# --- News detail ---

@router.get("/news/{item_id}")
async def get_news_item(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a single news item with full detail."""
    try:
        nid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid news item ID")

    result = await db.execute(
        select(NewsItem, NewsSource.name, NewsSource.website_url, NewsSource.authority_weight)
        .join(NewsSource, NewsSource.id == NewsItem.source_id)
        .where(NewsItem.id == nid)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="News item not found")

    item, source_name, source_website, authority_weight = row

    # Get cluster siblings
    cluster_siblings = []
    if item.primary_cluster_id:
        siblings_result = await db.execute(
            select(NewsItem.id, NewsItem.url, NewsItem.title, NewsSource.name)
            .join(NewsSource, NewsSource.id == NewsItem.source_id)
            .where(
                NewsItem.primary_cluster_id == item.primary_cluster_id,
                NewsItem.id != item.id,
            )
        )
        for sid, surl, stitle, sname in siblings_result.all():
            cluster_siblings.append({
                "id": str(sid), "url": surl, "title": stitle, "source_name": sname
            })

    return {
        "id": str(item.id),
        "source_id": str(item.source_id),
        "source_name": source_name,
        "source_website": source_website,
        "authority_weight": float(authority_weight),
        "url": item.url,
        "canonical_url": item.canonical_url,
        "title": item.title,
        "excerpt": item.excerpt,
        "full_text": item.full_text,
        "full_text_scraped_at": item.full_text_scraped_at.isoformat() if item.full_text_scraped_at else None,
        "author": item.author,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "tags": item.tags or [],
        "categories": item.categories or [],
        "relevance_score": float(item.relevance_score) if item.relevance_score else None,
        "llm_score": float(item.llm_score) if item.llm_score else None,
        "llm_score_reasoning": item.llm_score_reasoning,
        "summary": item.summary,
        "summary_generated_at": item.summary_generated_at.isoformat() if item.summary_generated_at else None,
        "is_cluster_primary": item.is_cluster_primary,
        "scholarlib_ref_id": item.scholarlib_ref_id,
        "cluster_also_covered_in": cluster_siblings,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


# --- Admin: News sources ---

class NewsSourceCreate(BaseModel):
    name: str
    feed_url: str
    website_url: str
    authority_weight: float = Field(1.0, ge=0, le=2)
    per_source_daily_cap: int = Field(5, ge=1)
    per_source_min_relevance: float = Field(0.30, ge=0, le=1)


class NewsSourceUpdate(BaseModel):
    name: str | None = None
    feed_url: str | None = None
    website_url: str | None = None
    authority_weight: float | None = Field(None, ge=0, le=2)
    enabled: bool | None = None
    per_source_daily_cap: int | None = Field(None, ge=1)
    per_source_min_relevance: float | None = Field(None, ge=0, le=1)


@router.get("/admin/news-sources")
async def list_news_sources(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    sources = await news_sources_service.get_all_sources(db)
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "feed_url": s.feed_url,
            "website_url": s.website_url,
            "authority_weight": float(s.authority_weight),
            "enabled": s.enabled,
            "per_source_daily_cap": s.per_source_daily_cap,
            "per_source_min_relevance": float(s.per_source_min_relevance),
            "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
            "last_fetch_status": s.last_fetch_status,
            "last_fetch_error": s.last_fetch_error,
        }
        for s in sources
    ]


@router.post("/admin/news-sources")
async def create_news_source(
    body: NewsSourceCreate,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await news_sources_service.create_source(db, **body.model_dump())
    return {"id": str(source.id), "name": source.name}


@router.patch("/admin/news-sources/{source_id}")
async def update_news_source(
    source_id: str,
    body: NewsSourceUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    source = await news_sources_service.update_source(db, uuid.UUID(source_id), **updates)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"id": str(source.id), "name": source.name, "status": "updated"}


@router.delete("/admin/news-sources/{source_id}")
async def delete_news_source(
    source_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    deleted = await news_sources_service.delete_source(db, uuid.UUID(source_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "deleted"}


@router.post("/admin/news-sources/{source_id}/test-feed")
async def test_feed(
    source_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await news_sources_service.get_source(db, uuid.UUID(source_id))
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return await news_sources_service.validate_feed(source.feed_url)


@router.post("/admin/news-sources/{source_id}/run-now")
async def run_ingest_now(
    source_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await news_sources_service.get_source(db, uuid.UUID(source_id))
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    from app.services.news_ingest import ingest_source
    from app.services.relevance_service import load_anchors
    await load_anchors(db)
    stats = await ingest_source(db, source)

    # Include total news_items count for debugging
    from sqlalchemy import func as sa_func
    total = (await db.execute(
        select(sa_func.count(NewsItem.id)).where(
            NewsItem.source_id == source.id,
            NewsItem.is_cluster_primary == True,
        )
    )).scalar() or 0
    stats["total_visible"] = total

    return stats
