"""Tests for Phase 1 Chunk 1: admin threshold endpoints and reference-paper anchor mirroring."""

import uuid

import pytest
import pytest_asyncio

from app.models.paper import Paper
from app.models.user_profile import UserProfile
from app.models.reference_paper import ReferencePaper
from app.models.system_settings import SystemSettings


# ---------------------------------------------------------------------------
# Admin threshold endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_thresholds_defaults(test_client, db_session):
    """GET /api/v1/admin/thresholds returns default values on fresh settings row."""
    from app.auth import require_admin
    from app.main import app

    admin_user = {"id": str(uuid.uuid4()), "email": "admin@test.com", "role": "admin"}
    app.dependency_overrides[require_admin] = lambda: admin_user

    # Ensure settings row exists
    db_session.add(SystemSettings(id=1))
    await db_session.commit()

    resp = await test_client.get("/api/v1/admin/thresholds")
    assert resp.status_code == 200
    data = resp.json()
    assert data["similarity_threshold"] == 0.50
    assert data["negative_anchor_lambda"] == 0.5

    del app.dependency_overrides[require_admin]


@pytest.mark.asyncio
async def test_put_thresholds_updates(test_client, db_session):
    """PUT /api/v1/admin/thresholds with valid values returns 200, GET reflects changes."""
    from app.auth import require_admin
    from app.main import app

    admin_user = {"id": str(uuid.uuid4()), "email": "admin@test.com", "role": "admin"}
    app.dependency_overrides[require_admin] = lambda: admin_user

    db_session.add(SystemSettings(id=1))
    await db_session.commit()

    resp = await test_client.put("/api/v1/admin/thresholds", json={
        "similarity_threshold": 0.6,
        "negative_anchor_lambda": 0.7,
    })
    assert resp.status_code == 200

    resp = await test_client.get("/api/v1/admin/thresholds")
    data = resp.json()
    assert data["similarity_threshold"] == 0.6
    assert data["negative_anchor_lambda"] == 0.7

    del app.dependency_overrides[require_admin]


@pytest.mark.asyncio
async def test_put_thresholds_rejects_high_similarity(test_client, db_session):
    """PUT with similarity_threshold > 1.0 returns 422 (validation error)."""
    from app.auth import require_admin
    from app.main import app

    admin_user = {"id": str(uuid.uuid4()), "email": "admin@test.com", "role": "admin"}
    app.dependency_overrides[require_admin] = lambda: admin_user

    db_session.add(SystemSettings(id=1))
    await db_session.commit()

    resp = await test_client.put("/api/v1/admin/thresholds", json={
        "similarity_threshold": 1.5,
        "negative_anchor_lambda": 0.5,
    })
    assert resp.status_code == 422

    del app.dependency_overrides[require_admin]


@pytest.mark.asyncio
async def test_put_thresholds_rejects_negative_lambda(test_client, db_session):
    """PUT with negative_anchor_lambda < 0 returns 422."""
    from app.auth import require_admin
    from app.main import app

    admin_user = {"id": str(uuid.uuid4()), "email": "admin@test.com", "role": "admin"}
    app.dependency_overrides[require_admin] = lambda: admin_user

    db_session.add(SystemSettings(id=1))
    await db_session.commit()

    resp = await test_client.put("/api/v1/admin/thresholds", json={
        "similarity_threshold": 0.5,
        "negative_anchor_lambda": -0.1,
    })
    assert resp.status_code == 422

    del app.dependency_overrides[require_admin]


@pytest.mark.asyncio
async def test_thresholds_requires_admin(test_client, db_session):
    """Non-admin user gets 401/403 on threshold endpoints."""
    resp = await test_client.get("/api/v1/admin/thresholds")
    assert resp.status_code in (401, 403)

    resp = await test_client.put("/api/v1/admin/thresholds", json={
        "similarity_threshold": 0.5,
        "negative_anchor_lambda": 0.5,
    })
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Reference paper → positive_anchors mirroring tests
# ---------------------------------------------------------------------------

FAKE_EMBEDDING = [0.1] * 10  # short vector for testing


