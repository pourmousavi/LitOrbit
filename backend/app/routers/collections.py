import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, desc, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, check_owner_or_admin
from app.database import get_db
from app.models.collection import Collection, CollectionPaper
from app.models.paper import Paper
from app.models.paper_score import PaperScore
from app.models.podcast import Podcast

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None
    color: str = "#0891b2"


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class AddPaperRequest(BaseModel):
    paper_id: str


@router.get("")
async def list_collections(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all collections with paper counts, podcast counts, and stats."""
    user_id = user["id"]

    # Base query: collection + paper count
    result = await db.execute(
        select(
            Collection,
            func.count(CollectionPaper.id).label("paper_count"),
        )
        .outerjoin(CollectionPaper, CollectionPaper.collection_id == Collection.id)
        .group_by(Collection.id)
        .order_by(Collection.name)
    )
    rows = result.all()

    if not rows:
        return []

    col_ids = [col.id for col, _ in rows]

    # Podcast counts per collection (single vs dual)
    podcast_result = await db.execute(
        select(
            CollectionPaper.collection_id,
            func.count(case((Podcast.voice_mode == "single", 1))).label("single_count"),
            func.count(case((Podcast.voice_mode == "dual", 1))).label("dual_count"),
        )
        .join(Podcast, Podcast.paper_id == CollectionPaper.paper_id)
        .where(CollectionPaper.collection_id.in_(col_ids), Podcast.audio_path.isnot(None))
        .group_by(CollectionPaper.collection_id)
    )
    podcast_map: dict[str, dict] = {}
    for cid, single, dual in podcast_result.all():
        podcast_map[str(cid)] = {"single": single, "dual": dual}

    # Last updated (most recent paper added_at) per collection
    last_updated_result = await db.execute(
        select(
            CollectionPaper.collection_id,
            func.max(CollectionPaper.added_at).label("last_updated"),
        )
        .where(CollectionPaper.collection_id.in_(col_ids))
        .group_by(CollectionPaper.collection_id)
    )
    last_updated_map: dict[str, str | None] = {}
    for cid, last_dt in last_updated_result.all():
        last_updated_map[str(cid)] = last_dt.isoformat() if last_dt else None

    # Top categories per collection (unnest paper categories, count, take top 3)
    cat_result = await db.execute(text("""
        SELECT cp.collection_id, cat, COUNT(*) as cnt
        FROM collection_papers cp
        JOIN papers p ON p.id = cp.paper_id
        CROSS JOIN LATERAL unnest(p.categories) AS cat
        WHERE cp.collection_id = ANY(:col_ids)
        GROUP BY cp.collection_id, cat
        ORDER BY cp.collection_id, cnt DESC
    """), {"col_ids": [str(c) for c in col_ids]})
    top_cats_map: dict[str, list[str]] = {}
    for cid, cat, cnt in cat_result.all():
        key = str(cid)
        if key not in top_cats_map:
            top_cats_map[key] = []
        if len(top_cats_map[key]) < 3:
            top_cats_map[key].append(cat)

    # Avg relevance score per collection
    score_result = await db.execute(
        select(
            CollectionPaper.collection_id,
            func.avg(PaperScore.relevance_score).label("avg_score"),
        )
        .join(PaperScore, (PaperScore.paper_id == CollectionPaper.paper_id) & (PaperScore.user_id == user_id))
        .where(CollectionPaper.collection_id.in_(col_ids))
        .group_by(CollectionPaper.collection_id)
    )
    score_map: dict[str, float | None] = {}
    for cid, avg_score in score_result.all():
        score_map[str(cid)] = round(float(avg_score), 1) if avg_score else None

    # Summarized paper count per collection
    summary_result = await db.execute(
        select(
            CollectionPaper.collection_id,
            func.count(Paper.id).label("summarized_count"),
        )
        .join(Paper, Paper.id == CollectionPaper.paper_id)
        .where(CollectionPaper.collection_id.in_(col_ids), Paper.summary.isnot(None))
        .group_by(CollectionPaper.collection_id)
    )
    summary_map: dict[str, int] = {}
    for cid, cnt in summary_result.all():
        summary_map[str(cid)] = cnt

    return [
        {
            "id": str(col.id),
            "name": col.name,
            "description": col.description,
            "color": col.color,
            "paper_count": count,
            "podcast_count_single": podcast_map.get(str(col.id), {}).get("single", 0),
            "podcast_count_dual": podcast_map.get(str(col.id), {}).get("dual", 0),
            "last_updated": last_updated_map.get(str(col.id)),
            "top_categories": top_cats_map.get(str(col.id), []),
            "avg_relevance_score": score_map.get(str(col.id)),
            "summarized_count": summary_map.get(str(col.id), 0),
            "created_at": col.created_at.isoformat() if col.created_at else None,
        }
        for col, count in rows
    ]


@router.post("")
async def create_collection(
    req: CollectionCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new collection."""
    col = Collection(
        id=uuid.uuid4(),
        name=req.name,
        description=req.description,
        color=req.color,
        created_by=uuid.UUID(user["id"]),
    )
    db.add(col)
    await db.commit()
    return {"id": str(col.id), "status": "created"}


@router.patch("/{collection_id}")
async def update_collection(
    collection_id: str,
    req: CollectionUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a collection."""
    result = await db.execute(select(Collection).where(Collection.id == uuid.UUID(collection_id)))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    check_owner_or_admin(col.created_by, user)

    if req.name is not None:
        col.name = req.name
    if req.description is not None:
        col.description = req.description
    if req.color is not None:
        col.color = req.color

    await db.commit()
    return {"status": "updated"}


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a collection (papers are NOT deleted)."""
    result = await db.execute(select(Collection).where(Collection.id == uuid.UUID(collection_id)))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    check_owner_or_admin(col.created_by, user)
    await db.delete(col)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{collection_id}/papers")
async def add_paper_to_collection(
    collection_id: str,
    req: AddPaperRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a paper to a collection."""
    # Check collection exists and ownership
    col = (await db.execute(select(Collection).where(Collection.id == uuid.UUID(collection_id)))).scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    check_owner_or_admin(col.created_by, user)

    # Check paper exists
    paper = (await db.execute(select(Paper).where(Paper.id == uuid.UUID(req.paper_id)))).scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Check not already added
    existing = (await db.execute(
        select(CollectionPaper).where(
            CollectionPaper.collection_id == uuid.UUID(collection_id),
            CollectionPaper.paper_id == uuid.UUID(req.paper_id),
        )
    )).scalar_one_or_none()
    if existing:
        return {"status": "already_added"}

    cp = CollectionPaper(
        id=uuid.uuid4(),
        collection_id=uuid.UUID(collection_id),
        paper_id=uuid.UUID(req.paper_id),
    )
    db.add(cp)
    await db.commit()
    return {"status": "added"}


@router.delete("/{collection_id}/papers/{paper_id}")
async def remove_paper_from_collection(
    collection_id: str,
    paper_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a paper from a collection."""
    # Check collection ownership
    col = (await db.execute(select(Collection).where(Collection.id == uuid.UUID(collection_id)))).scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    check_owner_or_admin(col.created_by, user)

    result = await db.execute(
        select(CollectionPaper).where(
            CollectionPaper.collection_id == uuid.UUID(collection_id),
            CollectionPaper.paper_id == uuid.UUID(paper_id),
        )
    )
    cp = result.scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail="Paper not in collection")
    await db.delete(cp)
    await db.commit()
    return {"status": "removed"}


@router.get("/{collection_id}/papers")
async def list_collection_papers(
    collection_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List papers in a collection with scores."""
    user_id = user["id"]

    result = await db.execute(
        select(Paper, PaperScore.relevance_score, PaperScore.score_reasoning)
        .join(CollectionPaper, CollectionPaper.paper_id == Paper.id)
        .outerjoin(PaperScore, (PaperScore.paper_id == Paper.id) & (PaperScore.user_id == user_id))
        .where(CollectionPaper.collection_id == uuid.UUID(collection_id))
        .order_by(desc(PaperScore.relevance_score).nulls_last(), desc(Paper.created_at))
    )
    rows = result.all()

    return {
        "papers": [
            {
                "id": str(paper.id),
                "doi": paper.doi,
                "title": paper.title,
                "authors": paper.authors,
                "abstract": paper.abstract,
                "journal": paper.journal,
                "journal_source": paper.journal_source,
                "published_date": paper.published_date.isoformat() if paper.published_date else None,
                "online_date": paper.online_date.isoformat() if paper.online_date else None,
                "early_access": paper.early_access,
                "url": paper.url,
                "keywords": paper.keywords or [],
                "categories": paper.categories,
                "summary": paper.summary,
                "relevance_score": score,
                "score_reasoning": reasoning,
                "created_at": paper.created_at.isoformat() if paper.created_at else None,
            }
            for paper, score, reasoning in rows
        ],
        "total": len(rows),
    }


@router.get("/paper/{paper_id}")
async def get_paper_collections(
    paper_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all collections a paper belongs to."""
    result = await db.execute(
        select(Collection)
        .join(CollectionPaper, CollectionPaper.collection_id == Collection.id)
        .where(CollectionPaper.paper_id == uuid.UUID(paper_id))
        .order_by(Collection.name)
    )
    collections = result.scalars().all()
    return [
        {"id": str(c.id), "name": c.name, "color": c.color}
        for c in collections
    ]
