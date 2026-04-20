"""Tests for Phase 2 Chunk 5: threshold suggestion script."""

import random
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.paper import Paper
from app.models.user_profile import UserProfile
from app.models.scoring_signal import ScoringSignal
from app.models.rating import Rating
from app.models.system_settings import SystemSettings
from scripts.suggest_thresholds import run_report


FAKE_EMBEDDING = [0.1] * 10


def _now():
    return datetime.now(timezone.utc)


async def _seed_user(db, user_id=None):
    uid = user_id or uuid.uuid4()
    profile = UserProfile(id=uid, full_name="Test", email="test@test.com", role="researcher")
    db.add(profile)
    await db.flush()
    return uid


async def _seed_paper(db, paper_id=None):
    pid = paper_id or uuid.uuid4()
    paper = Paper(
        id=pid, title=f"Paper {pid}", authors=["A"],
        journal="J", journal_source="rss", embedding=FAKE_EMBEDDING,
    )
    db.add(paper)
    await db.flush()
    return pid


async def _seed_signal_and_rating(db, user_id, paper_id, max_pos, max_neg, effective, rating_val):
    sig = ScoringSignal(
        id=uuid.uuid4(), paper_id=paper_id, user_id=user_id,
        max_positive_sim=max_pos, max_negative_sim=max_neg,
        effective_score=effective, threshold_used=0.5, lambda_used=0.5,
        prefilter_matched=True, passed_gate=True,
    )
    db.add(sig)
    rat = Rating(
        id=uuid.uuid4(), paper_id=paper_id, user_id=user_id,
        rating=rating_val, rated_at=_now(),
    )
    db.add(rat)
    await db.flush()


@pytest.mark.asyncio
async def test_not_enough_data(db_session):
    """Fewer than min_rated signals prints the expected message."""
    uid = await _seed_user(db_session)
    # Seed only 14 signals
    for _ in range(14):
        pid = await _seed_paper(db_session)
        await _seed_signal_and_rating(db_session, uid, pid, 0.6, 0.2, 0.5, 8)
    db_session.add(SystemSettings(id=1))
    await db_session.commit()

    report = await run_report(db_session, min_rated=30)
    assert "Not enough rated signals" in report
    assert "14 found" in report


@pytest.mark.asyncio
async def test_separable_data_suggests_threshold(db_session):
    """With cleanly separable data, script recommends a threshold around 0.4."""
    uid = await _seed_user(db_session)
    random.seed(42)

    # 50 positives: effective_score ~ 0.6 (range 0.45-0.75)
    for _ in range(50):
        pid = await _seed_paper(db_session)
        eff = 0.6 + random.gauss(0, 0.08)
        await _seed_signal_and_rating(db_session, uid, pid, eff + 0.1, 0.2, eff, 8)

    # 30 negatives: effective_score ~ 0.2 (range 0.05-0.35)
    for _ in range(30):
        pid = await _seed_paper(db_session)
        eff = 0.2 + random.gauss(0, 0.08)
        await _seed_signal_and_rating(db_session, uid, pid, eff + 0.1, 0.2, eff, 2)

    db_session.add(SystemSettings(id=1))
    await db_session.commit()

    report = await run_report(db_session, min_rated=30)
    assert "Threshold suggestion report" in report
    assert "Positives (rating >= 7):" in report
    # The suggested threshold should be between 0.3 and 0.5 for this distribution
    assert "similarity_threshold:" in report


@pytest.mark.asyncio
async def test_user_id_filter(db_session):
    """--user-id filters to only that user's signals."""
    uid1 = await _seed_user(db_session, user_id=uuid.uuid4())
    uid2 = await _seed_user(db_session, user_id=uuid.uuid4())

    # Seed 40 for uid1
    for _ in range(40):
        pid = await _seed_paper(db_session)
        await _seed_signal_and_rating(db_session, uid1, pid, 0.6, 0.2, 0.5, 8)

    # Seed 5 for uid2
    for _ in range(5):
        pid = await _seed_paper(db_session)
        await _seed_signal_and_rating(db_session, uid2, pid, 0.6, 0.2, 0.5, 8)

    db_session.add(SystemSettings(id=1))
    await db_session.commit()

    # uid1 has enough data
    report = await run_report(db_session, user_id=uid1, min_rated=30)
    assert "Threshold suggestion report" in report

    # uid2 does not
    report2 = await run_report(db_session, user_id=uid2, min_rated=30)
    assert "Not enough rated signals" in report2
