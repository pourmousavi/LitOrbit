import logging
from typing import Any

from Levenshtein import ratio as levenshtein_ratio

logger = logging.getLogger(__name__)


def deduplicate_papers(
    papers: list[dict[str, Any]],
    existing_dois: set[str] | None = None,
    existing_titles: set[str] | None = None,
    title_similarity_threshold: float = 0.95,
) -> list[dict[str, Any]]:
    """Deduplicate papers by DOI and title similarity.

    Args:
        papers: Raw paper dicts from all sources.
        existing_dois: DOIs already in the database (to skip).
        existing_titles: Normalised titles already in the database (to skip no-DOI duplicates).
        title_similarity_threshold: Levenshtein ratio threshold for title matching.

    Returns:
        Deduplicated list of papers.
    """
    if existing_dois is None:
        existing_dois = set()
    if existing_titles is None:
        existing_titles = set()

    seen_dois: dict[str, dict] = {}
    no_doi_papers: list[dict[str, Any]] = []

    for paper in papers:
        doi = paper.get("doi")

        # Skip papers already in DB
        if doi and doi in existing_dois:
            continue

        if doi:
            if doi in seen_dois:
                # Merge: keep the entry with more metadata
                _merge_paper(seen_dois[doi], paper)
            else:
                seen_dois[doi] = paper
        else:
            no_doi_papers.append(paper)

    # Deduplicate no-DOI papers by title similarity
    unique_no_doi: list[dict[str, Any]] = []
    for paper in no_doi_papers:
        title = paper.get("title", "").lower().strip()
        is_dup = False

        # Check against titles already in the database
        for db_title in existing_titles:
            if levenshtein_ratio(title, db_title) > title_similarity_threshold:
                is_dup = True
                break

        # Check against DOI papers in this batch
        if not is_dup:
            for existing in seen_dois.values():
                existing_title = existing.get("title", "").lower().strip()
                if levenshtein_ratio(title, existing_title) > title_similarity_threshold:
                    _merge_paper(existing, paper)
                    is_dup = True
                    break

        if not is_dup:
            # Check against other no-DOI papers in this batch
            for existing in unique_no_doi:
                existing_title = existing.get("title", "").lower().strip()
                if levenshtein_ratio(title, existing_title) > title_similarity_threshold:
                    _merge_paper(existing, paper)
                    is_dup = True
                    break

        if not is_dup:
            unique_no_doi.append(paper)

    result = list(seen_dois.values()) + unique_no_doi
    removed = len(papers) - len(result)
    if removed > 0:
        logger.info(f"Deduplication removed {removed} duplicate papers ({len(papers)} → {len(result)})")
    return result


def _merge_paper(target: dict, source: dict) -> None:
    """Merge source paper metadata into target, preferring non-empty values."""
    for key in ("abstract", "url", "doi", "published_date"):
        if not target.get(key) and source.get(key):
            target[key] = source[key]
    # Merge authors if target has fewer
    if len(source.get("authors", [])) > len(target.get("authors", [])):
        target["authors"] = source["authors"]
