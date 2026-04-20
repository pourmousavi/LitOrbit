"""Research Pulse engagement stats endpoint."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.collection import Collection, CollectionPaper
from app.models.paper_score import PaperScore
from app.models.paper_view import PaperView
from app.models.podcast import Podcast
from app.models.rating import Rating
from app.models.share import Share
from app.models.user_profile import UserProfile

router = APIRouter(prefix="/api/v1/engagement", tags=["engagement"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ActivityBreakdown(BaseModel):
    rated: int
    podcasts: int
    collected: int
    shared: int
    opened: int
    login_days: int


class LeaderboardEntry(BaseModel):
    user_id: str
    full_name: str
    points: int
    activity: ActivityBreakdown
    is_current_user: bool


class PulseResponse(BaseModel):
    unreviewed_count: int
    weekly_stats: ActivityBreakdown
    weekly_points: int
    streak: int
    best_streak: int
    lab_total_papers: int
    lab_reviewed: int
    lab_review_pct: float
    leaderboard: list[LeaderboardEntry]
    week_start: str
    last_week_points: int
    last_week_rated: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _week_boundaries(tz: ZoneInfo | None = None) -> tuple[datetime, datetime, datetime, datetime]:
    """Return (this_week_start, this_week_end, last_week_start, last_week_end) as UTC datetimes,
    with week boundaries aligned to the user's local timezone."""
    user_tz = tz or ZoneInfo("Australia/Adelaide")
    now = datetime.now(user_tz)
    # Monday 00:00 of current week in user's timezone, then convert to UTC
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    this_start = datetime(monday.year, monday.month, monday.day, tzinfo=user_tz).astimezone(timezone.utc)
    this_end = this_start + timedelta(days=7)
    last_start = this_start - timedelta(days=7)
    last_end = this_start
    return this_start, this_end, last_start, last_end


async def _count_in_range(db: AsyncSession, stmt, start: datetime, end: datetime) -> int:
    """Execute a count query filtered to a time range.  The stmt must be a
    partially-built select(func.count()) with a .where() placeholder for the
    timestamp filter — so callers pass the full query including the time filter."""
    result = await db.execute(stmt)
    return result.scalar() or 0


async def _user_weekly_stats(
    db: AsyncSession, user_uuid: uuid.UUID, start: datetime, end: datetime,
) -> ActivityBreakdown:
    """Compute activity counts for a single user in a time window."""
    rated = (await db.execute(
        select(func.count()).where(
            Rating.user_id == user_uuid,
            Rating.rated_at >= start,
            Rating.rated_at < end,
        )
    )).scalar() or 0

    podcasts = (await db.execute(
        select(func.count()).where(
            Podcast.user_id == user_uuid,
            Podcast.audio_path.isnot(None),
            Podcast.generated_at >= start,
            Podcast.generated_at < end,
        )
    )).scalar() or 0

    # Collection adds — attribute to the collection owner
    collected = (await db.execute(
        select(func.count()).select_from(CollectionPaper).join(
            Collection, CollectionPaper.collection_id == Collection.id,
        ).where(
            Collection.created_by == user_uuid,
            CollectionPaper.added_at >= start,
            CollectionPaper.added_at < end,
        )
    )).scalar() or 0

    shared = (await db.execute(
        select(func.count()).where(
            Share.shared_by == user_uuid,
            Share.shared_at >= start,
            Share.shared_at < end,
        )
    )).scalar() or 0

    opened = (await db.execute(
        select(func.count()).where(
            PaperView.user_id == user_uuid,
            PaperView.viewed_at >= start,
            PaperView.viewed_at < end,
        )
    )).scalar() or 0

    # Login days: count distinct dates where user had any activity
    # We union the dates from all activity tables
    rating_dates = select(func.date(Rating.rated_at).label("d")).where(
        Rating.user_id == user_uuid, Rating.rated_at >= start, Rating.rated_at < end,
    )
    podcast_dates = select(func.date(Podcast.generated_at).label("d")).where(
        Podcast.user_id == user_uuid, Podcast.generated_at >= start, Podcast.generated_at < end,
    )
    view_dates = select(func.date(PaperView.viewed_at).label("d")).where(
        PaperView.user_id == user_uuid, PaperView.viewed_at >= start, PaperView.viewed_at < end,
    )
    share_dates = select(func.date(Share.shared_at).label("d")).where(
        Share.shared_by == user_uuid, Share.shared_at >= start, Share.shared_at < end,
    )
    union = rating_dates.union_all(podcast_dates, view_dates, share_dates).subquery()
    login_days = (await db.execute(
        select(func.count(func.distinct(union.c.d)))
    )).scalar() or 0

    return ActivityBreakdown(
        rated=rated, podcasts=podcasts, collected=collected,
        shared=shared, opened=opened, login_days=login_days,
    )


def _compute_points(stats: ActivityBreakdown) -> int:
    return (
        stats.rated * 10
        + stats.podcasts * 5
        + stats.collected * 3
        + stats.shared * 5
        + stats.opened * 1
        + stats.login_days * 2
    )


