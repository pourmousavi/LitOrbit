import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_score import PaperScore


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    """GET /health returns 200 with status healthy."""
    resp = await test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_papers_endpoint_requires_auth(test_client):
    """GET /api/v1/papers without token returns 401 or 403."""
    resp = await test_client.get("/api/v1/papers")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_papers_endpoint_returns_list(test_client, db_session):
    """GET /api/v1/papers with valid auth returns 200 + list."""
    # Mock auth to return a fake user
    fake_user_id = uuid.uuid4()
    fake_user = {"id": str(fake_user_id), "email": "test@test.com", "role": "researcher"}

    # Seed a paper with a score for this user (feed uses INNER JOIN on
    # PaperScore, so papers without scores are hidden).
    paper = Paper(
        id=uuid.uuid4(),
        title="Test Paper for API",
        authors=["Author A"],
        journal="Test Journal",
        journal_source="rss",
        abstract="Test abstract.",
    )
    db_session.add(paper)
    await db_session.flush()
    db_session.add(PaperScore(
        id=uuid.uuid4(),
        paper_id=paper.id,
        user_id=fake_user_id,
        relevance_score=7.0,
    ))
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: fake_user

    resp = await test_client.get("/api/v1/papers")
    assert resp.status_code == 200
    data = resp.json()
    assert "papers" in data
    assert isinstance(data["papers"], list)
    assert len(data["papers"]) >= 1

    # Cleanup override
    del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_papers_sorted_by_score(test_client, db_session):
    """Assert response is sorted by relevance_score descending."""
    user_id = uuid.uuid4()
    fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

    # Create papers with different scores
    paper_low = Paper(id=uuid.uuid4(), title="Low Score Paper", authors=["A"], journal="J", journal_source="rss")
    paper_high = Paper(id=uuid.uuid4(), title="High Score Paper", authors=["B"], journal="J", journal_source="rss")
    paper_mid = Paper(id=uuid.uuid4(), title="Mid Score Paper", authors=["C"], journal="J", journal_source="rss")
    db_session.add_all([paper_low, paper_high, paper_mid])
    await db_session.commit()

    # Add scores
    db_session.add(PaperScore(id=uuid.uuid4(), paper_id=paper_low.id, user_id=user_id, relevance_score=2.0))
    db_session.add(PaperScore(id=uuid.uuid4(), paper_id=paper_high.id, user_id=user_id, relevance_score=9.5))
    db_session.add(PaperScore(id=uuid.uuid4(), paper_id=paper_mid.id, user_id=user_id, relevance_score=6.0))
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: fake_user

    resp = await test_client.get("/api/v1/papers")
    assert resp.status_code == 200
    papers = resp.json()["papers"]

    # Filter to only our papers (test DB may have others from other tests)
    scored_papers = [p for p in papers if p["relevance_score"] is not None]
    scores = [p["relevance_score"] for p in scored_papers]
    assert scores == sorted(scores, reverse=True), f"Papers not sorted by score: {scores}"

    del app.dependency_overrides[get_current_user]


# --- Phase 4: Ratings ---

