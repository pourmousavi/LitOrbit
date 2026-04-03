import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

BASE_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"


async def fetch_ieee_papers(
    publication_number: str,
    lookback_days: int = 7,
) -> list[dict[str, Any]]:
    """Fetch recent papers from an IEEE Xplore journal by publication number."""
    settings = get_settings()
    if not settings.ieee_api_key:
        logger.warning("IEEE_API_KEY not set, skipping IEEE discovery")
        return []

    today = datetime.now(timezone.utc)
    start_date = (today - timedelta(days=lookback_days)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    params = {
        "apikey": settings.ieee_api_key,
        "publication_number": publication_number,
        "sort_field": "publication_date",
        "sort_order": "desc",
        "start_record": 1,
        "max_records": 25,
        "start_date": start_date,
        "end_date": end_date,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            start = datetime.now(timezone.utc)
            resp = await client.get(BASE_URL, params=params)
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            logger.info(f"IEEE API call for pub {publication_number}: {resp.status_code} in {duration:.2f}s")

            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"IEEE API error for pub {publication_number}: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"IEEE API request error for pub {publication_number}: {e}")
            return []

    articles = data.get("articles", [])
    papers = []
    for article in articles:
        authors_list = []
        if "authors" in article and "authors" in article["authors"]:
            raw = article["authors"]["authors"]
            if isinstance(raw, dict):
                raw = [raw]
            authors_list = [a.get("full_name", "") for a in raw if a.get("full_name")]

        # Extract keywords from index_terms
        keywords = []
        index_terms = article.get("index_terms", {})
        for term_group in index_terms.values():
            if isinstance(term_group, dict) and "terms" in term_group:
                keywords.extend(term_group["terms"])

        papers.append({
            "doi": article.get("doi"),
            "title": article.get("title", ""),
            "authors": authors_list,
            "abstract": article.get("abstract", ""),
            "journal": article.get("publication_title", ""),
            "journal_source": "ieee",
            "published_date": _parse_ieee_date(article.get("publication_date")),
            "online_date": _parse_ieee_date(article.get("online_date")),
            "early_access": article.get("is_early_access", False),
            "url": article.get("html_url") or article.get("pdf_url", ""),
            "keywords": keywords,
        })

    logger.info(f"IEEE: Found {len(papers)} papers for pub {publication_number}")
    return papers


def _parse_ieee_date(date_str: str | None) -> str | None:
    """Parse IEEE date formats like '2 April 2024' or '2024'."""
    if not date_str:
        return None
    for fmt in ("%d %B %Y", "%B %Y", "%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


async def fetch_all_ieee_journals(journals: list[dict]) -> list[dict[str, Any]]:
    """Fetch papers from all active IEEE journals with rate limiting."""
    all_papers = []
    for journal in journals:
        pub_number = journal["source_identifier"]
        papers = await fetch_ieee_papers(pub_number)
        all_papers.extend(papers)
        await asyncio.sleep(0.2)  # Rate limit: stay under 10 calls/second
    return all_papers
