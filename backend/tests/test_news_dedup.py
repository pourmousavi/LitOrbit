"""Tests for news deduplication service.

Covers:
- Two near-duplicate items merge into one cluster
- Primary selection by authority weight
- Non-duplicate items get separate clusters
- Cosine threshold boundary behavior
"""

import uuid
import math
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.models.news_source import NewsSource
from app.models.news_item import NewsItem
from app.models.news_cluster import NewsCluster


def _make_unit_vector(dim: int, angle_offset: float = 0.0) -> list[float]:
    """Create a unit vector in the given dimension with optional rotation."""
    vec = [0.0] * dim
    # Simple: put most of the weight on dim 0, with a small rotation
    vec[0] = math.cos(angle_offset)
    if dim > 1:
        vec[1] = math.sin(angle_offset)
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


def _make_similar_vectors(dim: int = 64, similarity: float = 0.90):
    """Create two vectors with approximately the given cosine similarity."""
    # For normalized vectors, cos(theta) = similarity
    theta = math.acos(max(-1, min(1, similarity)))
    vec_a = _make_unit_vector(dim, 0.0)
    vec_b = _make_unit_vector(dim, theta)
    return vec_a, vec_b


@pytest.mark.asyncio
async def test_new_item_creates_cluster(db_session):
    """A new item with no similar items should create its own cluster."""
    from app.services.news_dedup_service import assign_cluster

    source = NewsSource(
        name="Dedup Source A",
        feed_url="https://a.com/feed/",
        website_url="https://a.com/",
        authority_weight=1.0,
    )
    db_session.add(source)
    await db_session.flush()

    vec = _make_unit_vector(64)
    item = NewsItem(
        source_id=source.id,
        url="https://a.com/unique-article",
        title="Unique Article",
        published_at=datetime.now(timezone.utc),
        embedding=vec,
    )
    db_session.add(item)
    await db_session.flush()

    await assign_cluster(db_session, item, source_authority_weight=1.0)
    await db_session.commit()

    assert item.primary_cluster_id is not None
    assert item.is_cluster_primary is True


@pytest.mark.asyncio
async def test_duplicate_items_merge_cluster(db_session):
    """Two near-duplicate items should merge into one cluster."""
    from app.services.news_dedup_service import assign_cluster

    source = NewsSource(
        name="Dedup Source B",
        feed_url="https://b.com/feed/",
        website_url="https://b.com/",
        authority_weight=1.0,
    )
    db_session.add(source)
    await db_session.flush()

    # Create two very similar vectors (sim > 0.88)
    vec_a, vec_b = _make_similar_vectors(64, similarity=0.95)

    item_a = NewsItem(
        source_id=source.id,
        url="https://b.com/story-version-1",
        title="BESS project approved",
        published_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        embedding=vec_a,
        is_cluster_primary=True,
    )
    db_session.add(item_a)
    await db_session.flush()
    await assign_cluster(db_session, item_a, source_authority_weight=1.0)

    item_b = NewsItem(
        source_id=source.id,
        url="https://b.com/story-version-2",
        title="BESS project gets green light",
        published_at=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
        embedding=vec_b,
    )
    db_session.add(item_b)
    await db_session.flush()
    await assign_cluster(db_session, item_b, source_authority_weight=1.0)
    await db_session.commit()

    # Both should share the same cluster
    assert item_a.primary_cluster_id == item_b.primary_cluster_id

    # Exactly one should be primary
    primaries = [item_a.is_cluster_primary, item_b.is_cluster_primary]
    assert primaries.count(True) == 1


@pytest.mark.asyncio
async def test_high_authority_becomes_primary(db_session):
    """Higher authority_weight source should become cluster primary."""
    from app.services.news_dedup_service import assign_cluster

    source_low = NewsSource(
        name="Low Auth Source",
        feed_url="https://low.com/feed/",
        website_url="https://low.com/",
        authority_weight=0.8,
    )
    source_high = NewsSource(
        name="High Auth Source",
        feed_url="https://high.com/feed/",
        website_url="https://high.com/",
        authority_weight=1.5,
    )
    db_session.add(source_low)
    db_session.add(source_high)
    await db_session.flush()

    vec_a, vec_b = _make_similar_vectors(64, similarity=0.95)

    # Low-authority item first
    item_low = NewsItem(
        source_id=source_low.id,
        url="https://low.com/same-story",
        title="Same story low auth",
        published_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        embedding=vec_a,
    )
    db_session.add(item_low)
    await db_session.flush()
    await assign_cluster(db_session, item_low, source_authority_weight=0.8)

    # High-authority item second
    item_high = NewsItem(
        source_id=source_high.id,
        url="https://high.com/same-story",
        title="Same story high auth",
        published_at=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
        embedding=vec_b,
    )
    db_session.add(item_high)
    await db_session.flush()
    await assign_cluster(db_session, item_high, source_authority_weight=1.5)
    await db_session.commit()

    # High-authority item should be primary
    assert item_high.is_cluster_primary is True
    assert item_low.is_cluster_primary is False


@pytest.mark.asyncio
async def test_dissimilar_items_separate_clusters(db_session):
    """Items with low cosine similarity should get separate clusters."""
    from app.services.news_dedup_service import assign_cluster

    source = NewsSource(
        name="Dedup Source C",
        feed_url="https://c.com/feed/",
        website_url="https://c.com/",
        authority_weight=1.0,
    )
    db_session.add(source)
    await db_session.flush()

    # Create two very different vectors (sim < 0.88)
    vec_a, vec_b = _make_similar_vectors(64, similarity=0.3)

    item_a = NewsItem(
        source_id=source.id,
        url="https://c.com/totally-different-1",
        title="Battery technology",
        published_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        embedding=vec_a,
    )
    item_b = NewsItem(
        source_id=source.id,
        url="https://c.com/totally-different-2",
        title="Solar regulations",
        published_at=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
        embedding=vec_b,
    )

    db_session.add(item_a)
    await db_session.flush()
    await assign_cluster(db_session, item_a, source_authority_weight=1.0)

    db_session.add(item_b)
    await db_session.flush()
    await assign_cluster(db_session, item_b, source_authority_weight=1.0)
    await db_session.commit()

    # Should have separate clusters
    assert item_a.primary_cluster_id != item_b.primary_cluster_id
    assert item_a.is_cluster_primary is True
    assert item_b.is_cluster_primary is True


@pytest.mark.asyncio
async def test_item_without_embedding_gets_standalone_cluster(db_session):
    """An item with no embedding should get its own cluster."""
    from app.services.news_dedup_service import assign_cluster

    source = NewsSource(
        name="Dedup No Embed",
        feed_url="https://d.com/feed/",
        website_url="https://d.com/",
        authority_weight=1.0,
    )
    db_session.add(source)
    await db_session.flush()

    item = NewsItem(
        source_id=source.id,
        url="https://d.com/no-embed",
        title="No Embedding Item",
        published_at=datetime.now(timezone.utc),
        embedding=None,
    )
    db_session.add(item)
    await db_session.flush()
    await assign_cluster(db_session, item, source_authority_weight=1.0)
    await db_session.commit()

    assert item.primary_cluster_id is not None
    assert item.is_cluster_primary is True