@pytest.mark.asyncio
async def test_reference_paper_add_mirrors_to_positive_anchors(test_client, db_session):
    """After adding a reference paper with an embedding, positive_anchors has one entry."""
    from app.auth import get_current_user
    from app.main import app
    from unittest.mock import AsyncMock, patch

    user_id = uuid.uuid4()
    fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

    profile = UserProfile(
        id=user_id, full_name="Test User", email="test@test.com", role="researcher",
    )
    db_session.add(profile)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: fake_user

    # Mock embed_text to return a fake embedding
    with patch("app.routers.reference_papers.embed_text", new_callable=AsyncMock, return_value=FAKE_EMBEDDING):
        resp = await test_client.post("/api/v1/reference-papers/manual", json={
            "title": "Test Reference Paper",
            "abstract": "A great paper about batteries.",
        })
    assert resp.status_code == 200
    assert resp.json()["has_embedding"] is True

    await db_session.refresh(profile)
    anchors = profile.positive_anchors
    assert len(anchors) == 1
    assert anchors[0]["source"] == "reference"
    # Anchor entries no longer carry the embedding inline (egress optimisation);
    # the scorer joins back to reference_papers.embedding by paper_id.
    assert "paper_id" in anchors[0]
    assert "embedding" not in anchors[0]
    assert anchors[0]["weight"] == 1.0

    del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_reference_paper_delete_removes_from_positive_anchors(test_client, db_session):
    """After deleting a reference paper, its entry is removed from positive_anchors."""
    from app.auth import get_current_user
    from app.main import app
    from unittest.mock import AsyncMock, patch

    user_id = uuid.uuid4()
    fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

    profile = UserProfile(
        id=user_id, full_name="Test User", email="test@test.com", role="researcher",
    )
    db_session.add(profile)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: fake_user

    # Add a reference paper
    with patch("app.routers.reference_papers.embed_text", new_callable=AsyncMock, return_value=FAKE_EMBEDDING):
        resp = await test_client.post("/api/v1/reference-papers/manual", json={
            "title": "Paper to Delete",
            "abstract": "Will be removed.",
        })
    assert resp.status_code == 200
    paper_id = resp.json()["id"]

    await db_session.refresh(profile)
    assert len(profile.positive_anchors) == 1

    # Delete it
    resp = await test_client.delete(f"/api/v1/reference-papers/{paper_id}")
    assert resp.status_code == 200

    await db_session.refresh(profile)
    assert len(profile.positive_anchors) == 0

    del app.dependency_overrides[get_current_user]


# ---------------------------------------------------------------------------
# Negative title keywords endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_negative_title_keywords_defaults(test_client, db_session):
    """GET /api/v1/admin/negative-title-keywords returns empty list on fresh settings."""
    from app.auth import require_admin
    from app.main import app

    admin_user = {"id": str(uuid.uuid4()), "email": "admin@test.com", "role": "admin"}
    app.dependency_overrides[require_admin] = lambda: admin_user

    db_session.add(SystemSettings(id=1))
    await db_session.commit()

    resp = await test_client.get("/api/v1/admin/negative-title-keywords")
    assert resp.status_code == 200
    assert resp.json()["keywords"] == []

    del app.dependency_overrides[require_admin]


@pytest.mark.asyncio
async def test_put_negative_title_keywords_updates(test_client, db_session):
    """PUT updates; subsequent GET reflects the new list."""
    from app.auth import require_admin
    from app.main import app

    admin_user = {"id": str(uuid.uuid4()), "email": "admin@test.com", "role": "admin"}
    app.dependency_overrides[require_admin] = lambda: admin_user

    db_session.add(SystemSettings(id=1))
    await db_session.commit()

    resp = await test_client.put("/api/v1/admin/negative-title-keywords", json={
        "keywords": ["tumor", "antibody"],
    })
    assert resp.status_code == 200

    resp = await test_client.get("/api/v1/admin/negative-title-keywords")
    data = resp.json()
    assert data["keywords"] == ["tumor", "antibody"]

    del app.dependency_overrides[require_admin]


@pytest.mark.asyncio
async def test_negative_title_keywords_requires_admin(test_client, db_session):
    """Non-admin user gets 401/403."""
    resp = await test_client.get("/api/v1/admin/negative-title-keywords")
    assert resp.status_code in (401, 403)

    resp = await test_client.put("/api/v1/admin/negative-title-keywords", json={
        "keywords": ["tumor"],
    })
    assert resp.status_code in (401, 403)