@pytest.mark.asyncio
async def test_rating_submission(test_client, db_session):
    """POST /ratings with rating=8 returns 200 with follow-up question."""
    from app.auth import get_current_user
    from app.main import app
    from app.models.user_profile import UserProfile

    user_id = uuid.uuid4()
    fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

    profile = UserProfile(id=user_id, full_name="Test User", email="test@test.com", role="researcher")
    db_session.add(profile)
    paper = Paper(id=uuid.uuid4(), title="Test Paper R", authors=["A"], journal="J", journal_source="rss", categories=["battery"])
    db_session.add(paper)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: fake_user

    resp = await test_client.post("/api/v1/ratings", json={
        "paper_id": str(paper.id),
        "rating": 8,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "rating_id" in data
    assert data["follow_up_question"] is not None

    del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_rating_1_to_3_question(test_client, db_session):
    """Rating 2 returns 'Was this irrelevant...' question."""
    from app.auth import get_current_user
    from app.main import app
    from app.models.user_profile import UserProfile

    user_id = uuid.uuid4()
    fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

    profile = UserProfile(id=user_id, full_name="Test User", email="test@test.com", role="researcher")
    db_session.add(profile)
    paper = Paper(id=uuid.uuid4(), title="Low Paper", authors=["A"], journal="J", journal_source="rss")
    db_session.add(paper)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: fake_user

    resp = await test_client.post("/api/v1/ratings", json={
        "paper_id": str(paper.id),
        "rating": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "irrelevant" in data["follow_up_question"].lower()

    del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_rating_9_to_10_question(test_client, db_session):
    """Rating 10 returns 'find related work' question."""
    from app.auth import get_current_user
    from app.main import app
    from app.models.user_profile import UserProfile

    user_id = uuid.uuid4()
    fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

    profile = UserProfile(id=user_id, full_name="Test User", email="test@test.com", role="researcher")
    db_session.add(profile)
    paper = Paper(id=uuid.uuid4(), title="Top Paper", authors=["A"], journal="J", journal_source="rss")
    db_session.add(paper)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: fake_user

    resp = await test_client.post("/api/v1/ratings", json={
        "paper_id": str(paper.id),
        "rating": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "related work" in data["follow_up_question"].lower()

    del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_category_weights_updated(test_client, db_session):
    """After rating=9, user's category_weights for paper's categories should increase."""
    from app.auth import get_current_user
    from app.main import app
    from app.models.user_profile import UserProfile

    user_id = uuid.uuid4()
    fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

    profile = UserProfile(id=user_id, full_name="Test User", email="test@test.com", role="researcher", interest_vector={}, category_weights={})
    db_session.add(profile)
    paper = Paper(id=uuid.uuid4(), title="Battery Paper", authors=["A"], journal="J", journal_source="rss", categories=["battery", "degradation"])
    db_session.add(paper)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: fake_user

    resp = await test_client.post("/api/v1/ratings", json={
        "paper_id": str(paper.id),
        "rating": 9,
    })
    assert resp.status_code == 200

    await db_session.refresh(profile)
    weights = profile.category_weights
    assert weights.get("battery", 0) > 0
    assert weights.get("degradation", 0) > 0

    del app.dependency_overrides[get_current_user]


# --- Phase 4: Shares ---

@pytest.mark.asyncio
async def test_share_creation(test_client, db_session):
    """POST /shares creates a share record."""
    from app.auth import get_current_user
    from app.main import app
    from app.models.user_profile import UserProfile

    sender_id = uuid.uuid4()
    recipient_id = uuid.uuid4()
    fake_user = {"id": str(sender_id), "email": "sender@test.com", "role": "admin"}

    sender = UserProfile(id=sender_id, full_name="Sender", email="sender@test.com", role="admin")
    recipient = UserProfile(id=recipient_id, full_name="Recipient", email="rec@test.com", role="researcher")
    db_session.add_all([sender, recipient])
    paper = Paper(id=uuid.uuid4(), title="Shared Paper", authors=["A"], journal="J", journal_source="rss")
    db_session.add(paper)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: fake_user

    resp = await test_client.post("/api/v1/shares", json={
        "paper_id": str(paper.id),
        "shared_with": str(recipient_id),
        "annotation": "Check this out!",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "shared"

    del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_share_inbox(test_client, db_session):
    """GET /shares/inbox returns shares addressed to user."""
    from app.auth import get_current_user
    from app.main import app
    from app.models.user_profile import UserProfile
    from app.models.share import Share

    sender_id = uuid.uuid4()
    recipient_id = uuid.uuid4()

    sender = UserProfile(id=sender_id, full_name="Sender", email="s@test.com", role="admin")
    recipient = UserProfile(id=recipient_id, full_name="Recipient", email="r@test.com", role="researcher")
    db_session.add_all([sender, recipient])
    paper = Paper(id=uuid.uuid4(), title="Inbox Paper", authors=["A"], journal="J", journal_source="rss")
    db_session.add(paper)
    await db_session.commit()

    share = Share(id=uuid.uuid4(), paper_id=paper.id, shared_by=sender_id, shared_with=recipient_id, annotation="Read this")
    db_session.add(share)
    await db_session.commit()

    fake_user = {"id": str(recipient_id), "email": "r@test.com", "role": "researcher"}
    app.dependency_overrides[get_current_user] = lambda: fake_user

    resp = await test_client.get("/api/v1/shares/inbox")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["sharer_name"] == "Sender"
    assert data[0]["annotation"] == "Read this"

    del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
async def test_share_not_visible_to_others(test_client, db_session):
    """User B cannot see User A's shares."""
    from app.auth import get_current_user
    from app.main import app
    from app.models.user_profile import UserProfile
    from app.models.share import Share

    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    sender = uuid.uuid4()

    db_session.add_all([
        UserProfile(id=sender, full_name="Sender", email="s@x.com", role="admin"),
        UserProfile(id=user_a, full_name="User A", email="a@x.com", role="researcher"),
        UserProfile(id=user_b, full_name="User B", email="b@x.com", role="researcher"),
    ])
    paper = Paper(id=uuid.uuid4(), title="Private Paper", authors=["X"], journal="J", journal_source="rss")
    db_session.add(paper)
    await db_session.commit()

    share = Share(id=uuid.uuid4(), paper_id=paper.id, shared_by=sender, shared_with=user_a)
    db_session.add(share)
    await db_session.commit()

    fake_user_b = {"id": str(user_b), "email": "b@x.com", "role": "researcher"}
    app.dependency_overrides[get_current_user] = lambda: fake_user_b

    resp = await test_client.get("/api/v1/shares/inbox")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0

    del app.dependency_overrides[get_current_user]
