"""Unified relevance scoring against the shared anchor set.

Scores both papers and news items using the same mechanism:
mean of top-K anchor similarities (weighted).
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.relevance_anchor import RelevanceAnchor
from app.services.ranking.embedder import cosine_similarity

logger = logging.getLogger(__name__)

TOP_K_ANCHORS_FOR_SCORE = 10

# In-memory cache for anchors (refreshed per ingest run)
_anchor_cache: list[dict] | None = None


async def load_anchors(db: AsyncSession) -> list[dict]:
    """Load enabled anchors from DB and cache them."""
    global _anchor_cache
    result = await db.execute(
        select(RelevanceAnchor).where(RelevanceAnchor.enabled == True)
    )
    anchors = result.scalars().all()
    _anchor_cache = [
        {"embedding": a.embedding, "weight": float(a.weight)}
        for a in anchors
        if a.embedding
    ]
    logger.info("Loaded %d relevance anchors", len(_anchor_cache))
    return _anchor_cache


def get_cached_anchors() -> list[dict]:
    """Return cached anchors, or empty list if not loaded."""
    return _anchor_cache or []


def invalidate_cache() -> None:
    """Clear the anchor cache (call after anchor modifications)."""
    global _anchor_cache
    _anchor_cache = None


def compute_relevance_score(
    item_embedding: list[float],
    anchors: list[dict] | None = None,
) -> float:
    """Compute relevance score as mean of top-K weighted anchor similarities.

    Args:
        item_embedding: The embedding vector of the item to score.
        anchors: List of anchor dicts with 'embedding' and 'weight' keys.
                 If None, uses cached anchors.

    Returns:
        Relevance score (0.0 to ~1.0+, can exceed 1.0 with high weights).
    """
    if anchors is None:
        anchors = get_cached_anchors()

    if not anchors or not item_embedding:
        return 0.0

    sims = []
    for anchor in anchors:
        anchor_emb = anchor.get("embedding")
        if not anchor_emb:
            continue
        weight = float(anchor.get("weight", 1.0))
        sim = cosine_similarity(item_embedding, anchor_emb)
        sims.append(sim * weight)

    if not sims:
        return 0.0

    # Sort descending, take top-K, return mean
    sims.sort(reverse=True)
    top_k = sims[:TOP_K_ANCHORS_FOR_SCORE]
    return sum(top_k) / len(top_k)
