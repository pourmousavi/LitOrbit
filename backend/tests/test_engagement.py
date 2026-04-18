"""Tests for the Research Pulse engagement endpoint."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.models.paper import Paper
from app.models.paper_score import PaperScore
from app.models.paper_view import PaperView
from app.models.rating import Rating
from app.models.podcast import Podcast
from app.models.share import Share
from app.models.collection import Collection, CollectionPaper
from app.models.user_profile import UserProfile
from app.routers.engagement import compute_streak, _user_weekly_stats, _compute_points, _week_boundaries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> datetime:
    return _now() - timedelta(days=n)


async def _seed_user(db, user_id=None, full_name="Test User", email="test@test.com"):
    uid = user_id or uuid.uuid4()
    profile = UserProfile(id=uid, full_name=full_name, email=email, role="researcher")
    db.add(profile)
    await db.flush()
    return uid


async def _seed_paper(db, paper_id=None):
    pid = paper_id or uuid.uuid4()
    paper = Paper(
        id=pid, doi=f"10.1000/{pid}", title=f"Paper {pid}",
        authors=["Author A"], journal="Test Journal",
        journal_source="test", url="http://example.com",
    )
    db.add(paper)
    await db.flush()
    return pid


async def _seed_rating(db, user_id, paper_id, rated_at=None):
    rating = Rating(
        id=uuid.uuid4(), paper_id=paper_id, user_id=user_id,
        rating=7, rated_at=rated_at or _now(),
    )
    db.add(rating)
    await db.flush()
    return rating


async def _seed_score(db, user_id, paper_id):
    score = PaperScore(
        id=uuid.uuid4(), paper_id=paper_id, user_id=user_id,
        relevance_score=7.5, scored_at=_now(),
    )
    db.add(score)
    await db.flush()
    return score


# ===================================================================
# STREAK TESTS (8 tests)
# ===================================================================

@pytest.mark.asyncio
async def test_streak_no_ratings(db_session):
    uid = await _seed_user(db_session)
    await db_session.commit()
    current, best = await compute_streak(db_session, uid)
    assert current == 0
    assert best == 0


@pytest.mark.asyncio
async def test_streak_rated_today_only(db_session):
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, pid, rated_at=_now())
    await db_session.commit()
    current, best = await compute_streak(db_session, uid)
    assert current == 1


@pytest.mark.asyncio
async def test_streak_today_and_yesterday(db_session):
    uid = await _seed_user(db_session)
    for i in range(2):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rated_at=_days_ago(i))
    await db_session.commit()
    current, best = await compute_streak(db_session, uid)
    assert current == 2


@pytest.mark.asyncio
async def test_streak_three_consecutive_days(db_session):
    uid = await _seed_user(db_session)
    for i in range(3):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rated_at=_days_ago(i))
    await db_session.commit()
    current, best = await compute_streak(db_session, uid)
    assert current == 3


@pytest.mark.asyncio
async def test_streak_gap_resets(db_session):
    """Rated today and 3 days ago (not yesterday) → current=1."""
    uid = await _seed_user(db_session)
    p1 = await _seed_paper(db_session)
    p2 = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, p1, rated_at=_now())
    await _seed_rating(db_session, uid, p2, rated_at=_days_ago(3))
    await db_session.commit()
    current, best = await compute_streak(db_session, uid)
    assert current == 1


@pytest.mark.asyncio
async def test_streak_yesterday_grace(db_session):
    """Rated yesterday only (not today) → current=1 due to grace period."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, pid, rated_at=_days_ago(1))
    await db_session.commit()
    current, best = await compute_streak(db_session, uid)
    assert current == 1


@pytest.mark.asyncio
async def test_streak_multiple_ratings_same_day(db_session):
    """3 ratings today → still counts as streak=1."""
    uid = await _seed_user(db_session)
    for _ in range(3):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rated_at=_now())
    await db_session.commit()
    current, best = await compute_streak(db_session, uid)
    assert current == 1


@pytest.mark.asyncio
async def test_streak_best_tracking(db_session):
    """5 consecutive days last week, gap, then 2 days this week → current=2, best=5."""
    uid = await _seed_user(db_session)
    # 5 consecutive days starting 10 days ago (days 10,9,8,7,6)
    for i in range(6, 11):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rated_at=_days_ago(i))
    # 2 consecutive days: today and yesterday
    for i in range(2):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid, pid, rated_at=_days_ago(i))
    await db_session.commit()
    current, best = await compute_streak(db_session, uid)
    assert current == 2
    assert best == 5


