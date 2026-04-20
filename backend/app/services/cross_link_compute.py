"""Cross-link computation: paper <-> news semantic similarity.

Runs after each daily ingest. For each paper/news item added in the last 24h,
finds the top 3 opposite-type items from the last 14 days with cosine sim > 0.75.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.news_item import NewsItem
from app.models.content_cross_link import ContentCrossLink
from app.services.ranking.embedder import cosine_similarity

logger = logging.getLogger(__name__)

CROSS_LINK_THRESHOLD = 0.75
CROSS_LINK_TOP_K = 3
CROSS_LINK_LOOKBACK = timedelta(days=14)


async def build_cross_links(db: AsyncSession) -> dict:
    """Compute cross-links between recently added papers and news items.

    Returns stats dict with counts.
    """
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_lookback = now - CROSS_LINK_LOOKBACK

    stats = {"papers_checked": 0, "news_checked": 0, "links_created": 0}

    # Get recent papers with embeddings
    recent_papers = (await db.execute(
        select(Paper).where(
            Paper.created_at >= since_24h,
            Paper.embedding.isnot(None),
        )
    )).scalars().all()

    # Get recent news with embeddings (lookback window for matching)
    lookback_news = (await db.execute(
        select(NewsItem).where(
            NewsItem.created_at >= since_lookback,
            NewsItem.embedding.isnot(None),
            NewsItem.is_cluster_primary == True,
        )
    )).scalars().all()

    # Get recent news items (last 24h) for reverse matching
    recent_news = (await db.execute(
        select(NewsItem).where(
            NewsItem.created_at >= since_24h,
            NewsItem.embedding.isnot(None),
            NewsItem.is_cluster_primary == True,
        )
    )).scalars().all()

    # Get papers in lookback window for reverse matching
    lookback_papers = (await db.execute(
        select(Paper).where(
            Paper.created_at >= since_lookback,
            Paper.embedding.isnot(None),
        )
    )).scalars().all()

    # Paper -> News links
    for paper in recent_papers:
        stats["papers_checked"] += 1
        matches = []
        for news in lookback_news:
            sim = cosine_similarity(paper.embedding, news.embedding)
            if sim >= CROSS_LINK_THRESHOLD:
                matches.append((news, sim))

        matches.sort(key=lambda x: x[1], reverse=True)
        for news, sim in matches[:CROSS_LINK_TOP_K]:
            await _upsert_link(db, "paper", paper.id, "news", news.id, sim)
            stats["links_created"] += 1

    # News -> Paper links
    for news in recent_news:
        stats["news_checked"] += 1
        matches = []
        for paper in lookback_papers:
            sim = cosine_similarity(news.embedding, paper.embedding)
            if sim >= CROSS_LINK_THRESHOLD:
                matches.append((paper, sim))

        matches.sort(key=lambda x: x[1], reverse=True)
        for paper, sim in matches[:CROSS_LINK_TOP_K]:
            await _upsert_link(db, "news", news.id, "paper", paper.id, sim)
            stats["links_created"] += 1

    await db.commit()
    logger.info(
        "Cross-links: checked %d papers + %d news, created %d links",
        stats["papers_checked"], stats["news_checked"], stats["links_created"],
    )
    return stats


async def _upsert_link(
    db: AsyncSession,
    src_type: str, src_id: uuid.UUID,
    tgt_type: str, tgt_id: uuid.UUID,
    similarity: float,
) -> None:
    """Insert or update a cross-link."""
    existing = await db.execute(
        select(ContentCrossLink).where(
            ContentCrossLink.source_content_type == src_type,
            ContentCrossLink.source_content_id == src_id,
            ContentCrossLink.target_content_type == tgt_type,
            ContentCrossLink.target_content_id == tgt_id,
        )
    )
    link = existing.scalar_one_or_none()
    if link:
        link.similarity = similarity
        link.computed_at = datetime.now(timezone.utc)
    else:
        db.add(ContentCrossLink(
            source_content_type=src_type,
            source_content_id=src_id,
            target_content_type=tgt_type,
            target_content_id=tgt_id,
            similarity=similarity,
        ))
