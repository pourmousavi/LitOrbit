import logging
import re
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.reference_paper import ReferencePaper
from app.models.user_profile import UserProfile
from app.services.ranking.embedder import (
    embed_text,
    prepare_paper_text,
    compute_centroid,
    EmbeddingQuotaExhausted,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reference-papers", tags=["reference-papers"])

MAX_REFERENCE_PAPERS = 10


async def _recompute_profile_embedding(db: AsyncSession, user_id: uuid.UUID):
    """Recompute user's profile embedding from their reference papers."""
    result = await db.execute(
        select(ReferencePaper).where(
            ReferencePaper.user_id == user_id,
            ReferencePaper.embedding.isnot(None),
        )
    )
    papers = result.scalars().all()

    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        return

    if not papers:
        profile.interest_vector = {}
    else:
        vectors = [p.embedding for p in papers]
        profile.interest_vector = compute_centroid(vectors)

    await db.commit()


async def _check_limit(db: AsyncSession, user_id: uuid.UUID):
    """Raise 400 if user has reached the reference paper limit."""
    result = await db.execute(
        select(func.count()).where(ReferencePaper.user_id == user_id)
    )
    count = result.scalar() or 0
    if count >= MAX_REFERENCE_PAPERS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_REFERENCE_PAPERS} reference papers allowed.",
        )


def _extract_abstract_from_text(full_text: str) -> str | None:
    """Heuristically extract the abstract from PDF text."""
    # Look for "Abstract" header
    match = re.search(
        r'\babstract\b[:\s]*\n?(.*?)(?:\n\s*\n|\b(?:introduction|keywords|1\.\s)\b)',
        full_text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        abstract = match.group(1).strip()
        if len(abstract) > 50:  # sanity check
            return abstract[:3000]

    # Fallback: first 2000 chars
    return full_text[:2000] if full_text else None


@router.get("")
async def list_reference_papers(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List the current user's reference papers."""
    result = await db.execute(
        select(ReferencePaper)
        .where(ReferencePaper.user_id == uuid.UUID(user["id"]))
        .order_by(ReferencePaper.created_at.desc())
    )
    papers = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "abstract_preview": p.abstract[:200] if p.abstract else None,
            "doi": p.doi,
            "source": p.source,
            "has_embedding": p.embedding is not None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in papers
    ]


@router.post("/upload-pdf")
async def upload_reference_pdf(
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a PDF as a reference paper."""
    from app.services.pdf_processor import validate_pdf, extract_text_from_pdf

    user_id = uuid.UUID(user["id"])
    await _check_limit(db, user_id)

    file_bytes = await file.read()
    error = validate_pdf(file_bytes, file.filename or "upload.pdf")
    if error:
        status = 413 if "too large" in error.lower() else 400
        raise HTTPException(status_code=status, detail=error)

    full_text = extract_text_from_pdf(file_bytes)

    # Extract title from first lines
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    title = lines[0] if lines else file.filename or "Untitled"
    if len(title) > 300:
        title = title[:300]

    abstract = _extract_abstract_from_text(full_text)

    # Embed
    text_to_embed = prepare_paper_text(title, abstract)
    embedding = None
    warning = None
    try:
        embedding = await embed_text(text_to_embed)
    except Exception as e:
        logger.warning(f"Failed to embed reference paper: {e}")
        warning = "Embedding failed — will be processed on next pipeline run."

    paper = ReferencePaper(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        abstract=abstract,
        source="pdf_upload",
        embedding=embedding,
    )
    db.add(paper)
    await db.commit()

    await _recompute_profile_embedding(db, user_id)

    result = {
        "status": "created",
        "id": str(paper.id),
        "title": title,
        "has_embedding": embedding is not None,
    }
    if warning:
        result["warning"] = warning
    return result


class DOILookupRequest(BaseModel):
    doi: str


@router.post("/doi-lookup")
async def add_by_doi(
    req: DOILookupRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a reference paper by DOI lookup via CrossRef."""
    user_id = uuid.UUID(user["id"])
    await _check_limit(db, user_id)

    doi = req.doi.strip()

    # Fetch metadata from CrossRef
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": "LitOrbit/1.0 (mailto:litorbit@adelaide.edu.au)"},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=404, detail="DOI not found on CrossRef.")

    data = resp.json().get("message", {})
    title_parts = data.get("title", [])
    title = title_parts[0] if title_parts else doi
    abstract = data.get("abstract", "")
    # CrossRef abstracts can have JATS XML tags — strip them
    if abstract:
        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

    # Embed
    text_to_embed = prepare_paper_text(title, abstract or None)
    embedding = None
    warning = None
    try:
        embedding = await embed_text(text_to_embed)
    except Exception as e:
        logger.warning(f"Failed to embed reference paper: {e}")
        warning = "Embedding failed — will be processed on next pipeline run."

    paper = ReferencePaper(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        abstract=abstract or None,
        doi=doi,
        source="doi_lookup",
        embedding=embedding,
    )
    db.add(paper)
    await db.commit()

    await _recompute_profile_embedding(db, user_id)

    result = {
        "status": "created",
        "id": str(paper.id),
        "title": title,
        "has_embedding": embedding is not None,
    }
    if warning:
        result["warning"] = warning
    return result


class ManualEntryRequest(BaseModel):
    title: str
    abstract: str | None = None


@router.post("/manual")
async def add_manual(
    req: ManualEntryRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a reference paper manually with title and optional abstract."""
    user_id = uuid.UUID(user["id"])
    await _check_limit(db, user_id)

    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required.")

    abstract = req.abstract.strip() if req.abstract else None

    text_to_embed = prepare_paper_text(title, abstract)
    embedding = None
    warning = None
    try:
        embedding = await embed_text(text_to_embed)
    except Exception as e:
        logger.warning(f"Failed to embed reference paper: {e}")
        warning = "Embedding failed — will be processed on next pipeline run."

    paper = ReferencePaper(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        abstract=abstract,
        source="manual",
        embedding=embedding,
    )
    db.add(paper)
    await db.commit()

    await _recompute_profile_embedding(db, user_id)

    result = {
        "status": "created",
        "id": str(paper.id),
        "title": title,
        "has_embedding": embedding is not None,
    }
    if warning:
        result["warning"] = warning
    return result


@router.delete("/{paper_id}")
async def delete_reference_paper(
    paper_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a reference paper and recompute profile embedding."""
    user_id = uuid.UUID(user["id"])

    result = await db.execute(
        select(ReferencePaper).where(
            ReferencePaper.id == uuid.UUID(paper_id),
            ReferencePaper.user_id == user_id,
        )
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Reference paper not found.")

    await db.delete(paper)
    await db.commit()

    await _recompute_profile_embedding(db, user_id)

    return {"status": "deleted"}
