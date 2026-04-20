"""Tests for Phase 1 Chunk 5: backfill_anchors script."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.paper import Paper
from app.models.user_profile import UserProfile
from app.models.reference_paper import ReferencePaper
from app.models.rating import Rating
from scripts.backfill_anchors import backfill_user


FAKE_EMBEDDING = [0.1] * 10
FAKE_EMBEDDING_2 = [0.2] * 10


def _now():
    return datetime.now(timezone.utc)


def _days_ago(n):
    return _now() - timedelta(days=n)


async def _seed_user(db, user_id=None, email="test@test.com"):
    uid = user_id or uuid.uuid4()
    profile = UserProfile(id=uid, full_name="Test", email=email, role="researcher")
    db.add(profile)
    await db.flush()
    return uid


async def _seed_paper(db, paper_id=None, embedding=FAKE_EMBEDDING):
    pid = paper_id or uuid.uuid4()
    paper = Paper(
        id=pid, title=f"Paper {pid}", authors=["A"],
        journal="J", journal_source="rss", embedding=embedding,
    )
    db.add(paper)
    await db.flush()
    return pid


async def _seed_rating(db, user_id, paper_id, rating_val, feedback_type=None, rated_at=None):
    r = Rating(
        id=uuid.uuid4(), paper_id=paper_id, user_id=user_id,
        rating=rating_val, feedback_type=feedback_type,
        rated_at=rated_at or _now(),
    )
    db.add(r)
    await db.flush()
    return r


async def _seed_reference(db, user_id, paper_id=None, embedding=FAKE_EMBEDDING):
    pid = paper_id or uuid.uuid4()
    ref = ReferencePaper(
        id=pid, user_id=user_id,
        title=f"Ref {pid}", source="manual", embedding=embedding,
    )
    db.add(ref)
    await db.flush()
    return pid


# ---------------------------------------------------------------------------
# Core backfill tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backfill_positive_from_high_ratings(db_session):
    """5 ratings >= 7 → +5 positive anchors."""
    uid = await _seed_user(db_session)

    for i in range(5):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rating_val=8)

    await db_session.commit()
    summary = await backfill_user(db_session, uid, dry_run=False)

    assert summary["positive_added"] == 5

    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    rating_anchors = [a for a in profile.positive_anchors if a["source"] == "rating"]
    assert len(rating_anchors) == 5


@pytest.mark.asyncio
async def test_backfill_negative_from_low_ratings(db_session):
    """3 ratings <= 3 → +3 negative anchors."""
    uid = await _seed_user(db_session)

    for i in range(3):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rating_val=2)

    await db_session.commit()
    summary = await backfill_user(db_session, uid, dry_run=False)

    assert summary["negative_added"] == 3

    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    assert len(profile.negative_anchors) == 3


@pytest.mark.asyncio
async def test_backfill_skips_mid_ratings_no_feedback(db_session):
    """2 ratings in 4-6 with no feedback → skipped."""
    uid = await _seed_user(db_session)

    for _ in range(2):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rating_val=5)

    await db_session.commit()
    summary = await backfill_user(db_session, uid, dry_run=False)

    assert summary["positive_added"] == 0
    assert summary["negative_added"] == 0
    assert summary["skipped_no_spec"] == 2


@pytest.mark.asyncio
async def test_backfill_skips_remove_spec(db_session):
    """Rating <= 3 with 'Right topic, weak paper' → skipped (remove spec)."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, pid, rating_val=2, feedback_type="Right topic, weak paper")
    await db_session.commit()

    summary = await backfill_user(db_session, uid, dry_run=False)
    assert summary["positive_added"] == 0
    assert summary["negative_added"] == 0


@pytest.mark.asyncio
async def test_backfill_skips_no_embedding(db_session):
    """Rating on paper with no embedding → skipped."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session, embedding=None)
    await _seed_rating(db_session, uid, pid, rating_val=9)
    await db_session.commit()

    summary = await backfill_user(db_session, uid, dry_run=False)
    assert summary["skipped_no_embedding"] == 1
    assert summary["positive_added"] == 0


@pytest.mark.asyncio
async def test_backfill_skips_reference_papers(db_session):
    """Rating on a paper that's in reference_papers → skipped."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)

    # Add as reference paper and seed into positive_anchors
    await _seed_reference(db_session, uid, paper_id=pid)

    # Seed positive_anchors with reference entry (simulating chunk 1 migration)
    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    profile.positive_anchors = [{
        "paper_id": str(pid),
        "embedding": FAKE_EMBEDDING,
        "source": "reference",
        "weight": 1.0,
        "added_at": _now().isoformat(),
        "tags": [],
    }]
    await db_session.flush()

    # Now rate that same paper
    await _seed_rating(db_session, uid, pid, rating_val=9)
    await db_session.commit()

    summary = await backfill_user(db_session, uid, dry_run=False)
    assert summary["skipped_reference"] == 1
    assert summary["positive_added"] == 0


