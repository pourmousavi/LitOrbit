import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.elsevier.com/content/search/scopus"


async def fetch_scopus_papers(
    issn: str,
    lookback_days: int = 7,
) -> list[dict[str, Any]]:
    """Fetch recent papers from Scopus by ISSN."""
    settings = get_settings()
    if not settings.scopus_api_key:
        logger.warning("SCOPUS_API_KEY not set, skipping Scopus discovery")
        return []

    today = datetime.now(timezone.utc)

    # Strip "ISSN:" prefix if present
    clean_issn = issn.replace("ISSN:", "").strip()

    headers = {
        "X-ELS-APIKey": settings.scopus_api_key,
        "Accept": "application/json",
    }

    params = {
        "query": f"ISSN({clean_issn}) AND PUBYEAR > {today.year - 1}",
        "sort": "coverDate",
        "count": 25,
        "field": "dc:title,dc:creator,prism:doi,prism:publicationName,prism:coverDate,dc:description,prism:url,authkeywords",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            start = datetime.now(timezone.utc)
            resp = await client.get(BASE_URL, headers=headers, params=params)
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            logger.info(f"Scopus API call for ISSN {clean_issn}: {resp.status_code} in {duration:.2f}s")

            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Scopus API error for ISSN {clean_issn}: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Scopus API request error for ISSN {clean_issn}: {e}")
            return []

    results = data.get("search-results", {}).get("entry", [])
    if not results or (len(results) == 1 and "error" in results[0]):
        logger.info(f"Scopus: No results for ISSN {clean_issn}")
        return []

    papers = []
    for entry in results:
        if "error" in entry:
            continue
        # Extract author keywords
        keywords = []
        authkw = entry.get("authkeywords")
        if authkw and isinstance(authkw, str):
            keywords = [k.strip() for k in authkw.split("|") if k.strip()]

        papers.append({
            "doi": entry.get("prism:doi"),
            "title": entry.get("dc:title", ""),
            "authors": [entry.get("dc:creator", "")] if entry.get("dc:creator") else [],
            "abstract": entry.get("dc:description", ""),
            "journal": entry.get("prism:publicationName", ""),
            "journal_source": "scopus",
            "published_date": entry.get("prism:coverDate"),
            "online_date": entry.get("prism:coverDate"),
            "early_access": False,
            "url": entry.get("prism:url", ""),
            "keywords": keywords,
        })

    logger.info(f"Scopus: Found {len(papers)} papers for ISSN {clean_issn}")
    return papers


async def fetch_all_scopus_journals(journals: list[dict]) -> list[dict[str, Any]]:
    """Fetch papers from all active Scopus journals with rate limiting."""
    all_papers = []
    for journal in journals:
        issn = journal["source_identifier"]
        papers = await fetch_scopus_papers(issn)
        all_papers.extend(papers)
        await asyncio.sleep(0.2)
    return all_papers
