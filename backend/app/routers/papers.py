import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
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
                    bg_paper.categories = summary.get("categories", [])
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
        )
        db.add(paper)
        await db.commit()
        return {"status": "created", "paper_id": str(paper.id), "text_length": len(full_text)}