@pytest.mark.asyncio
async def test_backfill_preserves_reference_anchors(db_session):
    """Reference entries in positive_anchors are never modified or evicted."""
    uid = await _seed_user(db_session)

    # Seed 5 reference papers into positive_anchors
    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    ref_anchors = []
    for i in range(5):
        ref_id = uuid.uuid4()
        await _seed_reference(db_session, uid, paper_id=ref_id)
        ref_anchors.append({
            "paper_id": str(ref_id),
            "embedding": FAKE_EMBEDDING,
            "source": "reference",
            "weight": 1.0,
            "added_at": _now().isoformat(),
            "tags": [],
        })
    profile.positive_anchors = ref_anchors
    await db_session.flush()

    # Add 3 high ratings on different papers
    for _ in range(3):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rating_val=8)
    await db_session.commit()

    summary = await backfill_user(db_session, uid, dry_run=False)
    assert summary["positive_added"] == 3
    assert summary["positive_existing_refs"] == 5

    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    assert len(profile.positive_anchors) == 8  # 5 ref + 3 rating


@pytest.mark.asyncio
async def test_backfill_idempotent(db_session):
    """Running twice produces +0 on second run."""
    uid = await _seed_user(db_session)
    for _ in range(3):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rating_val=8)
    await db_session.commit()

    # First run
    summary1 = await backfill_user(db_session, uid, dry_run=False)
    assert summary1["positive_added"] == 3

    # Snapshot
    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    snapshot = json.dumps(profile.positive_anchors, sort_keys=True)

    # Second run — should be zero additions
    summary2 = await backfill_user(db_session, uid, dry_run=False)
    assert summary2["positive_added"] == 0

    # Verify no changes
    await db_session.refresh(profile)
    snapshot2 = json.dumps(profile.positive_anchors, sort_keys=True)
    assert snapshot == snapshot2


@pytest.mark.asyncio
async def test_dry_run_no_db_writes(db_session):
    """--dry-run produces summary but zero DB changes."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, pid, rating_val=9)
    await db_session.commit()

    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    before = json.dumps(profile.positive_anchors or [], sort_keys=True)

    summary = await backfill_user(db_session, uid, dry_run=True)
    assert summary["positive_added"] == 1

    await db_session.refresh(profile)
    after = json.dumps(profile.positive_anchors or [], sort_keys=True)
    assert before == after


@pytest.mark.asyncio
async def test_cap_enforcement(db_session):
    """With >100 rating anchors, cap at 100 and never evict reference entries."""
    uid = await _seed_user(db_session)

    # Pre-seed 5 reference anchors
    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    ref_anchors = []
    for i in range(5):
        ref_id = uuid.uuid4()
        await _seed_reference(db_session, uid, paper_id=ref_id)
        ref_anchors.append({
            "paper_id": str(ref_id),
            "embedding": FAKE_EMBEDDING,
            "source": "reference",
            "weight": 1.0,
            "added_at": _now().isoformat(),
            "tags": [],
        })
    profile.positive_anchors = ref_anchors

    # Pre-seed 90 rating-sourced anchors directly
    for i in range(90):
        fake_pid = str(uuid.uuid4())
        profile.positive_anchors = list(profile.positive_anchors) + [{
            "paper_id": fake_pid,
            "embedding": FAKE_EMBEDDING,
            "source": "rating",
            "weight": 0.5,  # low weight, should be evicted first
            "added_at": _days_ago(100 + i).isoformat(),
            "tags": [],
        }]
    await db_session.flush()

    # Now add 10 new high ratings
    for _ in range(10):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rating_val=9)
    await db_session.commit()

    summary = await backfill_user(db_session, uid, dry_run=False)

    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()

    # Total should be capped at 100
    assert len(profile.positive_anchors) == 100

    # All 5 reference entries must survive
    ref_count = sum(1 for a in profile.positive_anchors if a.get("source") == "reference")
    assert ref_count == 5