# ===================================================================
# POINTS TESTS (8 tests)
# ===================================================================

@pytest.mark.asyncio
async def test_points_rating(db_session):
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, pid, rated_at=_now())
    await db_session.commit()
    this_start, this_end, _, _ = _week_boundaries()
    stats = await _user_weekly_stats(db_session, uid, this_start, this_end)
    assert stats.rated == 1
    assert _compute_points(stats) >= 10


@pytest.mark.asyncio
async def test_points_podcast(db_session):
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    db_session.add(Podcast(
        id=uuid.uuid4(), paper_id=pid, user_id=uid,
        audio_path="https://storage.example.com/test.mp3",
        generated_at=_now(),
    ))
    await db_session.commit()
    this_start, this_end, _, _ = _week_boundaries()
    stats = await _user_weekly_stats(db_session, uid, this_start, this_end)
    assert stats.podcasts == 1
    pts = _compute_points(stats)
    assert pts >= 5


@pytest.mark.asyncio
async def test_points_collection(db_session):
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    col = Collection(id=uuid.uuid4(), name="Test Col", created_by=uid)
    db_session.add(col)
    await db_session.flush()
    db_session.add(CollectionPaper(
        id=uuid.uuid4(), collection_id=col.id, paper_id=pid, added_at=_now(),
    ))
    await db_session.commit()
    this_start, this_end, _, _ = _week_boundaries()
    stats = await _user_weekly_stats(db_session, uid, this_start, this_end)
    assert stats.collected == 1
    assert _compute_points(stats) >= 3


@pytest.mark.asyncio
async def test_points_share(db_session):
    uid = await _seed_user(db_session)
    uid2 = await _seed_user(db_session, full_name="User 2", email="u2@test.com")
    pid = await _seed_paper(db_session)
    db_session.add(Share(
        id=uuid.uuid4(), paper_id=pid, shared_by=uid, shared_with=uid2,
        shared_at=_now(),
    ))
    await db_session.commit()
    this_start, this_end, _, _ = _week_boundaries()
    stats = await _user_weekly_stats(db_session, uid, this_start, this_end)
    assert stats.shared == 1
    assert _compute_points(stats) >= 5


@pytest.mark.asyncio
async def test_points_opened(db_session):
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    db_session.add(PaperView(user_id=uid, paper_id=pid, viewed_at=_now()))
    await db_session.commit()
    this_start, this_end, _, _ = _week_boundaries()
    stats = await _user_weekly_stats(db_session, uid, this_start, this_end)
    assert stats.opened == 1
    assert _compute_points(stats) >= 1


@pytest.mark.asyncio
async def test_points_combined(db_session):
    """2 ratings + 1 podcast + 1 collection = 2*10 + 5 + 3 = 28 + login_days*2."""
    uid = await _seed_user(db_session)
    p1 = await _seed_paper(db_session)
    p2 = await _seed_paper(db_session)
    p3 = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, p1, rated_at=_now())
    await _seed_rating(db_session, uid, p2, rated_at=_now())
    db_session.add(Podcast(
        id=uuid.uuid4(), paper_id=p3, user_id=uid,
        audio_path="https://example.com/a.mp3", generated_at=_now(),
    ))
    col = Collection(id=uuid.uuid4(), name="C", created_by=uid)
    db_session.add(col)
    await db_session.flush()
    db_session.add(CollectionPaper(
        id=uuid.uuid4(), collection_id=col.id, paper_id=p1, added_at=_now(),
    ))
    await db_session.commit()
    this_start, this_end, _, _ = _week_boundaries()
    stats = await _user_weekly_stats(db_session, uid, this_start, this_end)
    base_points = stats.rated * 10 + stats.podcasts * 5 + stats.collected * 3
    assert base_points == 28
    total = _compute_points(stats)
    assert total >= 28  # login_days adds more


