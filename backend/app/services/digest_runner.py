"""Digest runner — sends personalised digest emails and standalone podcast digests."""

import asyncio
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
from app.models.digest_run import DigestRun
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


def _lookback_days(frequency: str) -> float:
    """Lookback window in days.

    Daily uses 1.5 days (36 hours) instead of exactly 24 hours to avoid
    losing papers to timing drift between consecutive pipeline runs.
    Deduplication via DigestLog ensures no paper is sent twice.
    """
    return 1.5 if frequency == "daily" else 7


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
    source: str = "email",
) -> list[tuple[Paper, float]]:
    """Fetch top-N papers for this user that haven't been sent in a previous digest.

    Args:
        source: "email" or "podcast" — dedup is per-source so the same paper
                can appear in both an email digest and a standalone podcast digest.

    Returns list of (Paper, relevance_score) tuples ordered by score desc.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=_lookback_days(frequency))

    # Paper IDs already sent to this user for this source
    sent_result = await db.execute(
        select(DigestLog.paper_id).where(
            DigestLog.user_id == user_id,
            DigestLog.source == source,
        )
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


def _build_paper_dicts(paper_score_pairs: list[tuple[Paper, float]]) -> tuple[list[dict], list[dict]]:
    """Build email_papers and podcast_papers dicts from paper/score tuples."""
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
    return email_papers, podcast_papers


async def _generate_and_upload_podcast(
    papers_data: list[dict[str, Any]],
    user: UserProfile,
    frequency: str,
    voice_mode: str = "dual",
    podcast_type: str = "digest",
) -> Podcast | None:
    """Generate digest podcast audio, upload to storage, return Podcast record."""

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
            podcast_type=podcast_type,
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


async def _already_ran_today(db: AsyncSession, user_id: uuid.UUID, source: str) -> bool:
    """Check if a digest was already processed for this user/source today."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(DigestLog.id)
        .where(
            DigestLog.user_id == user_id,
            DigestLog.source == source,
            DigestLog.sent_at >= today_start,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _find_reusable_podcast(
    db: AsyncSession,
    user_id: uuid.UUID,
    frequency: str,
) -> Podcast | None:
    """Find a digest podcast generated today with the same frequency (same lookback window).

    Used for smart reuse: if both email and podcast digests share the same
    frequency, we only generate the podcast once.
    """
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    freq_label = "Daily" if frequency == "daily" else "Weekly"
    result = await db.execute(
        select(Podcast).where(
            Podcast.user_id == user_id,
            Podcast.podcast_type.in_(["digest", "standalone_digest"]),
            Podcast.generated_at >= today_start,
            Podcast.title.startswith(freq_label),
        ).limit(1)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Product 1: Email Digest
# ---------------------------------------------------------------------------

async def send_email_digest_for_user(
    db: AsyncSession,
    user: UserProfile,
) -> dict[str, Any]:
    """Send a digest email (with optional podcast) to a single user."""
    from app.services.settings import get_system_settings
    sys_settings = await get_system_settings(db)

    frequency = user.digest_frequency or "weekly"

    # Guard: skip if already sent today
    if await _already_ran_today(db, user.id, "email"):
        logger.info(f"Email digest already sent to {user.full_name} today, skipping")
        return {"user": user.full_name, "papers": 0, "sent": False, "skipped_duplicate": True}

    top_n = user.digest_top_papers or _default_top(frequency)
    top_n = min(top_n, sys_settings.max_papers_per_digest)

    # 1. Fetch papers
    paper_score_pairs = await _get_digest_papers(db, user.id, frequency, top_n, source="email")
    email_papers, podcast_papers = _build_paper_dicts(paper_score_pairs)

    # 2. Fetch shared papers
    shared_papers = await _get_shared_papers(db, user.id, frequency)

    # 3. Optionally generate/reuse podcast for email
    settings = get_settings()
    podcast_info = None
    podcast_record = None

    if email_papers and user.digest_podcast_enabled and sys_settings.digest_podcast_enabled_global:
        voice_mode = user.digest_podcast_voice_mode or "dual"
        # Try to reuse a podcast already generated today with the same frequency
        existing = await _find_reusable_podcast(db, user.id, frequency)
        if existing:
            logger.info(f"Reusing existing podcast for {user.full_name} email digest")
            podcast_record = existing
        else:
            logger.info(f"Generating email digest podcast for {user.full_name} ({len(podcast_papers)} papers)")
            podcast_record = await _generate_and_upload_podcast(
                podcast_papers, user, frequency,
                voice_mode=voice_mode, podcast_type="digest",
            )
            if podcast_record:
                db.add(podcast_record)
                await db.flush()

        if podcast_record:
            duration_min = (podcast_record.duration_seconds or 0) // 60
            duration_sec = (podcast_record.duration_seconds or 0) % 60
            voice_label = "Dual voice" if podcast_record.voice_mode == "dual" else "Single voice"
            podcast_info = {
                "title": podcast_record.title,
                "voice_label": voice_label,
                "duration_label": f"{duration_min}m {duration_sec}s",
                "play_url": f"{settings.frontend_url}/podcasts?play={podcast_record.id}",
            }

    # 4. Generate and send email
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
    if not sent:
        logger.warning(f"Email failed for {user.full_name}, but podcast/logs will still be saved")

    # 5. Log papers for dedup
    for paper, _score in paper_score_pairs:
        db.add(DigestLog(
            id=uuid.uuid4(),
            user_id=user.id,
            paper_id=paper.id,
            digest_type=frequency,
            source="email",
            podcast_id=podcast_record.id if podcast_record else None,
        ))
    await db.commit()

    return {
        "user": user.full_name,
        "papers": len(email_papers),
        "shared": len(shared_papers),
        "podcast": podcast_record is not None,
        "sent": sent,
        "email_failed": not sent,
    }


# ---------------------------------------------------------------------------
# Product 2: Standalone Podcast Digest
# ---------------------------------------------------------------------------

async def send_podcast_digest_for_user(
    db: AsyncSession,
    user: UserProfile,
) -> dict[str, Any]:
    """Generate a standalone podcast digest for a user (no email)."""
    from app.services.settings import get_system_settings
    sys_settings = await get_system_settings(db)

    frequency = user.podcast_digest_frequency or "weekly"

    # Guard: skip if already generated today
    if await _already_ran_today(db, user.id, "podcast"):
        logger.info(f"Podcast digest already generated for {user.full_name} today, skipping")
        return {"user": user.full_name, "papers": 0, "sent": False, "skipped_duplicate": True}

    top_n = user.podcast_digest_top_papers or _default_top(frequency)
    top_n = min(top_n, sys_settings.max_papers_per_digest)

    # 1. Fetch papers (dedup against podcast source only)
    paper_score_pairs = await _get_digest_papers(db, user.id, frequency, top_n, source="podcast")
    _email_papers, podcast_papers = _build_paper_dicts(paper_score_pairs)

    if not podcast_papers:
        logger.info(f"No papers for {user.full_name} standalone podcast digest, skipping")
        return {"user": user.full_name, "papers": 0, "sent": False}

    # 2. Try to reuse a podcast already generated today with the same frequency
    voice_mode = user.podcast_digest_voice_mode or "dual"
    existing = await _find_reusable_podcast(db, user.id, frequency)
    if existing:
        logger.info(f"Reusing existing podcast for {user.full_name} standalone digest")
        podcast_record = existing
    else:
        logger.info(f"Generating standalone podcast digest for {user.full_name} ({len(podcast_papers)} papers)")
        podcast_record = await _generate_and_upload_podcast(
            podcast_papers, user, frequency,
            voice_mode=voice_mode, podcast_type="standalone_digest",
        )
        if podcast_record:
            db.add(podcast_record)
            await db.flush()

    if not podcast_record:
        logger.warning(f"Podcast generation failed for {user.full_name}")
        return {"user": user.full_name, "papers": len(podcast_papers), "sent": False}

    # 3. Log papers for dedup
    for paper, _score in paper_score_pairs:
        db.add(DigestLog(
            id=uuid.uuid4(),
            user_id=user.id,
            paper_id=paper.id,
            digest_type=frequency,
            source="podcast",
            podcast_id=podcast_record.id,
        ))
    await db.commit()

    return {
        "user": user.full_name,
        "papers": len(podcast_papers),
        "podcast": True,
        "sent": True,
    }


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

async def send_digest_for_user(
    db: AsyncSession,
    user: UserProfile,
) -> dict[str, Any]:
    """Alias for send_email_digest_for_user (backward compatibility)."""
    return await send_email_digest_for_user(db, user)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def _append_log(db: AsyncSession, run: DigestRun, entry: dict) -> None:
    """Append an entry to the digest run log and persist."""
    run.run_log = [*run.run_log, entry]
    await db.commit()


async def _run_for_product(
    db: AsyncSession,
    product: str,
    frequency: str | None = None,
    skip_day_check: bool = False,
) -> list[dict[str, Any]]:
    """Run digests for a single product ("email" or "podcast").

    Returns list of per-user result dicts.
    """
    run = DigestRun(
        id=uuid.uuid4(),
        frequency=frequency or "all",
        run_type=product,
        started_at=datetime.now(timezone.utc),
        status="running",
        run_log=[],
    )
    db.add(run)
    await db.commit()

    try:
        await _append_log(db, run, {"step": "querying_users", "detail": f"Finding eligible {product} digest users..."})

        # Query eligible users based on product
        if product == "email":
            query = select(UserProfile).where(UserProfile.email_digest_enabled == True)
            if frequency:
                query = query.where(UserProfile.digest_frequency == frequency)
        else:  # podcast
            query = select(UserProfile).where(UserProfile.podcast_digest_enabled == True)
            if frequency:
                query = query.where(UserProfile.podcast_digest_frequency == frequency)

        result = await db.execute(query)
        all_users = result.scalars().all()

        # Filter weekly users by their chosen digest day
        today_name = datetime.now(timezone.utc).strftime("%A").lower()
        users = []
        skipped_day = 0
        for u in all_users:
            if not skip_day_check:
                if product == "email" and u.digest_frequency == "weekly":
                    user_day = (u.digest_day or "monday").lower()
                    if user_day != today_name:
                        skipped_day += 1
                        continue
                elif product == "podcast" and u.podcast_digest_frequency == "weekly":
                    user_day = (u.podcast_digest_day or "monday").lower()
                    if user_day != today_name:
                        skipped_day += 1
                        continue
            users.append(u)

        run.users_total = len(users)
        await _append_log(db, run, {
            "step": "users_found",
            "product": product,
            "eligible": len(users),
            "skipped_day": skipped_day,
        })

        if not users:
            logger.info(f"No users eligible for {product} digest")
            run.status = "success"
            run.completed_at = datetime.now(timezone.utc)
            await _append_log(db, run, {"step": "completed", "detail": "No eligible users"})
            return []

        results = []
        for i, user in enumerate(users):
            try:
                await _append_log(db, run, {
                    "step": "processing_user",
                    "user": user.full_name,
                    "index": i + 1,
                    "total": len(users),
                })

                if product == "email":
                    summary = await asyncio.wait_for(
                        send_email_digest_for_user(db, user),
                        timeout=120,
                    )
                else:
                    summary = await asyncio.wait_for(
                        send_podcast_digest_for_user(db, user),
                        timeout=300,
                    )
                results.append(summary)

                if summary.get("sent"):
                    run.users_sent += 1
                    step = "user_sent"
                elif summary.get("skipped_duplicate"):
                    run.users_skipped += 1
                    step = "user_skipped_duplicate"
                else:
                    run.users_sent += 1
                    step = "user_partial"

                log_entry: dict[str, Any] = {
                    "step": step,
                    "user": user.full_name,
                    "papers": summary.get("papers", 0),
                    "podcast": summary.get("podcast", False),
                }
                if summary.get("email_failed"):
                    log_entry["email_failed"] = True
                await _append_log(db, run, log_entry)

            except Exception as e:
                logger.exception(f"{product.capitalize()} digest failed for {user.full_name}: {e}")
                results.append({"user": user.full_name, "error": str(e), "sent": False})
                run.users_failed += 1
                await _append_log(db, run, {
                    "step": "user_error",
                    "user": user.full_name,
                    "error": str(e),
                })

        run.completed_at = datetime.now(timezone.utc)
        sent_count = sum(1 for r in results if r.get("sent"))
        failed_count = run.users_failed + sum(1 for r in results if r.get("email_failed"))

        run.status = "partial" if failed_count > 0 else "success"

        await _append_log(db, run, {
            "step": "completed",
            "sent": sent_count,
            "total": len(users),
            "failed": failed_count,
            "skipped": run.users_skipped,
        })
        logger.info(f"{product.capitalize()} digest run complete: {sent_count}/{len(users)} processed")
        return results

    except Exception as e:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = str(e)
        await db.commit()
        logger.exception(f"{product.capitalize()} digest run failed: {e}")
        raise


async def run_digests(
    db: AsyncSession,
    frequency: str | None = None,
    skip_day_check: bool = False,
    product: str = "all",
) -> list[dict[str, Any]]:
    """Send digests to all eligible users.

    Args:
        frequency: If provided, only send to users with this frequency setting.
        skip_day_check: If True, skip the weekly day-of-week filter (manual triggers).
        product: "email", "podcast", or "all" (runs email first, then podcast).
    """
    results = []

    if product in ("email", "all"):
        email_results = await _run_for_product(db, "email", frequency, skip_day_check)
        results.extend(email_results)

    if product in ("podcast", "all"):
        podcast_results = await _run_for_product(db, "podcast", frequency, skip_day_check)
        results.extend(podcast_results)

    return results
