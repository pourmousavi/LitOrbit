"""News-specific API routes: detail view, actions, admin source management."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models.news_item import NewsItem
from app.models.news_source import NewsSource
from app.models.news_cluster import NewsCluster
from app.services import news_sources_service

logger = logging.getLogger(__name__)
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

    # Update category_weights from news item categories (same mechanism as papers)
    item_result = await db.execute(
        select(NewsItem).where(NewsItem.id == nid)
    )
    news_item = item_result.scalar_one_or_none()
    if news_item and news_item.categories:
        from app.routers.ratings import update_category_weights
        await update_category_weights(db, str(user_id), news_item.categories, body.rating)

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


@router.post("/news/{item_id}/rescore")
async def rescore_news_item(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-score and re-summarise a single news item."""
    nid = uuid.UUID(item_id)
    item = await db.get(NewsItem, nid)
    if not item:
        raise HTTPException(status_code=404, detail="News item not found")

    source = await db.get(NewsSource, item.source_id)
    source_name = source.name if source else "Unknown"

    from app.services.news_scorer import score_and_summarise_news_item
    await score_and_summarise_news_item(db, item, source_name)

    return {
        "status": "success",
        "llm_score": float(item.llm_score) if item.llm_score else None,
        "llm_score_reasoning": item.llm_score_reasoning,
        "summary_regenerated": item.summary is not None,
    }


@router.get("/news/{item_id}/podcast")
async def get_news_podcast(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    voice_mode: str = Query("single"),
) -> dict:
    """Get podcast status for a news item."""
    from app.models.podcast import Podcast
    from datetime import timedelta

    nid = uuid.UUID(item_id)
    result = await db.execute(
        select(Podcast).where(
            Podcast.news_item_id == nid,
            Podcast.voice_mode == voice_mode,
        ).order_by(Podcast.generated_at.desc())
    )
    podcast = result.scalar_one_or_none()

    if not podcast:
        return {"status": "not_generated", "podcast": None}

    if podcast.audio_path:
        return {
            "status": "ready",
            "podcast": {
                "id": str(podcast.id),
                "news_item_id": str(podcast.news_item_id),
                "voice_mode": podcast.voice_mode,
                "audio_url": f"/api/v1/podcasts/audio/{podcast.id}",
                "duration_seconds": podcast.duration_seconds,
                "generated_at": podcast.generated_at.isoformat() if podcast.generated_at else None,
            },
        }

    if podcast.script and podcast.script.startswith("ERROR:"):
        return {"status": "failed", "error": podcast.script, "podcast": None}

    from datetime import datetime, timezone
    if podcast.generated_at:
        age = datetime.now(timezone.utc) - podcast.generated_at.replace(tzinfo=timezone.utc)
        if age > timedelta(minutes=10):
            await db.delete(podcast)
            await db.commit()
            return {"status": "not_generated", "podcast": None}

    return {"status": "generating", "podcast": None}