async def compute_streak(db: AsyncSession, user_uuid: uuid.UUID, tz: ZoneInfo | None = None) -> tuple[int, int]:
    """Return (current_streak, best_streak) based on distinct rating dates in user's timezone."""
    user_tz = tz or ZoneInfo("Australia/Adelaide")

    # Fetch all rating timestamps, then convert to user-local dates in Python
    # (avoids DB-specific timezone functions that differ between PostgreSQL and SQLite)
    result = await db.execute(
        select(Rating.rated_at)
        .where(Rating.user_id == user_uuid)
        .order_by(Rating.rated_at.desc())
    )
    raw_timestamps = [row[0] for row in result.all()]

    if not raw_timestamps:
        return 0, 0

    # Convert to distinct local dates
    local_dates: set[date] = set()
    for ts in raw_timestamps:
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        local_dates.add(ts.astimezone(user_tz).date())

    parsed = sorted(local_dates, reverse=True)

    today = datetime.now(user_tz).date()

    # Current streak: start from today or yesterday (grace period)
    current = 0
    if parsed[0] == today:
        anchor = today
    elif parsed[0] == today - timedelta(days=1):
        anchor = today - timedelta(days=1)
    else:
        # Most recent rating is older than yesterday — no active streak
        anchor = None

    if anchor is not None:
        for d in parsed:
            expected = anchor - timedelta(days=current)
            if d == expected:
                current += 1
            elif d < expected:
                break

    # Best streak: scan all dates for longest consecutive run
    best = 0
    run = 1
    for i in range(1, len(parsed)):
        if parsed[i] == parsed[i - 1] - timedelta(days=1):
            run += 1
        else:
            best = max(best, run)
            run = 1
    best = max(best, run)

    return current, best


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/pulse")
async def get_pulse(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PulseResponse:
    user_uuid = uuid.UUID(user["id"])

    # Fetch user's timezone for accurate day/week boundaries
    user_profile = (await db.execute(
        select(UserProfile).where(UserProfile.id == user_uuid)
    )).scalar_one_or_none()
    try:
        user_tz = ZoneInfo(user_profile.digest_timezone) if user_profile and user_profile.digest_timezone else ZoneInfo("Australia/Adelaide")
    except (KeyError, Exception):
        user_tz = ZoneInfo("Australia/Adelaide")

    this_start, this_end, last_start, last_end = _week_boundaries(user_tz)

    # Unreviewed: all papers scored for this user that have not been rated
    rated_paper_ids = select(Rating.paper_id).where(Rating.user_id == user_uuid)
    unreviewed = (await db.execute(
        select(func.count()).select_from(PaperScore).where(
            PaperScore.user_id == user_uuid,
            PaperScore.paper_id.not_in(rated_paper_ids),
        )
    )).scalar() or 0

    # Personal weekly stats
    weekly_stats = await _user_weekly_stats(db, user_uuid, this_start, this_end)
    weekly_points = _compute_points(weekly_stats)

    # Streak (using user's timezone for day boundaries)
    streak, best_streak = await compute_streak(db, user_uuid, user_tz)

    # Lab pulse: papers scored this week (any user) vs papers rated this week (any user)
    lab_total = (await db.execute(
        select(func.count(func.distinct(PaperScore.paper_id))).where(
            PaperScore.scored_at >= this_start,
            PaperScore.scored_at < this_end,
        )
    )).scalar() or 0

    lab_reviewed = (await db.execute(
        select(func.count(func.distinct(Rating.paper_id))).where(
            Rating.rated_at >= this_start,
            Rating.rated_at < this_end,
        )
    )).scalar() or 0

    lab_pct = round(lab_reviewed / lab_total * 100, 1) if lab_total > 0 else 0.0

    # Leaderboard: weekly stats for all users
    users_result = await db.execute(select(UserProfile.id, UserProfile.full_name))
    all_users = users_result.all()

    leaderboard: list[LeaderboardEntry] = []
    for uid, name in all_users:
        stats = await _user_weekly_stats(db, uid, this_start, this_end)
        pts = _compute_points(stats)
        leaderboard.append(LeaderboardEntry(
            user_id=str(uid),
            full_name=name,
            points=pts,
            activity=stats,
            is_current_user=(uid == user_uuid),
        ))
    leaderboard.sort(key=lambda e: e.points, reverse=True)

    # Last week stats for Monday toast
    last_week_stats = await _user_weekly_stats(db, user_uuid, last_start, last_end)
    last_week_points = _compute_points(last_week_stats)

    return PulseResponse(
        unreviewed_count=unreviewed,
        weekly_stats=weekly_stats,
        weekly_points=weekly_points,
        streak=streak,
        best_streak=best_streak,
        lab_total_papers=lab_total,
        lab_reviewed=lab_reviewed,
        lab_review_pct=lab_pct,
        leaderboard=leaderboard,
        week_start=this_start.date().isoformat(),
        last_week_points=last_week_points,
        last_week_rated=last_week_stats.rated,
    )
