import json
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, check_owner_or_admin
from app.database import get_db, init_db
import app.database as _db_module
from app.models.collection import Collection, CollectionPaper
from app.models.digest_log import DigestLog
from app.models.paper import Paper
from app.models.paper_favorite import PaperFavorite
from app.models.podcast import Podcast
from app.models.user_profile import UserProfile
from app.services.podcast import generate_podcast
from app.services.storage import upload_audio

router = APIRouter(prefix="/api/v1/podcasts", tags=["podcasts"])

# Cache voices list (fetched once per process)
_voices_cache: list[dict] | None = None


@router.get("/voices")
async def list_voices() -> list[dict]:
    """List available English TTS voices."""
    global _voices_cache
    if _voices_cache is None:
        import edge_tts
        all_voices = await edge_tts.list_voices()
        _voices_cache = [
            {
                "id": v["ShortName"],
                "name": v["ShortName"].split("-")[2].replace("Neural", "").replace("Multilingual", ""),
                "gender": v["Gender"],
                "locale": v["Locale"],
                "locale_name": v["Locale"].replace("en-", "").replace("AU", "Australia").replace("US", "United States").replace("GB", "United Kingdom").replace("CA", "Canada").replace("IN", "India").replace("IE", "Ireland").replace("NZ", "New Zealand").replace("SG", "Singapore").replace("ZA", "South Africa").replace("HK", "Hong Kong").replace("KE", "Kenya").replace("NG", "Nigeria").replace("PH", "Philippines").replace("TZ", "Tanzania"),
            }
            for v in all_voices
            if v["Locale"].startswith("en-")
        ]
    return _voices_cache


class GenerateRequest(BaseModel):
    voice_mode: str = "single"  # 'single' | 'dual'


async def _generate_in_background(
    paper_id: str,
    podcast_id: str,
    title: str,
    summary: str,
    voice_mode: str,
    custom_prompt: str | None = None,
    custom_voices: dict[str, str] | None = None,
) -> None:
    """Background task to generate podcast audio and upload to Supabase Storage."""
    import logging
    import time
    logger = logging.getLogger(__name__)

    logger.info(f"Podcast generation started for {podcast_id} (paper={paper_id}, mode={voice_mode})")

    if _db_module.async_session_factory is None:
        init_db()

    start_time = time.time()

    async with _db_module.async_session_factory() as db:
        try:
            output_dir = os.path.join("/tmp", "litorbit_podcasts")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{podcast_id}.mp3")

            logger.info(f"Podcast {podcast_id}: generating script and audio...")
            script, audio_path, duration = await generate_podcast(
                title=title,
                summary=summary,
                voice_mode=voice_mode,
                output_path=output_path,
                custom_prompt=custom_prompt,
                custom_voices=custom_voices,
            )

            # Upload to Supabase Storage
            storage_key = f"{podcast_id}.mp3"
            logger.info(f"Podcast {podcast_id}: uploading to Supabase Storage...")
            public_url = await upload_audio(audio_path, storage_key)

            if not public_url:
                raise RuntimeError("Failed to upload audio to Supabase Storage")

            gen_time = int(time.time() - start_time)
            logger.info(f"Podcast {podcast_id}: complete in {gen_time}s, duration={duration}s")

            # Update podcast record with the public URL
            result = await db.execute(
                select(Podcast).where(Podcast.id == uuid.UUID(podcast_id))
            )
            podcast = result.scalar_one_or_none()
            if podcast:
                podcast.script = script
                podcast.audio_path = public_url  # Store the Supabase public URL
                podcast.duration_seconds = duration
                podcast.generation_time_seconds = gen_time
                await db.commit()
                logger.info(f"Podcast {podcast_id}: saved to database")

            # Clean up local temp file
            if os.path.exists(audio_path):
                os.unlink(audio_path)

        except Exception as e:
            gen_time = int(time.time() - start_time)
            logger.exception(f"Podcast generation failed for {podcast_id} after {gen_time}s: {e}")
            try:
                result = await db.execute(
                    select(Podcast).where(Podcast.id == uuid.UUID(podcast_id))
                )
                podcast = result.scalar_one_or_none()
                if podcast:
                    podcast.script = f"ERROR: {str(e)}"
                    podcast.generation_time_seconds = gen_time
                    await db.commit()
            except Exception as db_err:
                logger.exception(f"Failed to save error state for podcast {podcast_id}: {db_err}")