@router.post("/news/{item_id}/podcast/generate")
async def generate_news_podcast(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    voice_mode: str = Query("single"),
) -> dict:
    """Start podcast generation for a news item."""
    import json
    import os
    from datetime import datetime, timezone
    from app.models.podcast import Podcast
    from app.services.podcast import generate_podcast
    from app.services.storage import upload_audio
    from sqlalchemy import func as sa_func

    nid = uuid.UUID(item_id)
    item = await db.get(NewsItem, nid)
    if not item:
        raise HTTPException(status_code=404, detail="News item not found")

    # Build content for podcast
    content = ""
    if item.summary:
        try:
            summary_data = json.loads(item.summary)
            parts = []
            for key in ("key_points", "industry_impact", "relevance"):
                val = summary_data.get(key)
                if val and isinstance(val, str):
                    parts.append(val)
            content = " ".join(parts)
        except json.JSONDecodeError:
            content = item.summary

    if not content and item.full_text:
        content = item.full_text[:4000]
    if not content and item.excerpt:
        content = item.excerpt
    if not content:
        raise HTTPException(status_code=400, detail="News item has no content to generate podcast from")

    # Check existing
    existing = await db.execute(
        select(Podcast).where(
            Podcast.news_item_id == nid,
            Podcast.voice_mode == voice_mode,
            Podcast.audio_path.isnot(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Podcast already exists. Delete it first to regenerate.")

    # Clean up old failed records
    old_result = await db.execute(
        select(Podcast).where(
            Podcast.news_item_id == nid,
            Podcast.voice_mode == voice_mode,
            Podcast.audio_path.is_(None),
        )
    )
    for old in old_result.scalars().all():
        await db.delete(old)

    # Get avg generation time
    avg_result = await db.execute(
        select(sa_func.avg(Podcast.generation_time_seconds)).where(
            Podcast.generation_time_seconds.isnot(None),
            Podcast.audio_path.isnot(None),
        )
    )
    avg_time = avg_result.scalar()

    # Create placeholder
    podcast = Podcast(
        id=uuid.uuid4(),
        news_item_id=nid,
        user_id=uuid.UUID(user["id"]),
        voice_mode=voice_mode,
        podcast_type="news",
        title=f"News: {item.title[:80]}",
    )
    db.add(podcast)
    await db.commit()

    # Generate in background (reuse the paper podcast generator)
    import asyncio
    asyncio.create_task(_generate_news_podcast_bg(
        str(podcast.id), item.title, content, voice_mode, user["id"],
    ))

    return {
        "status": "generating",
        "podcast_id": str(podcast.id),
        "estimated_seconds": int(avg_time) if avg_time else 45,
    }


async def _generate_news_podcast_bg(
    podcast_id: str, title: str, content: str, voice_mode: str, user_id: str,
) -> None:
    """Background task to generate news podcast audio."""
    import logging
    import os
    import time
    import app.database as _db_module

    logger = logging.getLogger(__name__)

    if _db_module.async_session_factory is None:
        _db_module.init_db()

    start_time = time.time()
    async with _db_module.async_session_factory() as db:
        try:
            # Get user voice settings
            user_profile = (await db.execute(
                select(UserProfile).where(UserProfile.id == uuid.UUID(user_id))
            )).scalar_one_or_none()

            custom_prompt = None
            custom_voices = None
            if user_profile:
                if voice_mode == "single" and user_profile.single_voice_prompt:
                    custom_prompt = user_profile.single_voice_prompt
                elif voice_mode == "dual" and user_profile.dual_voice_prompt:
                    custom_prompt = user_profile.dual_voice_prompt
                voices: dict[str, str] = {}
                if voice_mode == "single" and user_profile.single_voice_id:
                    voices["single"] = user_profile.single_voice_id
                elif voice_mode == "dual":
                    if user_profile.dual_voice_alex_id:
                        voices["alex"] = user_profile.dual_voice_alex_id
                    if user_profile.dual_voice_sam_id:
                        voices["sam"] = user_profile.dual_voice_sam_id
                if voices:
                    custom_voices = voices

            output_dir = os.path.join("/tmp", "litorbit_podcasts")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{podcast_id}.mp3")

            from app.services.podcast import generate_podcast
            script, audio_path, duration = await generate_podcast(
                title=title, summary=content, voice_mode=voice_mode,
                output_path=output_path, custom_prompt=custom_prompt,
                custom_voices=custom_voices,
            )

            from app.services.storage import upload_audio
            storage_key = f"{podcast_id}.mp3"
            public_url = await upload_audio(audio_path, storage_key)
            if not public_url:
                raise RuntimeError("Audio upload failed")

            gen_time = int(time.time() - start_time)
            from app.models.podcast import Podcast
            result = await db.execute(select(Podcast).where(Podcast.id == uuid.UUID(podcast_id)))
            podcast = result.scalar_one_or_none()
            if podcast:
                podcast.script = script
                podcast.audio_path = public_url
                podcast.duration_seconds = duration
                podcast.generation_time_seconds = gen_time
                await db.commit()

            if os.path.exists(audio_path):
                os.unlink(audio_path)

        except Exception as e:
            gen_time = int(time.time() - start_time)
            logger.exception(f"News podcast generation failed: {e}")
            from app.models.podcast import Podcast
            result = await db.execute(select(Podcast).where(Podcast.id == uuid.UUID(podcast_id)))
            podcast = result.scalar_one_or_none()
            if podcast:
                podcast.script = f"ERROR: {e}"
                podcast.generation_time_seconds = gen_time
                await db.commit()


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


class NewsSourceUpdate(BaseModel):
    name: str | None = None
    feed_url: str | None = None
    website_url: str | None = None
    authority_weight: float | None = Field(None, ge=0, le=2)
    enabled: bool | None = None
    per_source_daily_cap: int | None = Field(None, ge=1)


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


# --- News ingest runs ---


@router.get("/admin/news/runs")
async def list_news_runs(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List recent news ingest runs."""
    from app.models.news_ingest_run import NewsIngestRun

    result = await db.execute(
        select(NewsIngestRun)
        .order_by(NewsIngestRun.started_at.desc())
        .limit(50)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "status": r.status,
            "items_new": r.items_new,
            "items_skipped": r.items_skipped,
            "items_embedded": r.items_embedded,
            "items_scored": r.items_scored,
            "items_errors": r.items_errors,
            "sources_total": r.sources_total,
            "sources_succeeded": r.sources_succeeded,
            "sources_failed": r.sources_failed,
            "error_message": r.error_message,
            "run_log": r.run_log,
        }
        for r in runs
    ]


@router.post("/admin/news/trigger")
async def trigger_news_ingest(
    background_tasks: BackgroundTasks,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict:
    """Trigger a full news ingest across all enabled sources (runs in background)."""
    async def _run():
        from app.database import init_db, async_session_factory
        from app.services.news_ingest import ingest_all_enabled_sources
        from app.services.relevance_service import load_anchors

        try:
            if async_session_factory is None:
                init_db()
            if async_session_factory is None:
                return
            async with async_session_factory() as session:
                await load_anchors(session)
                results = await ingest_all_enabled_sources(session)
                logger.info(f"Manual news ingest: {len(results)} sources processed")
        except Exception as e:
            logger.exception(f"Manual news ingest failed: {e}")

    background_tasks.add_task(_run)
    return {"status": "triggered"}


@router.delete("/admin/news/runs/{run_id}/items")
async def delete_news_run_items(
    run_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete all news items from a specific ingest run."""
    from app.models.news_ingest_run import NewsIngestRun
    from sqlalchemy import func as sa_func, delete

    rid = uuid.UUID(run_id)
    run = await db.get(NewsIngestRun, rid)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Count items in this run
    count = (await db.execute(
        select(sa_func.count(NewsItem.id)).where(NewsItem.ingest_run_id == rid)
    )).scalar() or 0

    # Delete them
    await db.execute(
        delete(NewsItem).where(NewsItem.ingest_run_id == rid)
    )

    # Update run status
    run.status = "deleted"
    run.error_message = f"{count} items deleted"
    await db.commit()

    return {"status": "deleted", "items_deleted": count}


@router.post("/admin/news/runs/{run_id}/rescore")
async def rescore_news_run(
    run_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-score all news items from a specific ingest run."""
    from app.models.news_ingest_run import NewsIngestRun
    from app.services.news_scorer import score_and_summarise_news_item

    rid = uuid.UUID(run_id)
    run = await db.get(NewsIngestRun, rid)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get items from this run that are cluster primaries
    result = await db.execute(
        select(NewsItem, NewsSource.name)
        .join(NewsSource, NewsSource.id == NewsItem.source_id)
        .where(
            NewsItem.ingest_run_id == rid,
            NewsItem.is_cluster_primary == True,
        )
    )
    rows = result.all()

    scored = 0
    errors = 0
    for item, source_name in rows:
        try:
            await score_and_summarise_news_item(db, item, source_name)
            scored += 1
        except Exception:
            errors += 1

    return {"status": "completed", "items_rescored": scored, "errors": errors}


@router.get("/admin/news/stats")
async def news_stats(
    _admin: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get news stats for the admin stat bar."""
    from app.models.news_ingest_run import NewsIngestRun
    from sqlalchemy import func as sa_func

    total_items = (await db.execute(
        select(sa_func.count(NewsItem.id))
    )).scalar() or 0

    scored_items = (await db.execute(
        select(sa_func.count(NewsItem.id)).where(NewsItem.llm_score.isnot(None))
    )).scalar() or 0

    total_sources = (await db.execute(
        select(sa_func.count(NewsSource.id))
    )).scalar() or 0

    enabled_sources = (await db.execute(
        select(sa_func.count(NewsSource.id)).where(NewsSource.enabled == True)
    )).scalar() or 0

    # Last successful run
    last_run_result = await db.execute(
        select(NewsIngestRun.completed_at)
        .where(NewsIngestRun.status.in_(["success", "partial"]))
        .order_by(NewsIngestRun.completed_at.desc())
        .limit(1)
    )
    last_run_row = last_run_result.first()
    last_fetch = last_run_row[0].isoformat() if last_run_row and last_run_row[0] else None

    total_runs = (await db.execute(
        select(sa_func.count(NewsIngestRun.id))
    )).scalar() or 0

    successful_runs = (await db.execute(
        select(sa_func.count(NewsIngestRun.id)).where(
            NewsIngestRun.status.in_(["success", "partial"])
        )
    )).scalar() or 0

    return {
        "total_items": total_items,
        "scored_items": scored_items,
        "total_sources": total_sources,
        "enabled_sources": enabled_sources,
        "last_fetch": last_fetch,
        "total_runs": total_runs,
        "successful_runs": successful_runs,
    }
