"""CRUD and feed validation for news sources."""

import logging
import uuid
from datetime import datetime, timezone

import feedparser
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_source import NewsSource

logger = logging.getLogger(__name__)


async def get_enabled_sources(db: AsyncSession) -> list[NewsSource]:
    result = await db.execute(
        select(NewsSource).where(NewsSource.enabled == True)
    )
    return list(result.scalars().all())


async def get_all_sources(db: AsyncSession) -> list[NewsSource]:
    result = await db.execute(select(NewsSource).order_by(NewsSource.name))
    return list(result.scalars().all())


async def get_source(db: AsyncSession, source_id: uuid.UUID) -> NewsSource | None:
    result = await db.execute(
        select(NewsSource).where(NewsSource.id == source_id)
    )
    return result.scalar_one_or_none()


async def create_source(db: AsyncSession, **kwargs) -> NewsSource:
    source = NewsSource(**kwargs)
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


async def update_source(db: AsyncSession, source_id: uuid.UUID, **kwargs) -> NewsSource | None:
    source = await get_source(db, source_id)
    if not source:
        return None
    for key, value in kwargs.items():
        setattr(source, key, value)
    await db.commit()
    await db.refresh(source)
    return source


async def delete_source(db: AsyncSession, source_id: uuid.UUID) -> bool:
    source = await get_source(db, source_id)
    if not source:
        return False
    await db.delete(source)
    await db.commit()
    return True


async def mark_fetched(
    db: AsyncSession,
    source_id: uuid.UUID,
    status: str,
    error: str | None = None,
) -> None:
    await db.execute(
        update(NewsSource)
        .where(NewsSource.id == source_id)
        .values(
            last_fetched_at=datetime.now(timezone.utc),
            last_fetch_status=status,
            last_fetch_error=error,
        )
    )
    await db.commit()


async def validate_feed(url: str) -> dict:
    """Fetch and parse a feed URL, return validation info.

    On parse failure also returns the HTTP status, final URL after
    redirects, content-type, and a snippet of the response body so the
    UI can surface why the host returned non-RSS (bot challenge,
    geoblock, redirect to homepage, etc.).
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "Accept-Language": "en-US,en;q=0.9",
            })
            resp.raise_for_status()

        diagnostics = {
            "http_status": resp.status_code,
            "final_url": str(resp.url),
            "content_type": resp.headers.get("content-type"),
            "body_snippet": resp.text[:300],
        }

        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            return {
                "valid": False,
                "item_count": 0,
                "latest_pub_at": None,
                "parse_errors": [str(feed.bozo_exception)],
                **diagnostics,
            }

        latest_pub = None
        if feed.entries:
            for entry in feed.entries:
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    if latest_pub is None or dt > latest_pub:
                        latest_pub = dt

        return {
            "valid": True,
            "item_count": len(feed.entries),
            "latest_pub_at": latest_pub.isoformat() if latest_pub else None,
            "parse_errors": [str(feed.bozo_exception)] if feed.bozo else [],
            **diagnostics,
        }

    except httpx.HTTPError as e:
        return {
            "valid": False,
            "item_count": 0,
            "latest_pub_at": None,
            "parse_errors": [str(e)],
            "http_status": getattr(getattr(e, "response", None), "status_code", None),
            "final_url": str(getattr(getattr(e, "request", None), "url", url)),
            "content_type": None,
            "body_snippet": None,
        }
