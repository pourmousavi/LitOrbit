"""Unified feed endpoint combining papers and news items.

GET /api/v1/feed returns a merged, paginated list of papers and news,
filterable by type, source, date, relevance, and sort order.
"""

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, asc, literal, case, null
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.paper import Paper
from app.models.paper_score import PaperScore
from app.models.paper_view import PaperView
from app.models.paper_favorite import PaperFavorite
from app.models.rating import Rating
from app.models.news_item import NewsItem
from app.models.news_source import NewsSource

router = APIRouter(prefix="/api/v1", tags=["feed"])


def _serialize_paper(paper, score, viewed_at, favorited_at, user_rating) -> dict:
    return {
        "item_type": "paper",
        "item_id": str(paper.id),
        "title": paper.title,
        "excerpt": (paper.abstract or "")[:400] if paper.abstract else None,
        "published_at": paper.published_date.isoformat() if paper.published_date else None,
        "relevance_score": float(score) if score else None,
        "source_name": paper.journal,
        "source_id": None,
        "paper": {
            "authors": paper.authors or [],
            "journal": paper.journal,
            "journal_source": paper.journal_source,
            "doi": paper.doi,
            "url": paper.url,
            "keywords": paper.keywords or [],
            "categories": paper.categories or [],
            "early_access": paper.early_access,
            "summary": paper.summary,
            "score_reasoning": None,
        },
        "news": None,
        "user_state": {
            "starred": favorited_at is not None,
            "read": viewed_at is not None,
            "rating": user_rating,
            "sent_to_scholarlib": False,
        },
        "cross_links": [],
        "created_at": paper.created_at.isoformat() if paper.created_at else None,
    }


def _serialize_news(item, source_name, source_authority) -> dict:
    return {
        "item_type": "news",
        "item_id": str(item.id),
        "title": item.title,
        "excerpt": item.excerpt,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "relevance_score": float(item.relevance_score) if item.relevance_score else None,
        "source_name": source_name,
        "source_id": str(item.source_id),
        "paper": None,
        "news": {
            "url": item.url,
            "author": item.author,
            "tags": item.tags or [],
            "categories": item.categories or [],
            "scholarlib_ref_id": item.scholarlib_ref_id,
            "cluster_also_covered_in": [],
        },
        "user_state": {
            "starred": False,
            "read": False,
            "rating": None,
            "sent_to_scholarlib": bool(item.scholarlib_ref_id),
        },
        "cross_links": [],
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/feed")
async def unified_feed(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    type: str = Query("all", pattern="^(all|papers|news)$"),
    sources: str | None = Query(None),
    date_from: date | None = None,
    date_to: date | None = None,
    min_relevance: float | None = None,
    sort: str = Query("relevance", pattern="^(relevance|date_desc|date_asc)$"),
    search: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
) -> dict:
    user_id = user["id"]
    offset = (page - 1) * size

    source_ids = None
    if sources:
        try:
            source_ids = [uuid.UUID(s.strip()) for s in sources.split(",")]
        except ValueError:
            source_ids = None

    items = []
    total_papers = 0
    total_news = 0

    # --- Papers query ---
    if type in ("all", "papers"):
        paper_query = (
            select(
                Paper,
                PaperScore.relevance_score,
                PaperView.viewed_at.label("viewed_at"),
                PaperFavorite.favorited_at.label("favorited_at"),
                Rating.rating.label("user_rating"),
            )
            .join(PaperScore, (PaperScore.paper_id == Paper.id) & (PaperScore.user_id == user_id))
            .outerjoin(PaperView, (PaperView.paper_id == Paper.id) & (PaperView.user_id == user_id))
            .outerjoin(PaperFavorite, (PaperFavorite.paper_id == Paper.id) & (PaperFavorite.user_id == user_id))
            .outerjoin(Rating, (Rating.paper_id == Paper.id) & (Rating.user_id == user_id))
        )

        if date_from:
            paper_query = paper_query.where(Paper.published_date >= date_from)
        if date_to:
            paper_query = paper_query.where(Paper.published_date <= date_to)
        if min_relevance is not None:
            paper_query = paper_query.where(PaperScore.relevance_score >= min_relevance)
        if search:
            term = f"%{search}%"
            paper_query = paper_query.where(
                Paper.title.ilike(term) | Paper.abstract.ilike(term)
            )

        # Count
        count_q = select(func.count()).select_from(paper_query.subquery())
        total_papers = (await db.execute(count_q)).scalar() or 0

        # Fetch all for merging (we paginate after merge)
        paper_results = (await db.execute(paper_query)).all()
        for row in paper_results:
            paper, score, viewed_at, favorited_at, user_rating = row
            items.append(_serialize_paper(paper, score, viewed_at, favorited_at, user_rating))

    # --- News query ---
    if type in ("all", "news"):
        news_query = (
            select(NewsItem, NewsSource.name, NewsSource.authority_weight)
            .join(NewsSource, NewsSource.id == NewsItem.source_id)
            .where(NewsItem.is_cluster_primary == True)
        )

        if source_ids:
            news_query = news_query.where(NewsItem.source_id.in_(source_ids))
        if date_from:
            news_query = news_query.where(func.date(NewsItem.published_at) >= date_from)
        if date_to:
            news_query = news_query.where(func.date(NewsItem.published_at) <= date_to)
        if min_relevance is not None:
            news_query = news_query.where(NewsItem.relevance_score >= min_relevance)
        if search:
            term = f"%{search}%"
            news_query = news_query.where(
                NewsItem.title.ilike(term) | NewsItem.excerpt.ilike(term)
            )

        # Count
        count_q = select(func.count()).select_from(news_query.subquery())
        total_news = (await db.execute(count_q)).scalar() or 0

        # Fetch all for merging
        news_results = (await db.execute(news_query)).all()
        for row in news_results:
            item, source_name, source_authority = row
            items.append(_serialize_news(item, source_name, source_authority))

    # --- Sort ---
    if sort == "relevance":
        items.sort(key=lambda x: (x["relevance_score"] or 0), reverse=True)
    elif sort == "date_desc":
        items.sort(key=lambda x: x["published_at"] or "", reverse=True)
    elif sort == "date_asc":
        items.sort(key=lambda x: x["published_at"] or "")

    # --- Paginate ---
    total = len(items)
    page_items = items[offset:offset + size]

    return {
        "items": page_items,
        "facets": {
            "by_type": {"papers": total_papers, "news": total_news},
        },
        "page": page,
        "size": size,
        "total": total,
    }
