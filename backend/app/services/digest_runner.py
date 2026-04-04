"""Digest runner — sends personalised digest emails with optional podcast."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.digest_log import DigestLog
from app.models.paper import Paper
from app.models.paper_score import PaperScore
from app.models.podcast import Podcast
from app.models.share import Share
from app.models.user_profile import UserProfile
from app.services.digest_podcast import generate_digest_podcast
from app.services.email_digest import generate_digest_html, send_digest_email
from app.services.storage import upload_audio

logger = logging.getLogger(__name__)

# Default top-N papers for the digest podcast
DEFAULT_DAILY_TOP = 3
DEFAULT_WEEKLY_TOP = 10


def _default_top(frequency: str) -> int:
    return DEFAULT_DAILY_TOP if frequency == "daily" else DEFAULT_WEEKLY_TOP


def _lookback_days(frequency: str) -> int:
    return 1 if frequency == "daily" else 7


def _summary_excerpt(summary_json: str | None) -> str | None:
    """Extract a short human-readable excerpt from a paper's JSON summary."""
    if not summary_json:
        return None
    try:
        data = json.loads(summary_json)
        gap = data.get("research_gap", "")
        findings = data.get("key_findings", "")
        if gap:
            return gap[:300]
        if findings:
            return findings[:300]
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def _summary_text(paper: Paper) -> str:
    """Get the full summary text for podcast generation."""
    if paper.summary:
        try:
            data = json.loads(paper.summary)
            parts = []
            for key in ("research_gap", "methodology", "key_findings", "relevance_to_energy_group"):
                val = data.get(key)
                if val and isinstance(val, str):
                    parts.append(val)
            if parts:
                return " ".join(parts)
        except json.JSONDecodeError:
            return paper.summary
    return paper.abstract or ""


async def _get_digest_papers(
    db: AsyncSession,
    user_id: uuid.UUID,
    frequency: str,
    top_n: int,
) -> list[tuple[Paper, float]]:
    """Fetch top-N papers for this user that haven't been sent in a previous digest.

    Returns list of (Paper, relevance_score) tuples ordered by score desc.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=_lookback_days(frequency))

    # Paper IDs already sent to this user
    sent_result = await db.execute(
        select(DigestLog.paper_id).where(DigestLog.user_id == user_id)
    )
    sent_paper_ids = {row[0] for row in sent_result.all()}

    # Top scored papers from the lookback window
    query = (
        select(Paper, PaperScore.relevance_score)
        .join(PaperScore, PaperScore.paper_id == Paper.id)
        .where(
            PaperScore.user_id == user_id,
            PaperScore.relevance_score >= 5.0,
            Paper.created_at >= cutoff,
        )
        .order_by(PaperScore.relevance_score.desc())
    )
    result = await db.execute(query)
    rows = result.all()

    # Filter out already-sent papers
    filtered = [(paper, score) for paper, score in rows if paper.id not in sent_paper_ids]
    return filtered[:top_n]


async def _get_shared_papers(
    db: AsyncSession,
    user_id: uuid.UUID,
    frequency: str,
) -> list[dict[str, Any]]:
    """Fetch papers shared with this user in the lookback window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_lookback_days(frequency))

    result = await db.execute(
        select(Share, Paper.title, UserProfile.full_name)
        .join(Paper, Paper.id == Share.paper_id)
        .join(UserProfile, UserProfile.id == Share.shared_by)
        .where(
            Share.shared_with == user_id,
            Share.shared_at >= cutoff,
        )
        .order_by(Share.shared_at.desc())
    )

    return [
        {
            "paper_title": title,
            "sharer_name": sharer_name,
            "annotation": share.annotation,
        }
        for share, title, sharer_name in result.all()
    ]


async def _generate_and_upload_podcast(
    papers_data: list[dict[str, Any]],
    user: UserProfile,
    frequency: str,
) -> Podcast | None:
    """Generate digest podcast audio, upload to storage, return Podcast record."""
    voice_mode = user.digest_podcast_voice_mode or "dual"

    # User custom prompt / voices
    custom_prompt = None
    custom_voices: dict[str, str] = {}
    if voice_mode == "single" and user.single_voice_prompt:
        custom_prompt = user.single_voice_prompt
    elif voice_mode == "dual" and user.dual_voice_prompt:
        custom_prompt = user.dual_voice_prompt

    if voice_mode == "single" and user.single_voice_id:
        custom_voices["single"] = user.single_voice_id
    elif voice_mode == "dual":
        if user.dual_voice_alex_id:
            custom_voices["alex"] = user.dual_voice_alex_id
        if user.dual_voice_sam_id:
            custom_voices["sam"] = user.dual_voice_sam_id

    podcast_id = uuid.uuid4()
    output_dir = os.path.join("/tmp", "litorbit_podcasts")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{podcast_id}.mp3")

    try:
        script, audio_path, duration = await generate_digest_podcast(
            papers=papers_data,
            voice_mode=voice_mode,
            output_path=output_path,
            custom_prompt=custom_prompt,
            custom_voices=custom_voices or None,
        )

        storage_key = f"{podcast_id}.mp3"
        public_url = await upload_audio(audio_path, storage_key)

        if not public_url:
            logger.error(f"Failed to upload digest podcast for user {user.id}")
            return None

        freq_label = "Daily" if frequency == "daily" else "Weekly"
        today_str = datetime.now(timezone.utc).strftime("%b %d, %Y")

        podcast = Podcast(
            id=podcast_id,
            paper_id=None,
            user_id=user.id,
            voice_mode=voice_mode,
            podcast_type="digest",
            title=f"{freq_label} Digest — {today_str}",
            script=script,
            audio_path=public_url,
            duration_seconds=duration,
        )

        # Clean up temp file
        if os.path.exists(audio_path):
            os.unlink(audio_path)

        return podcast

    except Exception as e:
        logger.exception(f"Digest podcast generation failed for user {user.id}: {e}")
        if os.path.exists(output_path):
            os.unlink(output_path)
        return None


