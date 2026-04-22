import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func, desc, cast, ARRAY, String, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, check_owner_or_admin
from app.database import get_db
from app.models.paper import Paper
from app.models.paper_score import PaperScore
from app.models.paper_view import PaperView
from app.models.paper_favorite import PaperFavorite
from app.models.rating import Rating
from app.models.user_profile import UserProfile

router = APIRouter(prefix="/api/v1/papers", tags=["papers"])


@router.get("")
async def list_papers(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    journal: str | None = None,
    category: str | None = None,
    search: str | None = None,
    sort: str | None = Query(None, pattern="^(score|newest|oldest|published)$"),
    favorites: bool = False,
) -> dict:
    """List papers paginated with configurable sort order."""
    user_id = user["id"]
    offset = (page - 1) * per_page

    # INNER JOIN on PaperScore: only show papers that have been scored for
    # this user.  Papers are saved to the DB before scoring completes, so a
    # LEFT JOIN would expose unscored papers (NULL relevance_score) in the
    # feed.  Scoring always retries unscored papers on the next pipeline run
    # (runner.py loads ALL papers and checks for missing score pairs), so
    # nothing is lost — papers just appear once scoring finishes.
    creator = select(UserProfile.full_name).where(UserProfile.id == Paper.created_by).correlate(Paper).scalar_subquery()
    query = (
        select(
            Paper,
            PaperScore.relevance_score,
            PaperScore.score_reasoning,
            creator.label("created_by_name"),
            PaperView.viewed_at.label("viewed_at"),
            PaperFavorite.favorited_at.label("favorited_at"),
            Rating.rating.label("user_rating"),
        )
        .join(
            PaperScore,
            (PaperScore.paper_id == Paper.id) & (PaperScore.user_id == user_id),
        )
        .outerjoin(
            PaperView,
            (PaperView.paper_id == Paper.id) & (PaperView.user_id == user_id),
        )
        .outerjoin(
            PaperFavorite,
            (PaperFavorite.paper_id == Paper.id) & (PaperFavorite.user_id == user_id),
        )
        .outerjoin(
            Rating,
            (Rating.paper_id == Paper.id) & (Rating.user_id == user_id),
        )
    )

    if favorites:
        query = query.where(PaperFavorite.favorited_at.isnot(None))

    # Filters
    if journal:
        query = query.where(Paper.journal == journal)
    if category:
        query = query.where(
            func.array_to_string(Paper.categories, '||').ilike(f"%{category}%")
        )
    if search:
        term = f"%{search}%"
        query = query.where(
            Paper.title.ilike(term)
            | Paper.abstract.ilike(term)
            | Paper.journal.ilike(term)
            | Paper.doi.ilike(term)
            | func.array_to_string(Paper.authors, ' ').ilike(term)
            | func.array_to_string(Paper.categories, ' ').ilike(term)
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Sort
    if sort == "newest":
        query = query.order_by(desc(Paper.created_at))
    elif sort == "oldest":
        query = query.order_by(Paper.created_at)
    elif sort == "published":
        query = query.order_by(desc(Paper.published_date).nulls_last(), desc(Paper.created_at))
    else:  # default: score
        query = query.order_by(desc(PaperScore.relevance_score).nulls_last(), desc(Paper.created_at))

    query = query.offset(offset).limit(per_page)

    results = (await db.execute(query)).all()

    # Bulk fetch collection memberships for these papers
    from app.models.collection import Collection, CollectionPaper
    paper_ids_in_page = [row[0].id for row in results]
    collections_map: dict[str, list[dict]] = {}
    if paper_ids_in_page:
        col_result = await db.execute(
            select(CollectionPaper.paper_id, Collection.id, Collection.name, Collection.color)
            .join(Collection, Collection.id == CollectionPaper.collection_id)
            .where(
                CollectionPaper.paper_id.in_(paper_ids_in_page),
                (Collection.visibility == "shared") | (Collection.created_by == uuid.UUID(user_id)),
            )
        )
        for pid, cid, cname, ccolor in col_result.all():
            collections_map.setdefault(str(pid), []).append({"id": str(cid), "name": cname, "color": ccolor})

    papers = []
    for row in results:
        paper, score, reasoning, creator_name, viewed_at, favorited_at, user_rating = row
        papers.append({
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
            "collections": collections_map.get(str(paper.id), []),
            "created_by_name": creator_name or "System",
            "is_opened": viewed_at is not None,
            "is_favorite": favorited_at is not None,
            "user_rating": user_rating,
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

    creator_sq = select(UserProfile.full_name).where(UserProfile.id == Paper.created_by).correlate(Paper).scalar_subquery()
    result = await db.execute(
        select(
            Paper,
            PaperScore.relevance_score,
            PaperScore.score_reasoning,
            creator_sq.label("created_by_name"),
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

    paper, score, reasoning, creator_name = row

    # Record that this user has opened the paper (idempotent)
    existing_view = await db.execute(
        select(PaperView).where(
            (PaperView.paper_id == pid) & (PaperView.user_id == uuid.UUID(user_id))
        )
    )
    if existing_view.scalar_one_or_none() is None:
        db.add(PaperView(paper_id=pid, user_id=uuid.UUID(user_id)))
        await db.commit()

    fav_result = await db.execute(
        select(PaperFavorite).where(
            (PaperFavorite.paper_id == pid) & (PaperFavorite.user_id == uuid.UUID(user_id))
        )
    )
    is_favorite = fav_result.scalar_one_or_none() is not None
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
        "online_date": paper.online_date.isoformat() if paper.online_date else None,
        "early_access": paper.early_access,
        "url": paper.url,
        "pdf_path": paper.pdf_path,
        "keywords": paper.keywords or [],
        "categories": paper.categories,
        "summary": paper.summary,
        "relevance_score": score,
        "score_reasoning": reasoning,
        "created_at": paper.created_at.isoformat() if paper.created_at else None,
        "created_by_name": creator_name or "System",
        "is_favorite": is_favorite,
    }


@router.post("/{paper_id}/favorite")
async def add_favorite(
    paper_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a paper as favorite for the current user (idempotent)."""
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    uid = uuid.UUID(user["id"])
    existing = await db.execute(
        select(PaperFavorite).where(
            (PaperFavorite.paper_id == pid) & (PaperFavorite.user_id == uid)
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(PaperFavorite(paper_id=pid, user_id=uid))
        await db.commit()
    return {"status": "favorited"}


@router.delete("/{paper_id}/favorite")
async def remove_favorite(
    paper_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a paper from the current user's favorites (idempotent)."""
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    uid = uuid.UUID(user["id"])
    from sqlalchemy import delete
    await db.execute(
        delete(PaperFavorite).where(
            (PaperFavorite.paper_id == pid) & (PaperFavorite.user_id == uid)
        )
    )
    await db.commit()
    return {"status": "unfavorited"}


@router.delete("/{paper_id}")
async def delete_paper(
    paper_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a paper and all associated data."""
    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    result = await db.execute(select(Paper).where(Paper.id == pid))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    check_owner_or_admin(paper.created_by, user)

    # Record deletion so it won't be re-fetched
    from app.models.deleted_paper import DeletedPaper
    db.add(DeletedPaper(id=uuid.uuid4(), doi=paper.doi, title=paper.title))

    await db.delete(paper)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{paper_id}/rescore")
async def rescore_paper(
    paper_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-score a single paper for all users."""
    from sqlalchemy import delete
    from app.services.ranking.scorer import score_paper_for_all_users
    from app.services.summariser import generate_summary
    from app.models.user_profile import UserProfile

    try:
        pid = uuid.UUID(paper_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID")

    result = await db.execute(select(Paper).where(Paper.id == pid))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    check_owner_or_admin(paper.created_by, user)

    # Delete existing scores
    del_result = await db.execute(delete(PaperScore).where(PaperScore.paper_id == pid))
    old_scores = del_result.rowcount
    await db.commit()

    # Get all users
    users_result = await db.execute(select(UserProfile))
    users = [
        {
            "id": str(u.id),
            "full_name": u.full_name,
            "interest_keywords": u.interest_keywords or [],
            "interest_categories": u.interest_categories or [],
            "interest_vector": u.interest_vector or {},
            "category_weights": u.category_weights or {},
            "scoring_prompt": u.scoring_prompt,
        }
        for u in users_result.scalars().all()
    ]

    if not users:
        return {"status": "no_users", "message": "No users found to score for"}

    paper_dict = {
        "id": str(paper.id),
        "title": paper.title,
        "abstract": paper.abstract or "",
        "authors": paper.authors,
        "journal": paper.journal,
        "keywords": paper.keywords or [],
    }

    # Score for all users
    scores = await score_paper_for_all_users(paper_dict, users)

    # Save scores
    for score_data in scores:
        score = PaperScore(
            id=uuid.uuid4(),
            paper_id=pid,
            user_id=uuid.UUID(score_data["user_id"]),
            relevance_score=score_data["score"],
            score_reasoning=score_data.get("reasoning"),
        )
        db.add(score)

    # Re-generate summary if any score >= 5.0
    max_score = max(s["score"] for s in scores) if scores else 0
    summary_regenerated = False
    if max_score >= 5.0:
        summary = await generate_summary(paper_dict)
        if summary:
            paper.summary = json.dumps(summary)
            paper.categories = summary.get("categories", [])[:6]
            paper.summary_generated_at = datetime.now(timezone.utc)
            summary_regenerated = True

    await db.commit()

    return {
        "status": "success",
        "old_scores_deleted": old_scores,
        "new_scores": len(scores),
        "max_score": round(max_score, 1),
        "summary_regenerated": summary_regenerated,
        "scores": [
            {"user": s["user_id"][:8], "score": round(s["score"], 1), "reasoning": s["reasoning"]}
            for s in scores
        ],
    }


@router.post("/{paper_id}/upload-pdf")
async def upload_pdf(
    paper_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a PDF for an existing paper. Extracts text and regenerates summary."""
    from app.services.pdf_processor import validate_pdf, extract_text_from_pdf
    from app.services.summariser import generate_summary

    # Get paper
    result = await db.execute(select(Paper).where(Paper.id == uuid.UUID(paper_id)))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Read and validate
    file_bytes = await file.read()

    error = validate_pdf(file_bytes, file.filename or "upload.pdf")
    if error:
        status = 413 if "too large" in error.lower() else 400
        raise HTTPException(status_code=status, detail=error)

    # Extract text
    full_text = extract_text_from_pdf(file_bytes)
    paper.full_text = full_text
    await db.commit()

    # Regenerate summary with full text in background
    async def _regenerate_summary():
        from app.database import init_db, async_session_factory
        import logging
        logger = logging.getLogger(__name__)

        try:
            if async_session_factory is None:
                init_db()
            if async_session_factory is None:
                logger.warning("Cannot regenerate summary: no database session factory")
                return
        except Exception:
            return

        async with async_session_factory() as bg_db:
            paper_dict = {
                "title": paper.title,
                "authors": paper.authors,
                "journal": paper.journal,
                "abstract": paper.abstract or "",
                "full_text": full_text,
            }
            summary = await generate_summary(paper_dict)
            if summary:
                bg_result = await bg_db.execute(select(Paper).where(Paper.id == uuid.UUID(paper_id)))
                bg_paper = bg_result.scalar_one_or_none()
                if bg_paper:
                    bg_paper.summary = json.dumps(summary)
                    bg_paper.categories = summary.get("categories", [])[:6]
                    bg_paper.summary_generated_at = datetime.now(timezone.utc)
                    await bg_db.commit()
                    logger.info(f"Regenerated summary for paper {paper_id} with full text")

    background_tasks.add_task(_regenerate_summary)

    return {
        "status": "uploaded",
        "text_length": len(full_text),
        "message": "PDF uploaded. Summary is being regenerated with full text.",
    }


class UploadNewPaperRequest(BaseModel):
    title: str | None = None
    journal: str = "Uploaded"
    doi: str | None = None


@router.post("/upload-new")
async def upload_new_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a PDF for a paper not yet in the system."""
    from app.services.pdf_processor import validate_pdf, extract_text_from_pdf

    file_bytes = await file.read()
    error = validate_pdf(file_bytes, file.filename or "upload.pdf")
    if error:
        status = 413 if "too large" in error.lower() else 400
        raise HTTPException(status_code=status, detail=error)

    full_text = extract_text_from_pdf(file_bytes)

    # Extract title from first lines of text
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    title = lines[0] if lines else file.filename or "Untitled Paper"
    if len(title) > 300:
        title = title[:300]

    paper = Paper(
        id=uuid.uuid4(),
        title=title,
        authors=[],
        journal="Uploaded",
        journal_source="upload",
        full_text=full_text,
        created_by=uuid.UUID(user["id"]),
    )
    db.add(paper)
    await db.commit()

    return {
        "status": "created",
        "paper_id": str(paper.id),
        "title": title,
        "text_length": len(full_text),
    }


class DOILookupRequest(BaseModel):
    doi: str
    paper_id: str | None = None  # If provided, attach to existing paper


@router.post("/doi-lookup")
async def doi_lookup(
    req: DOILookupRequest,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Look up a DOI via Unpaywall and auto-fetch the open access PDF."""
    from app.services.pdf_processor import fetch_pdf_from_unpaywall, extract_text_from_pdf

    pdf_bytes = await fetch_pdf_from_unpaywall(req.doi)
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="No open access PDF found for this DOI")

    full_text = extract_text_from_pdf(pdf_bytes)

    if req.paper_id:
        # Attach to existing paper
        result = await db.execute(select(Paper).where(Paper.id == uuid.UUID(req.paper_id)))
        paper = result.scalar_one_or_none()
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        paper.full_text = full_text
        if not paper.doi:
            paper.doi = req.doi
        await db.commit()
        return {"status": "attached", "paper_id": str(paper.id), "text_length": len(full_text)}
    else:
        # Create new paper
        paper = Paper(
            id=uuid.uuid4(),
            doi=req.doi,
            title=f"DOI: {req.doi}",
            authors=[],
            journal="Unknown",
            journal_source="doi_lookup",
            full_text=full_text,
            created_by=uuid.UUID(user["id"]),
        )
        db.add(paper)
        await db.commit()
        return {"status": "created", "paper_id": str(paper.id), "text_length": len(full_text)}
