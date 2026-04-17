import logging
import re
from typing import Any

from Levenshtein import ratio as levenshtein_ratio

logger = logging.getLogger(__name__)

# ---- Junk / non-article filter ----

JUNK_TITLE_PATTERNS = [
    r"^table of contents$",
    r"^front cover$",
    r"^back cover$",
    r"^masthead$",
    r"^blank page$",
    r"^(ieee )?editorial board$",
    r"^call for papers",
    r"^corrections? to ",
    r"^errata ",
    r"^reviewers? list$",
    r"^list of reviewers$",
    r"^advertiser.* index$",
    r"^(conference )?calendar$",
    r"^introduction to the special",
]

_JUNK_RE = re.compile("|".join(JUNK_TITLE_PATTERNS), re.IGNORECASE)

SHORT_TITLE_MAX_LEN = 30


def filter_junk_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove non-article entries (TOCs, covers, ads, etc.).

    Two layers:
    1. Regex blocklist for known junk titles.
    2. Short title (<=30 chars) with no abstract — almost certainly not a real article.
    """
    kept = []
    for paper in papers:
        title = (paper.get("title") or "").strip()
        abstract = (paper.get("abstract") or "").strip()

        if _JUNK_RE.search(title):
            logger.info(f"Filtered junk paper: '{title}'")
            continue

        if len(title) <= SHORT_TITLE_MAX_LEN and not abstract:
            logger.info(f"Filtered short-title junk (no abstract): '{title}'")
            continue

        kept.append(paper)

    removed = len(papers) - len(kept)
    if removed:
        logger.info(f"Junk filter removed {removed} non-article entries")
    return kept


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