@router.get("/{paper_id}")
async def get_podcast(
    paper_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    voice_mode: str = Query("single"),
) -> dict:
    """Get podcast for a paper. Returns status and URL if ready."""
    result = await db.execute(
        select(Podcast).where(
            Podcast.paper_id == uuid.UUID(paper_id),
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
                "paper_id": str(podcast.paper_id),
                "voice_mode": podcast.voice_mode,
                "audio_url": f"/api/v1/podcasts/audio/{podcast.id}",
                "duration_seconds": podcast.duration_seconds,
                "generation_time_seconds": podcast.generation_time_seconds,
                "generated_at": podcast.generated_at.isoformat() if podcast.generated_at else None,
            },
        }

    if podcast.script and podcast.script.startswith("ERROR:"):
        return {"status": "failed", "error": podcast.script, "podcast": None}

    # If generating for more than 10 minutes, treat as stuck and auto-clean
    from datetime import datetime, timezone, timedelta
    if podcast.generated_at:
        age = datetime.now(timezone.utc) - podcast.generated_at.replace(tzinfo=timezone.utc)
        if age > timedelta(minutes=10):
            await db.delete(podcast)
            await db.commit()
            return {"status": "not_generated", "podcast": None}

    return {"status": "generating", "podcast": None}


@router.post("/{paper_id}/generate")
async def generate_podcast_endpoint(
    paper_id: str,
    req: GenerateRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Start podcast generation as a background task."""
    from datetime import datetime, timezone
    from app.services.settings import get_system_settings

    # Check monthly podcast limit
    sys_settings = await get_system_settings(db)
    first_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    count_result = await db.execute(
        select(func.count()).select_from(Podcast).where(
            Podcast.user_id == uuid.UUID(user["id"]),
            Podcast.generated_at >= first_of_month,
            Podcast.audio_path.isnot(None),
        )
    )
    current_count = count_result.scalar() or 0
    if current_count >= sys_settings.max_podcasts_per_user_per_month:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly podcast limit reached ({sys_settings.max_podcasts_per_user_per_month}). Contact admin to increase.",
        )

    # Get paper
    paper_result = await db.execute(select(Paper).where(Paper.id == uuid.UUID(paper_id)))
    paper = paper_result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Get summary text
    summary_text = ""
    if paper.summary:
        try:
            summary_data = json.loads(paper.summary)
            parts = []
            for key in ("research_gap", "methodology", "key_findings", "relevance_to_energy_group"):
                val = summary_data.get(key)
                if val and isinstance(val, str):
                    parts.append(val)
            summary_text = " ".join(parts)
        except json.JSONDecodeError:
            summary_text = paper.summary

    if not summary_text and paper.abstract:
        summary_text = paper.abstract

    if not summary_text:
        raise HTTPException(status_code=400, detail="Paper has no summary or abstract to generate podcast from")

    # Check if a completed podcast of this type already exists
    existing = await db.execute(
        select(Podcast).where(
            Podcast.paper_id == uuid.UUID(paper_id),
            Podcast.voice_mode == req.voice_mode,
            Podcast.audio_path.isnot(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"A {req.voice_mode} podcast already exists for this paper. Delete it first to regenerate.",
        )

    # Clean up old failed/stuck records for this paper+voice_mode
    old_result = await db.execute(
        select(Podcast).where(
            Podcast.paper_id == uuid.UUID(paper_id),
            Podcast.voice_mode == req.voice_mode,
            Podcast.audio_path.is_(None),
        )
    )
    for old in old_result.scalars().all():
        await db.delete(old)

    # Get average generation time for estimates
    avg_result = await db.execute(
        select(func.avg(Podcast.generation_time_seconds)).where(
            Podcast.generation_time_seconds.isnot(None),
            Podcast.audio_path.isnot(None),
        )
    )
    avg_time = avg_result.scalar()

    # Create podcast record (placeholder)
    podcast = Podcast(
        id=uuid.uuid4(),
        paper_id=uuid.UUID(paper_id),
        user_id=uuid.UUID(user["id"]),
        voice_mode=req.voice_mode,
    )
    db.add(podcast)
    await db.commit()

    # Fetch user's custom podcast settings
    user_profile = (await db.execute(
        select(UserProfile).where(UserProfile.id == uuid.UUID(user["id"]))
    )).scalar_one_or_none()

    custom_prompt = None
    custom_voices = None
    if user_profile:
        if req.voice_mode == "single" and user_profile.single_voice_prompt:
            custom_prompt = user_profile.single_voice_prompt
        elif req.voice_mode == "dual" and user_profile.dual_voice_prompt:
            custom_prompt = user_profile.dual_voice_prompt

        voices: dict[str, str] = {}
        if req.voice_mode == "single" and user_profile.single_voice_id:
            voices["single"] = user_profile.single_voice_id
        elif req.voice_mode == "dual":
            if user_profile.dual_voice_alex_id:
                voices["alex"] = user_profile.dual_voice_alex_id
            if user_profile.dual_voice_sam_id:
                voices["sam"] = user_profile.dual_voice_sam_id
        if voices:
            custom_voices = voices

    # Start background generation
    import asyncio
    asyncio.create_task(
        _generate_in_background(
            paper_id=paper_id,
            podcast_id=str(podcast.id),
            title=paper.title,
            summary=summary_text,
            voice_mode=req.voice_mode,
            custom_prompt=custom_prompt,
            custom_voices=custom_voices,
        )
    )

    return {
        "status": "generating",
        "podcast_id": str(podcast.id),
        "estimated_seconds": int(avg_time) if avg_time else 45,
    }


@router.get("/audio/{podcast_id}")
async def serve_audio(
    podcast_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Redirect to the Supabase Storage URL for the podcast MP3."""
    result = await db.execute(
        select(Podcast).where(Podcast.id == uuid.UUID(podcast_id))
    )
    podcast = result.scalar_one_or_none()

    if not podcast or not podcast.audio_path:
        raise HTTPException(status_code=404, detail="Audio not found")

    # audio_path is now a Supabase public URL — redirect to it
    return RedirectResponse(url=podcast.audio_path, status_code=302)


@router.get("/download/{podcast_id}")
async def download_audio(
    podcast_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Proxy the podcast MP3 with Content-Disposition: attachment to force download."""
    import httpx
    from fastapi.responses import Response

    result = await db.execute(
        select(Podcast).where(Podcast.id == uuid.UUID(podcast_id))
    )
    podcast = result.scalar_one_or_none()

    if not podcast or not podcast.audio_path:
        raise HTTPException(status_code=404, detail="Audio not found")

    # Fetch from Supabase and proxy with download headers
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(podcast.audio_path)

    if resp.status_code != 200:
        raise HTTPException(status_code=404, detail="Audio file not found in storage")

    return Response(
        content=resp.content,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="podcast_{podcast_id}.mp3"'},
    )


@router.delete("/{podcast_id}")
async def delete_podcast(
    podcast_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a podcast and its audio from storage."""
    from app.services.storage import delete_audio

    result = await db.execute(
        select(Podcast).where(Podcast.id == uuid.UUID(podcast_id))
    )
    podcast = result.scalar_one_or_none()
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast not found")

    check_owner_or_admin(podcast.user_id, user)

    # Delete audio from Supabase Storage
    storage_key = f"{podcast_id}.mp3"
    await delete_audio(storage_key)

    # Delete DB record
    await db.delete(podcast)
    await db.commit()

    return {"status": "deleted", "paper_id": str(podcast.paper_id), "voice_mode": podcast.voice_mode}


@router.get("")
async def list_podcasts(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    search: str | None = None,
    podcast_type: str | None = Query(None, pattern="^(paper|digest)$"),
    voice_mode: str | None = Query(None, pattern="^(single|dual)$"),
    sort: str | None = Query(None, pattern="^(newest|oldest|longest|shortest)$"),
) -> list[dict]:
    """List all generated podcasts with collection info."""
    from sqlalchemy import or_

    # Build shared filters
    base_filters = [Podcast.audio_path.isnot(None), Podcast.user_id == user["id"]]
    if voice_mode:
        base_filters.append(Podcast.voice_mode == voice_mode)

    # Determine sort order
    if sort == "oldest":
        order = Podcast.generated_at.asc()
    elif sort == "longest":
        order = Podcast.duration_seconds.desc().nulls_last()
    elif sort == "shortest":
        order = Podcast.duration_seconds.asc().nulls_last()
    else:  # newest (default)
        order = Podcast.generated_at.desc()

    # Fetch paper-based podcasts (with join)
    paper_rows = []
    if podcast_type != "digest":
        paper_query = (
            select(Podcast, Paper.title, Paper.journal)
            .join(Paper, Podcast.paper_id == Paper.id)
            .where(
                *base_filters,
                or_(Podcast.podcast_type == "paper", Podcast.podcast_type.is_(None)),
            )
        )
        if search:
            term = f"%{search}%"
            paper_query = paper_query.where(
                Paper.title.ilike(term) | Paper.journal.ilike(term)
            )
        paper_query = paper_query.order_by(order)
        paper_result = await db.execute(paper_query)
        paper_rows = paper_result.all()

    # Fetch digest podcasts (no paper_id)
    digest_rows = []
    if podcast_type != "paper":
        digest_query = (
            select(Podcast)
            .where(
                *base_filters,
                Podcast.podcast_type == "digest",
            )
        )
        if search:
            term = f"%{search}%"
            digest_query = digest_query.where(
                Podcast.title.ilike(term)
            )
        digest_query = digest_query.order_by(order)
        digest_result = await db.execute(digest_query)
        digest_rows = digest_result.scalars().all()

    # Bulk fetch papers included in digest podcasts
    digest_ids = [p.id for p in digest_rows]
    digest_papers_map: dict[str, list[dict]] = {}
    if digest_ids:
        from app.models.paper_score import PaperScore
        dp_query = (
            select(
                DigestLog.podcast_id,
                Paper.id,
                Paper.title,
                Paper.journal,
                func.max(PaperScore.relevance_score).label("relevance_score"),
                PaperFavorite.favorited_at,
            )
            .join(Paper, DigestLog.paper_id == Paper.id)
            .outerjoin(
                PaperScore,
                (PaperScore.paper_id == Paper.id) & (PaperScore.user_id == user["id"]),
            )
            .outerjoin(
                PaperFavorite,
                (PaperFavorite.paper_id == Paper.id) & (PaperFavorite.user_id == user["id"]),
            )
            .where(DigestLog.podcast_id.in_(digest_ids))
            .group_by(DigestLog.podcast_id, Paper.id, Paper.title, Paper.journal, PaperFavorite.favorited_at)
            .order_by(func.max(PaperScore.relevance_score).desc().nulls_last())
        )
        dp_result = await db.execute(dp_query)
        for podcast_id, paper_id, title, journal, score, fav_at in dp_result.all():
            digest_papers_map.setdefault(str(podcast_id), []).append({
                "id": str(paper_id),
                "title": title,
                "journal": journal,
                "relevance_score": float(score) if score is not None else None,
                "is_favorite": fav_at is not None,
            })

    # Bulk fetch collections for paper-based podcasts
    paper_ids = list({podcast.paper_id for podcast, _, _ in paper_rows if podcast.paper_id})
    collections_map: dict[str, list[dict]] = {}
    if paper_ids:
        col_result = await db.execute(
            select(CollectionPaper.paper_id, Collection.id, Collection.name, Collection.color)
            .join(Collection, Collection.id == CollectionPaper.collection_id)
            .where(CollectionPaper.paper_id.in_(paper_ids))
        )
        for pid, cid, cname, ccolor in col_result.all():
            collections_map.setdefault(str(pid), []).append({"id": str(cid), "name": cname, "color": ccolor})

    # Bulk fetch creator names
    all_user_ids = list({
        p.user_id for p, _, _ in paper_rows if p.user_id
    } | {
        p.user_id for p in digest_rows if p.user_id
    })
    creator_map: dict[str, str] = {}
    if all_user_ids:
        name_result = await db.execute(
            select(UserProfile.id, UserProfile.full_name).where(UserProfile.id.in_(all_user_ids))
        )
        for uid, name in name_result.all():
            creator_map[str(uid)] = name

    items: list[dict] = []

    # Digest podcasts
    for podcast in digest_rows:
        items.append({
            "id": str(podcast.id),
            "paper_id": None,
            "paper_title": podcast.title or "Digest Podcast",
            "paper_journal": "",
            "voice_mode": podcast.voice_mode,
            "podcast_type": "digest",
            "audio_url": f"/api/v1/podcasts/audio/{podcast.id}",
            "duration_seconds": podcast.duration_seconds,
            "generated_at": podcast.generated_at.isoformat() if podcast.generated_at else None,
            "collections": [],
            "created_by_name": creator_map.get(str(podcast.user_id), "System") if podcast.user_id else "System",
            "digest_papers": digest_papers_map.get(str(podcast.id), []),
        })

    # Paper podcasts
    for podcast, title, journal in paper_rows:
        items.append({
            "id": str(podcast.id),
            "paper_id": str(podcast.paper_id),
            "paper_title": title,
            "paper_journal": journal,
            "voice_mode": podcast.voice_mode,
            "podcast_type": "paper",
            "audio_url": f"/api/v1/podcasts/audio/{podcast.id}",
            "duration_seconds": podcast.duration_seconds,
            "generated_at": podcast.generated_at.isoformat() if podcast.generated_at else None,
            "collections": collections_map.get(str(podcast.paper_id), []),
            "created_by_name": creator_map.get(str(podcast.user_id), "System") if podcast.user_id else "System",
        })

    # Re-sort combined list when mixing digest + paper results
    if sort == "longest":
        items.sort(key=lambda x: x["duration_seconds"] or 0, reverse=True)
    elif sort == "shortest":
        items.sort(key=lambda x: x["duration_seconds"] or 0)
    elif sort == "oldest":
        items.sort(key=lambda x: x["generated_at"] or "")
    else:  # newest
        items.sort(key=lambda x: x["generated_at"] or "", reverse=True)

    return items


@router.post("/{podcast_id}/listen")
async def record_listen(
    podcast_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a podcast listen event."""
    from datetime import datetime, timezone
    from sqlalchemy import update as sql_update

    await db.execute(
        sql_update(Podcast)
        .where(Podcast.id == uuid.UUID(podcast_id))
        .values(
            listen_count=Podcast.listen_count + 1,
            last_listened_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    return {"status": "ok"}
