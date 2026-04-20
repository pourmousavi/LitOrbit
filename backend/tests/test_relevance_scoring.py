"""Tests for the unified relevance scoring service.

Covers:
- Score returns non-zero for in-domain item
- Score uses top-K mean (not all anchors)
- Score respects anchor weights
- Empty anchors return 0.0
"""

import math

import pytest

from app.services.relevance_service import compute_relevance_score, TOP_K_ANCHORS_FOR_SCORE


def _make_unit_vector(dim: int, angle: float = 0.0) -> list[float]:
    vec = [0.0] * dim
    vec[0] = math.cos(angle)
    if dim > 1:
        vec[1] = math.sin(angle)
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


def test_score_returns_nonzero_for_similar_item():
    """An item similar to anchors should score > 0."""
    anchor_vec = _make_unit_vector(64, 0.0)
    item_vec = _make_unit_vector(64, 0.05)  # Very similar

    anchors = [{"embedding": anchor_vec, "weight": 1.0}]
    score = compute_relevance_score(item_vec, anchors)
    assert score > 0.5


def test_score_returns_zero_for_empty_anchors():
    """No anchors should produce score 0."""
    item_vec = _make_unit_vector(64, 0.0)
    assert compute_relevance_score(item_vec, []) == 0.0
    assert compute_relevance_score(item_vec, None) == 0.0


def test_score_returns_zero_for_empty_embedding():
    """No embedding should produce score 0."""
    anchors = [{"embedding": _make_unit_vector(64), "weight": 1.0}]
    assert compute_relevance_score([], anchors) == 0.0


def test_score_uses_top_k_mean():
    """Score should be mean of top-K similarities, not all."""
    dim = 64
    item_vec = _make_unit_vector(dim, 0.0)

    # Create 15 anchors: 5 very similar, 10 dissimilar
    anchors = []
    for i in range(5):
        anchors.append({"embedding": _make_unit_vector(dim, 0.01 * i), "weight": 1.0})
    for i in range(10):
        anchors.append({"embedding": _make_unit_vector(dim, 1.0 + 0.1 * i), "weight": 1.0})

    score = compute_relevance_score(item_vec, anchors)

    # Score should reflect the top-K (10) including the 5 very similar
    # It should be higher than if we averaged all 15
    all_sims = []
    from app.services.ranking.embedder import cosine_similarity
    for a in anchors:
        all_sims.append(cosine_similarity(item_vec, a["embedding"]))
    all_sims.sort(reverse=True)
    mean_all = sum(all_sims) / len(all_sims)
    mean_top_k = sum(all_sims[:TOP_K_ANCHORS_FOR_SCORE]) / min(TOP_K_ANCHORS_FOR_SCORE, len(all_sims))

    assert abs(score - mean_top_k) < 0.001
    assert score > mean_all  # Top-K should be higher than all-mean


def test_score_respects_weights():
    """Higher-weighted anchors should increase score."""
    dim = 64
    item_vec = _make_unit_vector(dim, 0.0)
    anchor_vec = _make_unit_vector(dim, 0.0)

    score_low = compute_relevance_score(
        item_vec, [{"embedding": anchor_vec, "weight": 0.5}]
    )
    score_high = compute_relevance_score(
        item_vec, [{"embedding": anchor_vec, "weight": 2.0}]
    )

    assert score_high > score_low
    assert abs(score_high / score_low - 4.0) < 0.01  # 2.0/0.5 = 4x ratio


def test_score_with_fewer_than_k_anchors():
    """With fewer than K anchors, should use all available."""
    dim = 64
    item_vec = _make_unit_vector(dim, 0.0)

    # Only 3 anchors (less than K=10)
    anchors = [
        {"embedding": _make_unit_vector(dim, 0.01), "weight": 1.0},
        {"embedding": _make_unit_vector(dim, 0.02), "weight": 1.0},
        {"embedding": _make_unit_vector(dim, 0.03), "weight": 1.0},
    ]

    score = compute_relevance_score(item_vec, anchors)
    assert score > 0.9  # Very similar vectors, should score high


def test_score_orthogonal_item():
    """An item orthogonal to all anchors should score near 0."""
    dim = 64
    item_vec = _make_unit_vector(dim, math.pi / 2)  # 90 degrees
    anchor_vec = _make_unit_vector(dim, 0.0)

    anchors = [{"embedding": anchor_vec, "weight": 1.0}]
    score = compute_relevance_score(item_vec, anchors)
    assert abs(score) < 0.01  # Should be near 0
