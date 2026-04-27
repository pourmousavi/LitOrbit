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
from app.models.user_interaction import UserInteraction

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
    # News engagement
    news_viewed: int = 0
    news_rated: int = 0
    news_starred: int = 0


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
    lifetime_points: int
    streak: int
    best_streak: int
    lab_total_papers: int
    lab_reviewed: int
    lab_review_pct: float
    leaderboard: list[LeaderboardEntry]
    week_start: str
    prior_7d_points: int
    prior_7d_rated: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rolling_windows() -> tuple[datetime, datetime, datetime, datetime]:
    """Return (this_start, this_end, prior_start, prior_end) as UTC datetimes
    for two contiguous rolling 7-day windows ending now.

    No timezone alignment is needed because the windows slide continuously
    instead of resetting at a calendar boundary.
    """
    now = datetime.now(timezone.utc)
    this_end = now
    this_start = now - timedelta(days=7)
    prior_end = this_start
    prior_start = this_start - timedelta(days=7)
    return this_start, this_end, prior_start, prior_end


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

    # News interactions
    news_viewed = (await db.execute(
        select(func.count()).where(
            UserInteraction.user_id == user_uuid,
            UserInteraction.content_type == "news",
            UserInteraction.event_type == "marked_read",
            UserInteraction.created_at >= start,
            UserInteraction.created_at < end,
        )
    )).scalar() or 0

    news_rated = (await db.execute(
        select(func.count()).where(
            UserInteraction.user_id == user_uuid,
            UserInteraction.content_type == "news",
            UserInteraction.event_type == "rated",
            UserInteraction.created_at >= start,
            UserInteraction.created_at < end,
        )
    )).scalar() or 0

    news_starred = (await db.execute(
        select(func.count()).where(
            UserInteraction.user_id == user_uuid,
            UserInteraction.content_type == "news",
            UserInteraction.event_type == "starred",
            UserInteraction.created_at >= start,
            UserInteraction.created_at < end,
        )
    )).scalar() or 0

    return ActivityBreakdown(
        rated=rated, podcasts=podcasts, collected=collected,
        shared=shared, opened=opened, login_days=login_days,
        news_viewed=news_viewed, news_rated=news_rated, news_starred=news_starred,
    )


def _compute_points(stats: ActivityBreakdown) -> int:
    return (
        stats.rated * 10
        + stats.podcasts * 5
        + stats.collected * 3
        + stats.shared * 5
        + stats.opened * 1
        + stats.login_days * 2
        # News events (same weight parity as papers per OP6)
        + stats.news_viewed * 1
        + stats.news_rated * 2
        + stats.news_starred * 3
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

    this_start, this_end, prior_start, prior_end = _rolling_windows()

    # Unreviewed: all papers scored for this user that have not been rated
    rated_paper_ids = select(Rating.paper_id).where(Rating.user_id == user_uuid)
    unreviewed = (await db.execute(
        select(func.count()).select_from(PaperScore).where(
            PaperScore.user_id == user_uuid,
            PaperScore.paper_id.not_in(rated_paper_ids),
        )
    )).scalar() or 0

    # Rolling 7-day stats
    weekly_stats = await _user_weekly_stats(db, user_uuid, this_start, this_end)
    weekly_points = _compute_points(weekly_stats)

    # Lifetime stats — pass an effectively-unbounded window
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    far_future = datetime(9999, 1, 1, tzinfo=timezone.utc)
    lifetime_stats = await _user_weekly_stats(db, user_uuid, epoch, far_future)
    lifetime_points = _compute_points(lifetime_stats)

    # Streak (using user's timezone for day boundaries)
    streak, best_streak = await compute_streak(db, user_uuid, user_tz)

    # Lab pulse: papers scored / rated within the rolling 7-day window
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

    # Leaderboard: rolling-7-day stats for all users
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

    # Prior 7-day window (now-14d → now-7d) for week-over-week deltas + Monday toast
    prior_stats = await _user_weekly_stats(db, user_uuid, prior_start, prior_end)
    prior_7d_points = _compute_points(prior_stats)

    return PulseResponse(
        unreviewed_count=unreviewed,
        weekly_stats=weekly_stats,
        weekly_points=weekly_points,
        lifetime_points=lifetime_points,
        streak=streak,
        best_streak=best_streak,
        lab_total_papers=lab_total,
        lab_reviewed=lab_reviewed,
        lab_review_pct=lab_pct,
        leaderboard=leaderboard,
        week_start=this_start.date().isoformat(),
        prior_7d_points=prior_7d_points,
        prior_7d_rated=prior_stats.rated,
    )