async def send_digest_for_user(
    db: AsyncSession,
    user: UserProfile,
) -> dict[str, Any]:
    """Send a digest email (with optional podcast) to a single user.

    Returns a summary dict.
    """
    frequency = user.digest_frequency or "weekly"
    top_n = user.digest_top_papers or _default_top(frequency)

    # 1. Fetch papers not previously sent
    paper_score_pairs = await _get_digest_papers(db, user.id, frequency, top_n)
    if not paper_score_pairs:
        logger.info(f"No new papers for {user.full_name} ({frequency} digest), skipping")
        return {"user": user.full_name, "papers": 0, "sent": False}

    # 2. Build paper dicts for email + podcast
    email_papers = []
    podcast_papers = []
    for paper, score in paper_score_pairs:
        email_papers.append({
            "title": paper.title,
            "journal": paper.journal,
            "score": score,
            "summary_excerpt": _summary_excerpt(paper.summary),
        })
        podcast_papers.append({
            "title": paper.title,
            "journal": paper.journal,
            "score": score,
            "summary": _summary_text(paper),
            "abstract": paper.abstract or "",
        })

    # 3. Fetch shared papers
    shared_papers = await _get_shared_papers(db, user.id, frequency)

    # 4. Optionally generate digest podcast
    settings = get_settings()
    podcast_info = None
    podcast_record = None

    if user.digest_podcast_enabled:
        logger.info(f"Generating digest podcast for {user.full_name} ({len(podcast_papers)} papers)")
        podcast_record = await _generate_and_upload_podcast(podcast_papers, user, frequency)
        if podcast_record:
            db.add(podcast_record)
            await db.flush()  # get the id assigned

            duration_min = (podcast_record.duration_seconds or 0) // 60
            duration_sec = (podcast_record.duration_seconds or 0) % 60
            voice_label = "Dual voice" if podcast_record.voice_mode == "dual" else "Single voice"

            podcast_info = {
                "title": podcast_record.title,
                "voice_label": voice_label,
                "duration_label": f"{duration_min}m {duration_sec}s",
                "play_url": f"{settings.frontend_url}/podcasts?play={podcast_record.id}",
            }

    # 5. Generate and send email
    freq_label = "Daily" if frequency == "daily" else "Weekly"
    today_str = datetime.now(timezone.utc).strftime("%b %d")
    subject = f"LitOrbit {freq_label} Digest — {today_str}"

    html = generate_digest_html(
        user_name=user.full_name,
        papers=email_papers,
        shared_papers=shared_papers,
        dashboard_url=settings.frontend_url,
        unsubscribe_url=f"{settings.frontend_url}/profile",
        frequency=frequency,
        podcast=podcast_info,
    )

    sent = send_digest_email(user.email, subject, html)

    # 6. Log papers to prevent future duplicates
    if sent:
        for paper, _score in paper_score_pairs:
            db.add(DigestLog(
                id=uuid.uuid4(),
                user_id=user.id,
                paper_id=paper.id,
                digest_type=frequency,
                podcast_id=podcast_record.id if podcast_record else None,
            ))
        await db.commit()

    return {
        "user": user.full_name,
        "papers": len(email_papers),
        "shared": len(shared_papers),
        "podcast": podcast_record is not None,
        "sent": sent,
    }


async def run_digests(
    db: AsyncSession,
    frequency: str | None = None,
) -> list[dict[str, Any]]:
    """Send digest emails to all eligible users.

    Args:
        frequency: If provided, only send to users with this frequency setting.
                   If None, send to all users whose frequency matches
                   (daily users get daily, weekly users get weekly).
    """
    query = select(UserProfile).where(UserProfile.email_digest_enabled == True)
    if frequency:
        query = query.where(UserProfile.digest_frequency == frequency)

    result = await db.execute(query)
    all_users = result.scalars().all()

    # Filter weekly users by their chosen digest day
    today_name = datetime.now(timezone.utc).strftime("%A").lower()  # e.g. "monday"
    users = []
    for u in all_users:
        if u.digest_frequency == "weekly":
            user_day = (u.digest_day or "monday").lower()
            if user_day != today_name:
                logger.info(f"Skipping {u.full_name}: weekly digest day is {user_day}, today is {today_name}")
                continue
        users.append(u)

    if not users:
        logger.info("No users eligible for digest")
        return []

    results = []
    for user in users:
        try:
            summary = await send_digest_for_user(db, user)
            results.append(summary)
        except Exception as e:
            logger.exception(f"Digest failed for {user.full_name}: {e}")
            results.append({"user": user.full_name, "error": str(e), "sent": False})

    sent_count = sum(1 for r in results if r.get("sent"))
    logger.info(f"Digest run complete: {sent_count}/{len(users)} emails sent")
    return results
