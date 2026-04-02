import json
import os
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db, init_db, async_session_factory
from app.models.paper import Paper
from app.models.podcast import Podcast
from app.services.podcast import generate_podcast

router = APIRouter(prefix="/api/v1/podcasts", tags=["podcasts"])


class GenerateRequest(BaseModel):
    voice_mode: str = "single"  # 'single' | 'dual'


async def _generate_in_background(
    paper_id: str,
    podcast_id: str,
    title: str,
    summary: str,
    voice_mode: str,
) -> None:
    """Background task to generate podcast audio."""
    import logging
    logger = logging.getLogger(__name__)

    if async_session_factory is None:
        init_db()

    async with async_session_factory() as db:
        try:
            output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "podcasts_output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{podcast_id}.mp3")

            script, audio_path, duration = await generate_podcast(
                title=title,
                summary=summary,
                voice_mode=voice_mode,
                output_path=output_path,
            )

            # Update podcast record
            result = await db.execute(
                select(Podcast).where(Podcast.id == uuid.UUID(podcast_id))
            )
            podcast = result.scalar_one_or_none()
            if podcast:
                podcast.script = script
                podcast.audio_path = audio_path
                podcast.duration_seconds = duration
                await db.commit()
                logger.info(f"Podcast {podcast_id} generated: {duration}s")

        except Exception as e:
            logger.exception(f"Podcast generation failed for {podcast_id}: {e}")
            # Mark as failed by clearing audio_path
            result = await db.execute(
                select(Podcast).where(Podcast.id == uuid.UUID(podcast_id))
            )
            podcast = result.scalar_one_or_none()
            if podcast:
                podcast.script = f"ERROR: {str(e)}"
                await db.commit()


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

    if podcast.audio_path and os.path.exists(podcast.audio_path):
        return {
            "status": "ready",
            "podcast": {
                "id": str(podcast.id),
                "paper_id": str(podcast.paper_id),
                "voice_mode": podcast.voice_mode,
                "audio_url": f"/api/v1/podcasts/audio/{podcast.id}",
                "duration_seconds": podcast.duration_seconds,
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
    background_tasks: BackgroundTasks,
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
                if key in summary_data:
                    parts.append(summary_data[key])
            summary_text = " ".join(parts)
        except json.JSONDecodeError:
            summary_text = paper.summary

    if not summary_text and paper.abstract:
        summary_text = paper.abstract

    if not summary_text:
        raise HTTPException(status_code=400, detail="Paper has no summary or abstract to generate podcast from")

    # Create podcast record (placeholder)
    podcast = Podcast(
        id=uuid.uuid4(),
        paper_id=uuid.UUID(paper_id),
        user_id=uuid.UUID(user["id"]),
        voice_mode=req.voice_mode,
    )
    db.add(podcast)
    await db.commit()

    # Start background generation
    background_tasks.add_task(
        _generate_in_background,
        paper_id=paper_id,
        podcast_id=str(podcast.id),
        title=paper.title,
        summary=summary_text,
        voice_mode=req.voice_mode,
    )

    return {"status": "generating", "podcast_id": str(podcast.id)}


@router.get("/audio/{podcast_id}")
async def serve_audio(
    podcast_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve the podcast MP3 file."""
    from fastapi.responses import FileResponse

    result = await db.execute(
        select(Podcast).where(Podcast.id == uuid.UUID(podcast_id))
    )
    podcast = result.scalar_one_or_none()

    if not podcast or not podcast.audio_path or not os.path.exists(podcast.audio_path):
        raise HTTPException(status_code=404, detail="Audio not found")

    return FileResponse(
        podcast.audio_path,
        media_type="audio/mpeg",
        filename=f"podcast_{podcast_id}.mp3",
    )


@router.get("")
async def list_podcasts(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all generated podcasts."""
    result = await db.execute(
        select(Podcast, Paper.title, Paper.journal)
        .join(Paper, Podcast.paper_id == Paper.id)
        .where(Podcast.audio_path.isnot(None))
        .order_by(Podcast.generated_at.desc())
    )
    rows = result.all()
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
        }
        for podcast, title, journal in rows
    ]
