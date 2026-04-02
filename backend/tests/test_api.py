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
    # Seed a paper
    paper = Paper(
        id=uuid.uuid4(),
        title="Test Paper for API",
        authors=["Author A"],
        journal="Test Journal",
        journal_source="rss",
        abstract="Test abstract.",
    )
    db_session.add(paper)
    await db_session.commit()

    # Mock auth to return a fake user
    fake_user = {"id": str(uuid.uuid4()), "email": "test@test.com", "role": "researcher"}

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
