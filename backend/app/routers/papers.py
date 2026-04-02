import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.paper import Paper
from app.models.paper_score import PaperScore

router = APIRouter(prefix="/api/v1/papers", tags=["papers"])


@router.get("")
async def list_papers(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    journal: str | None = None,
    category: str | None = None,
) -> dict:
    """List papers paginated and sorted by the current user's relevance score."""
    user_id = user["id"]
    offset = (page - 1) * per_page

    # Build base query: papers LEFT JOIN scores for this user
    query = (
        select(
            Paper,
            PaperScore.relevance_score,
            PaperScore.score_reasoning,
        )
        .outerjoin(
            PaperScore,
            (PaperScore.paper_id == Paper.id) & (PaperScore.user_id == user_id),
        )
    )

    # Filters
    if journal:
        query = query.where(Paper.journal == journal)
    if category:
        query = query.where(Paper.categories.contains([category]))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Sort by relevance score descending (nulls last), then by created_at
    query = (
        query
        .order_by(desc(PaperScore.relevance_score).nulls_last(), desc(Paper.created_at))
        .offset(offset)
        .limit(per_page)
    )

    results = (await db.execute(query)).all()

    papers = []
    for paper, score, reasoning in results:
        papers.append({
            "id": str(paper.id),
            "doi": paper.doi,
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "journal": paper.journal,
            "journal_source": paper.journal_source,
            "published_date": paper.published_date.isoformat() if paper.published_date else None,
            "early_access": paper.early_access,
            "url": paper.url,
            "categories": paper.categories,
            "summary": paper.summary,
            "relevance_score": score,
            "score_reasoning": reasoning,
            "created_at": paper.created_at.isoformat() if paper.created_at else None,
        })

    return {
        "papers": papers,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{paper_id}")
async def get_paper(
    paper_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a single paper with the current user's score."""
    user_id = user["id"]

    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    result = await db.execute(
        select(
            Paper,
            PaperScore.relevance_score,
            PaperScore.score_reasoning,
        )
        .outerjoin(
            PaperScore,
            (PaperScore.paper_id == Paper.id) & (PaperScore.user_id == user_id),
        )
        .where(Paper.id == pid)
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper, score, reasoning = row
    return {
        "id": str(paper.id),
        "doi": paper.doi,
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "full_text": paper.full_text,
        "journal": paper.journal,
        "journal_source": paper.journal_source,
        "published_date": paper.published_date.isoformat() if paper.published_date else None,
        "early_access": paper.early_access,
        "url": paper.url,
        "pdf_path": paper.pdf_path,
        "categories": paper.categories,
        "summary": paper.summary,
        "relevance_score": score,
        "score_reasoning": reasoning,
        "created_at": paper.created_at.isoformat() if paper.created_at else None,
    }
