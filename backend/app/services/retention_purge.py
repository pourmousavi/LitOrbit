"""Retention purge for news items.

Deletes news items older than retention_days that are NOT:
- Starred by any user
- Sent to ScholarLib
- Rated thumbs-up by any user

Default retention: 90 days for non-starred items.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_item import NewsItem
from app.models.user_interaction import UserInteraction

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 90


async def purge_expired_news(db: AsyncSession, retention_days: int = DEFAULT_RETENTION_DAYS) -> dict:
    """Delete expired news items that aren't protected.

    Returns stats dict.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    # Find protected item IDs (starred, sent to ScholarLib, or thumbs-up rated)
    starred_ids = set()
    result = await db.execute(
        select(UserInteraction.content_id).where(
            UserInteraction.content_type == "news",
            UserInteraction.event_type == "starred",
        )
    )
    starred_ids.update(row[0] for row in result.all())

    thumbs_up_ids = set()
    result = await db.execute(
        select(UserInteraction.content_id).where(
            UserInteraction.content_type == "news",
            UserInteraction.event_type == "rated",
        )
    )
    for row in result.all():
        # Only protect thumbs-up, not thumbs-down
        ui = await db.get(UserInteraction, row[0])
        if ui and ui.event_value and ui.event_value.get("rating") == "thumbs_up":
            thumbs_up_ids.add(ui.content_id)

    scholarlib_ids = set()
    result = await db.execute(
        select(NewsItem.id).where(
            NewsItem.scholarlib_ref_id.isnot(None),
        )
    )
    scholarlib_ids.update(row[0] for row in result.all())

    protected_ids = starred_ids | thumbs_up_ids | scholarlib_ids

    # Find expired items
    expired_query = select(NewsItem).where(
        NewsItem.created_at < cutoff,
    )
    if protected_ids:
        expired_query = expired_query.where(NewsItem.id.not_in(protected_ids))

    # Also skip items with retention_until = None (indefinite retention)
    expired_query = expired_query.where(
        (NewsItem.retention_until.isnot(None)) | (NewsItem.retention_until <= datetime.now(timezone.utc))
    )

    expired_items = (await db.execute(expired_query)).scalars().all()

    deleted_count = 0
    for item in expired_items:
        await db.delete(item)
        deleted_count += 1

    await db.commit()

    logger.info(
        "Retention purge: deleted %d news items older than %d days (%d protected)",
        deleted_count, retention_days, len(protected_ids),
    )
    return {
        "deleted": deleted_count,
        "protected": len(protected_ids),
        "retention_days": retention_days,
    }
