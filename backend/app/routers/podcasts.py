import json
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db, init_db
import app.database as _db_module
from app.models.collection import Collection, CollectionPaper
from app.models.paper import Paper
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

    return {"status": "generating", "podcast": None}


@router.post("/{paper_id}/generate")
async def generate_podcast_endpoint(
    paper_id: str,
    req: GenerateRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Start podcast generation as a background task."""
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


@router.get("")
async def list_podcasts(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all generated podcasts with collection info."""
    result = await db.execute(
        select(Podcast, Paper.title, Paper.journal)
        .join(Paper, Podcast.paper_id == Paper.id)
        .where(Podcast.audio_path.isnot(None))
        .order_by(Podcast.generated_at.desc())
    )
    rows = result.all()

    # Bulk fetch collections for all podcast papers
    paper_ids = list({podcast.paper_id for podcast, _, _ in rows})
    collections_map: dict[str, list[dict]] = {}
    if paper_ids:
        col_result = await db.execute(
            select(CollectionPaper.paper_id, Collection.id, Collection.name, Collection.color)
            .join(Collection, Collection.id == CollectionPaper.collection_id)
            .where(CollectionPaper.paper_id.in_(paper_ids))
        )
        for pid, cid, cname, ccolor in col_result.all():
            collections_map.setdefault(str(pid), []).append({"id": str(cid), "name": cname, "color": ccolor})

    return [
        {
            "id": str(podcast.id),
            "paper_id": str(podcast.paper_id),
            "paper_title": title,
            "paper_journal": journal,
            "voice_mode": podcast.voice_mode,
            "audio_url": f"/api/v1/podcasts/audio/{podcast.id}",
            "duration_seconds": podcast.duration_seconds,
            "generated_at": podcast.generated_at.isoformat() if podcast.generated_at else None,
            "collections": collections_map.get(str(podcast.paper_id), []),
        }
        for podcast, title, journal in rows
    ]
