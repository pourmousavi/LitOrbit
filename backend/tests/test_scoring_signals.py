"""Tests for Phase 1 Chunk 4: scoring signal logging and CSV export."""

import csv
import io
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.paper import Paper
from app.models.user_profile import UserProfile
from app.models.scoring_signal import ScoringSignal
from app.models.system_settings import SystemSettings


FAKE_EMBEDDING = [0.5] * 10


async def _seed_signal(db, user_id, paper_id, **kwargs):
    defaults = {
        "max_positive_sim": 0.7,
        "max_negative_sim": 0.1,
        "effective_score": 0.65,
        "threshold_used": 0.5,
        "lambda_used": 0.5,
        "prefilter_matched": True,
        "passed_gate": True,
        "llm_score": 7.5,
        "llm_errored": False,
    }
    defaults.update(kwargs)
    sig = ScoringSignal(
        id=uuid.uuid4(),
        paper_id=paper_id,
        user_id=user_id,
        **defaults,
    )
    db.add(sig)
    await db.flush()
    return sig


# ---------------------------------------------------------------------------
# CSV endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_endpoint_returns_valid_csv(test_client, db_session):
    """CSV endpoint returns valid CSV with correct columns."""
    from app.auth import require_admin
    from app.main import app

    admin_user = {"id": str(uuid.uuid4()), "email": "admin@test.com", "role": "admin"}
    app.dependency_overrides[require_admin] = lambda: admin_user

    # Seed data
    uid = uuid.uuid4()
    db_session.add(UserProfile(id=uid, full_name="Test", email="t@t.com", role="researcher"))
    paper = Paper(id=uuid.uuid4(), title="Test Paper", authors=["A"], journal="J", journal_source="rss")
    db_session.add(paper)
    await db_session.flush()

    await _seed_signal(db_session, uid, paper.id)
    await db_session.commit()

    resp = await test_client.get("/api/v1/admin/tuning/signals.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")

    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    header = rows[0]
    expected_header = [
        "created_at", "user_id", "paper_id", "paper_title",
        "max_positive_sim", "max_negative_sim", "effective_score",
        "threshold_used", "lambda_used", "prefilter_matched",
        "passed_gate", "llm_score", "llm_errored", "rating",
    ]
    assert header == expected_header
    assert len(rows) == 2  # header + 1 data row

    del app.dependency_overrides[require_admin]


@pytest.mark.asyncio
async def test_csv_endpoint_filters_by_user(test_client, db_session):
    """CSV with user_id filter returns only that user's rows."""
    from app.auth import require_admin
    from app.main import app

    admin_user = {"id": str(uuid.uuid4()), "email": "admin@test.com", "role": "admin"}
    app.dependency_overrides[require_admin] = lambda: admin_user

    uid1 = uuid.uuid4()
    uid2 = uuid.uuid4()
    db_session.add(UserProfile(id=uid1, full_name="User1", email="u1@t.com", role="researcher"))
    db_session.add(UserProfile(id=uid2, full_name="User2", email="u2@t.com", role="researcher"))
    p = Paper(id=uuid.uuid4(), title="P", authors=["A"], journal="J", journal_source="rss")
    db_session.add(p)
    await db_session.flush()

    await _seed_signal(db_session, uid1, p.id)
    # Create second signal with different paper to avoid unique constraint
    p2 = Paper(id=uuid.uuid4(), title="P2", authors=["A"], journal="J", journal_source="rss")
    db_session.add(p2)
    await db_session.flush()
    await _seed_signal(db_session, uid2, p2.id)
    await db_session.commit()

    resp = await test_client.get(f"/api/v1/admin/tuning/signals.csv?user_id={uid1}")
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 2  # header + 1 row for uid1 only

    del app.dependency_overrides[require_admin]


@pytest.mark.asyncio
async def test_csv_requires_admin(test_client):
    """Non-admin gets 401/403."""
    resp = await test_client.get("/api/v1/admin/tuning/signals.csv")
    assert resp.status_code in (401, 403)
