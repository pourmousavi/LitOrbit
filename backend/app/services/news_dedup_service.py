"""Deduplication for news items using embedding cosine similarity.

Groups near-duplicate articles into clusters. The highest-authority
source's article becomes the cluster primary (shown in feed).
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.models.news_item import NewsItem
from app.models.news_cluster import NewsCluster
from app.services.ranking.embedder import cosine_similarity, compute_centroid

logger = logging.getLogger(__name__)

COSINE_DUP_THRESHOLD = 0.88
DEDUP_WINDOW_DAYS = 7


async def assign_cluster(
    db: AsyncSession,
    new_item: NewsItem,
    source_authority_weight: float,
) -> None:
    """Assign a news item to an existing or new cluster.

    Finds similar items within the dedup window and merges into a cluster.
    The item with the highest authority_weight becomes the cluster primary.
    """
    if not new_item.embedding:
        # No embedding, create standalone cluster
        cluster = NewsCluster(primary_item_id=new_item.id, member_count=1)
        db.add(cluster)
        await db.flush()
        new_item.primary_cluster_id = cluster.id
        new_item.is_cluster_primary = True
        return

    since = datetime.now(timezone.utc) - timedelta(days=DEDUP_WINDOW_DAYS)

    # Find recent primary items with embeddings
    # (embedding column is deferred; undefer for the cosine_similarity loop below)
    result = await db.execute(
        select(NewsItem)
        .where(
            NewsItem.published_at > since,
            NewsItem.is_cluster_primary == True,
            NewsItem.embedding.isnot(None),
            NewsItem.id != new_item.id,
        )
        .options(undefer(NewsItem.embedding))
    )
    candidates = result.scalars().all()

    # Find similar items
    similar_items = []
    for candidate in candidates:
        sim = cosine_similarity(new_item.embedding, candidate.embedding)
        if sim >= COSINE_DUP_THRESHOLD:
            similar_items.append((candidate, sim))

    if not similar_items:
        # No duplicates found, create new cluster
        cluster = NewsCluster(
            primary_item_id=new_item.id,
            centroid_embedding=new_item.embedding,
            member_count=1,
        )
        db.add(cluster)
        await db.flush()
        new_item.primary_cluster_id = cluster.id
        new_item.is_cluster_primary = True
        return

    # Found duplicates — merge into existing cluster
    # Use the cluster of the most similar item
    best_match, best_sim = max(similar_items, key=lambda x: x[1])
    cluster_id = best_match.primary_cluster_id

    if cluster_id:
        cluster = await db.get(NewsCluster, cluster_id)
    else:
        # Existing item has no cluster yet (shouldn't happen, but handle it)
        cluster = NewsCluster(primary_item_id=best_match.id, member_count=1)
        db.add(cluster)
        await db.flush()
        best_match.primary_cluster_id = cluster.id
        cluster_id = cluster.id

    # Determine primary: highest authority_weight, tiebreak by earliest published_at
    # We need to compare new_item vs current primary. Undefer embedding because
    # we read it below for centroid recompute.
    current_primary = None
    if cluster.primary_item_id:
        current_primary = (await db.execute(
            select(NewsItem)
            .where(NewsItem.id == cluster.primary_item_id)
            .options(undefer(NewsItem.embedding))
        )).scalar_one_or_none()

    new_item.primary_cluster_id = cluster.id

    if current_primary:
        # Compare: new_item source authority vs current primary's source authority
        # We get the authority weight from the source, passed in for new_item
        # For existing primary, we'd need to look up its source, but for simplicity
        # we check if the new item should replace the primary
        from app.models.news_source import NewsSource
        current_source = await db.get(NewsSource, current_primary.source_id)
        current_weight = float(current_source.authority_weight) if current_source else 1.0

        if source_authority_weight > current_weight or (
            source_authority_weight == current_weight
            and new_item.published_at < current_primary.published_at
        ):
            # New item becomes primary
            new_item.is_cluster_primary = True
            current_primary.is_cluster_primary = False
            cluster.primary_item_id = new_item.id
        else:
            # Existing primary stays
            new_item.is_cluster_primary = False
    else:
        new_item.is_cluster_primary = True
        cluster.primary_item_id = new_item.id

    cluster.member_count += 1
    cluster.last_updated_at = datetime.now(timezone.utc)

    # Update centroid
    all_embeddings = [new_item.embedding]
    if current_primary and current_primary.embedding:
        all_embeddings.append(current_primary.embedding)
    cluster.centroid_embedding = compute_centroid(all_embeddings)

    logger.info(
        "Dedup: item '%s' merged into cluster %s (sim=%.3f)",
        new_item.title[:50], cluster.id, best_sim,
    )