@pytest.mark.asyncio
async def test_points_only_current_week(db_session):
    """Rating this week counts; rating last week does not."""
    uid = await _seed_user(db_session)
    p1 = await _seed_paper(db_session)
    p2 = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, p1, rated_at=_now())
    await _seed_rating(db_session, uid, p2, rated_at=_days_ago(10))
    await db_session.commit()
    this_start, this_end, _, _ = _week_boundaries()
    stats = await _user_weekly_stats(db_session, uid, this_start, this_end)
    assert stats.rated == 1


@pytest.mark.asyncio
async def test_points_previous_week_excluded(db_session):
    """All actions last week → current week stats = 0."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, pid, rated_at=_days_ago(10))
    await db_session.commit()
    this_start, this_end, _, _ = _week_boundaries()
    stats = await _user_weekly_stats(db_session, uid, this_start, this_end)
    assert stats.rated == 0
    assert _compute_points(stats) == 0


# ===================================================================
# UNREVIEWED COUNT TESTS (4 tests)
# ===================================================================

@pytest.mark.asyncio
async def test_unreviewed_5_scored_0_rated(test_client, db_session):
    uid = uuid.uuid4()
    await _seed_user(db_session, user_id=uid)
    for _ in range(5):
        pid = await _seed_paper(db_session)
        await _seed_score(db_session, uid, pid)
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid), "email": "t@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    assert resp.status_code == 200
    assert resp.json()["unreviewed_count"] == 5


@pytest.mark.asyncio
async def test_unreviewed_5_scored_3_rated(test_client, db_session):
    uid = uuid.uuid4()
    await _seed_user(db_session, user_id=uid)
    paper_ids = []
    for _ in range(5):
        pid = await _seed_paper(db_session)
        await _seed_score(db_session, uid, pid)
        paper_ids.append(pid)
    # Rate 3 of them
    for pid in paper_ids[:3]:
        await _seed_rating(db_session, uid, pid)
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid), "email": "t@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    assert resp.json()["unreviewed_count"] == 2


@pytest.mark.asyncio
async def test_unreviewed_all_rated(test_client, db_session):
    uid = uuid.uuid4()
    await _seed_user(db_session, user_id=uid)
    for _ in range(5):
        pid = await _seed_paper(db_session)
        await _seed_score(db_session, uid, pid)
        await _seed_rating(db_session, uid, pid)
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid), "email": "t@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    assert resp.json()["unreviewed_count"] == 0


@pytest.mark.asyncio
async def test_unreviewed_no_scores(test_client, db_session):
    """Papers exist but no PaperScore for user → unreviewed = 0."""
    uid = uuid.uuid4()
    await _seed_user(db_session, user_id=uid)
    await _seed_paper(db_session)
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid), "email": "t@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    assert resp.json()["unreviewed_count"] == 0


# ===================================================================
# LAB PULSE TESTS (4 tests)
# ===================================================================

@pytest.mark.asyncio
async def test_lab_aggregate_multiple_users(test_client, db_session):
    """Two users rating different papers → lab_reviewed counts unique papers."""
    uid1 = uuid.uuid4()
    uid2 = uuid.uuid4()
    await _seed_user(db_session, user_id=uid1, full_name="User 1", email="u1@t.com")
    await _seed_user(db_session, user_id=uid2, full_name="User 2", email="u2@t.com")
    p1 = await _seed_paper(db_session)
    p2 = await _seed_paper(db_session)
    p3 = await _seed_paper(db_session)
    # Score all papers for both users so they show as "this week" papers
    for uid in [uid1, uid2]:
        for pid in [p1, p2, p3]:
            await _seed_score(db_session, uid, pid)
    # User1 rates p1, User2 rates p2
    await _seed_rating(db_session, uid1, p1, rated_at=_now())
    await _seed_rating(db_session, uid2, p2, rated_at=_now())
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid1), "email": "u1@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    data = resp.json()
    assert data["lab_reviewed"] == 2  # 2 unique papers rated


@pytest.mark.asyncio
async def test_lab_review_percentage(test_client, db_session):
    uid = uuid.uuid4()
    await _seed_user(db_session, user_id=uid)
    papers = []
    for _ in range(10):
        pid = await _seed_paper(db_session)
        await _seed_score(db_session, uid, pid)
        papers.append(pid)
    # Rate 5 of 10
    for pid in papers[:5]:
        await _seed_rating(db_session, uid, pid, rated_at=_now())
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid), "email": "t@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    data = resp.json()
    assert data["lab_total_papers"] == 10
    assert data["lab_reviewed"] == 5
    assert data["lab_review_pct"] == 50.0


@pytest.mark.asyncio
async def test_leaderboard_sorted_by_points(test_client, db_session):
    uid1 = uuid.uuid4()
    uid2 = uuid.uuid4()
    uid3 = uuid.uuid4()
    await _seed_user(db_session, user_id=uid1, full_name="Alice", email="a@t.com")
    await _seed_user(db_session, user_id=uid2, full_name="Bob", email="b@t.com")
    await _seed_user(db_session, user_id=uid3, full_name="Carol", email="c@t.com")
    # Alice: 3 ratings, Bob: 1 rating, Carol: 0
    for _ in range(3):
        pid = await _seed_paper(db_session)
        await _seed_rating(db_session, uid1, pid, rated_at=_now())
    pid = await _seed_paper(db_session)
    await _seed_rating(db_session, uid2, pid, rated_at=_now())
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid1), "email": "a@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    lb = resp.json()["leaderboard"]
    assert lb[0]["full_name"] == "Alice"
    assert lb[1]["full_name"] == "Bob"
    assert lb[0]["points"] > lb[1]["points"]
    assert lb[1]["points"] > lb[2]["points"] or lb[1]["points"] >= lb[2]["points"]


@pytest.mark.asyncio
async def test_leaderboard_current_user_marked(test_client, db_session):
    uid1 = uuid.uuid4()
    uid2 = uuid.uuid4()
    await _seed_user(db_session, user_id=uid1, full_name="Me", email="me@t.com")
    await _seed_user(db_session, user_id=uid2, full_name="Other", email="other@t.com")
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid1), "email": "me@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    lb = resp.json()["leaderboard"]
    current_users = [e for e in lb if e["is_current_user"]]
    assert len(current_users) == 1
    assert current_users[0]["user_id"] == str(uid1)


# ===================================================================
# API ENDPOINT TESTS (4 tests)
# ===================================================================

@pytest.mark.asyncio
async def test_pulse_returns_200(test_client, db_session):
    uid = uuid.uuid4()
    await _seed_user(db_session, user_id=uid)
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid), "email": "t@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    assert resp.status_code == 200
    data = resp.json()
    expected_keys = {
        "unreviewed_count", "weekly_stats", "weekly_points", "streak",
        "best_streak", "lab_total_papers", "lab_reviewed", "lab_review_pct",
        "leaderboard", "week_start", "last_week_points", "last_week_rated",
    }
    assert expected_keys.issubset(set(data.keys()))


@pytest.mark.asyncio
async def test_pulse_requires_auth(test_client):
    resp = await test_client.get("/api/v1/engagement/pulse")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_pulse_empty_state(test_client, db_session):
    uid = uuid.uuid4()
    await _seed_user(db_session, user_id=uid)
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid), "email": "t@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    data = resp.json()
    assert data["unreviewed_count"] == 0
    assert data["weekly_points"] == 0
    assert data["streak"] == 0
    assert data["best_streak"] == 0
    assert data["lab_total_papers"] == 0
    assert data["lab_reviewed"] == 0
    assert data["lab_review_pct"] == 0.0


@pytest.mark.asyncio
async def test_pulse_weekly_boundary(test_client, db_session):
    """Rating on Monday 00:01 counts; previous Sunday 23:59 does not."""
    uid = uuid.uuid4()
    await _seed_user(db_session, user_id=uid)

    this_start, this_end, _, _ = _week_boundaries()
    # Paper rated at start of current week (Monday 00:01)
    p1 = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, p1, rated_at=this_start + timedelta(minutes=1))
    # Paper rated at end of current week (Sunday 23:58)
    p2 = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, p2, rated_at=this_end - timedelta(minutes=2))
    # Paper rated previous Sunday 23:59 (just before this week)
    p3 = await _seed_paper(db_session)
    await _seed_rating(db_session, uid, p3, rated_at=this_start - timedelta(minutes=1))
    await db_session.commit()

    from app.auth import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uid), "email": "t@t.com", "role": "researcher"}
    resp = await test_client.get("/api/v1/engagement/pulse")
    del app.dependency_overrides[get_current_user]
    data = resp.json()
    assert data["weekly_stats"]["rated"] == 2  # Monday + Sunday of this week
