"""Public podcast RSS feed endpoint — no auth required (token in URL acts as auth)."""

from datetime import timezone
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.podcast import Podcast
from app.models.user_profile import UserProfile

router = APIRouter(tags=["feed"])

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def _rfc2822(dt) -> str:
    """Format a datetime as RFC 2822 for RSS <pubDate>."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _format_duration(seconds: int | None) -> str:
    if not seconds:
        return "0:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _build_feed_xml(profile: UserProfile, podcasts: list[Podcast]) -> bytes:
    """Build a podcast RSS XML feed."""
    rss = Element("rss", version="2.0")
    rss.set("xmlns:itunes", ITUNES_NS)

    channel = SubElement(rss, "channel")

    # Channel metadata
    title = profile.podcast_feed_title or f"LitOrbit Digest — {profile.full_name}"
    SubElement(channel, "title").text = title
    SubElement(channel, "description").text = (
        profile.podcast_feed_description
        or "AI-curated research digest podcasts powered by LitOrbit"
    )
    SubElement(channel, "language").text = "en"
    SubElement(channel, f"{{{ITUNES_NS}}}author").text = (
        profile.podcast_feed_author or profile.full_name
    )
    SubElement(channel, f"{{{ITUNES_NS}}}explicit").text = "false"

    # Cover art
    if profile.podcast_feed_cover_url:
        img = SubElement(channel, f"{{{ITUNES_NS}}}image")
        img.set("href", profile.podcast_feed_cover_url)

    # Category
    cat = SubElement(channel, f"{{{ITUNES_NS}}}category")
    cat.set("text", "Science")

    # Episodes (newest first)
    for pod in podcasts:
        if not pod.audio_path:
            continue

        item = SubElement(channel, "item")
        SubElement(item, "title").text = pod.title or "Digest Podcast"
        SubElement(item, "description").text = (
            f"{pod.voice_mode.capitalize()} voice digest podcast"
        )

        enclosure = SubElement(item, "enclosure")
        enclosure.set("url", pod.audio_path)
        enclosure.set("type", "audio/mpeg")
        enclosure.set("length", "0")

        SubElement(item, "pubDate").text = _rfc2822(pod.generated_at)
        SubElement(item, "guid").text = str(pod.id)
        SubElement(item, f"{{{ITUNES_NS}}}duration").text = _format_duration(
            pod.duration_seconds
        )
        SubElement(item, f"{{{ITUNES_NS}}}explicit").text = "false"

    return tostring(rss, encoding="unicode", xml_declaration=True).encode("utf-8")


@router.get("/api/v1/feed/{token}.xml")
async def podcast_feed(token: str, db: AsyncSession = Depends(get_db)):
    """Public RSS feed for a user's digest podcasts. The token in the URL acts as auth."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.podcast_feed_token == token)
    )
    profile = result.scalar_one_or_none()

    if not profile or not profile.podcast_feed_enabled:
        raise HTTPException(status_code=404, detail="Feed not found")

    # Fetch digest podcasts for this user, newest first
    pods_result = await db.execute(
        select(Podcast)
        .where(
            Podcast.user_id == profile.id,
            Podcast.podcast_type == "digest",
            Podcast.audio_path.isnot(None),
        )
        .order_by(Podcast.generated_at.desc())
        .limit(50)
    )
    podcasts = pods_result.scalars().all()

    xml_bytes = _build_feed_xml(profile, podcasts)

    return Response(
        content=xml_bytes,
        media_type="application/rss+xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=900"},
    )
