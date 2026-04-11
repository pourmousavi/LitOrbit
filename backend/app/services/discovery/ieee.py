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

    PAGE_SIZE = 25  # IEEE API max per request
    MAX_PAGES = 8   # Safety cap: 200 papers max per journal per run

    async with httpx.AsyncClient(timeout=30.0) as client:
        all_articles: list[dict] = []
        start_record = 1

        while True:
            params = {
                "apikey": settings.ieee_api_key,
                "publication_number": publication_number,
                "sort_field": "publication_date",
                "sort_order": "desc",
                "start_record": start_record,
                "max_records": PAGE_SIZE,
                "start_date": start_date,
                "end_date": end_date,
            }

            try:
                start = datetime.now(timezone.utc)
                resp = await client.get(BASE_URL, params=params)
                duration = (datetime.now(timezone.utc) - start).total_seconds()
                logger.info(f"IEEE API call for pub {publication_number} (start={start_record}): {resp.status_code} in {duration:.2f}s")

                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 429:
                    logger.warning(
                        f"IEEE API rate limit hit (429) for pub {publication_number}. "
                        "Per-second throttle exceeded; backing off this run."
                    )
                elif status == 403:
                    logger.error(
                        f"IEEE API quota/permission error (403) for pub {publication_number}. "
                        "Likely daily 400-call quota exhausted or key inactive."
                    )
                else:
                    logger.error(f"IEEE API error for pub {publication_number}: {status}")
                break
            except httpx.RequestError as e:
                logger.error(f"IEEE API request error for pub {publication_number}: {e}")
                break

            articles = data.get("articles", [])
            all_articles.extend(articles)

            total_records = data.get("total_records", 0)
            fetched_so_far = start_record - 1 + len(articles)
            page_num = (start_record - 1) // PAGE_SIZE + 1

            if fetched_so_far >= total_records or len(articles) < PAGE_SIZE or page_num >= MAX_PAGES:
                break

            start_record += PAGE_SIZE
            await asyncio.sleep(0.3)  # brief pause between pages

    papers = []
    for article in all_articles:
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
    """Parse IEEE date formats. IEEE returns a variety of shapes:
    '2 April 2024', '2 Apr 2024', 'April 2024', 'Apr 2024', '2024',
    '2024-04-08', '04/08/2024'. Range strings like '2-6 April 2024'
    are reduced to their first date.
    """
    if not date_str:
        return None
    s = date_str.strip()
    # Reduce ranges like "2-6 April 2024" or "April-June 2024" to the first chunk.
    # Only collapse a numeric day range (e.g. "2-6 April 2024" -> "2 April 2024"),
    # not a month range, which we just take the head of.
    if "-" in s and not s[:4].isdigit():
        head, _, tail = s.partition("-")
        # If head is a number (day range), use head + remainder after the second token
        if head.strip().isdigit():
            rest = tail.split(" ", 1)
            s = f"{head.strip()} {rest[1]}" if len(rest) > 1 else tail.strip()
        else:
            s = head.strip() + " " + s.split(" ", 1)[1] if " " in s else head.strip()
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %Y", "%b %Y", "%m/%d/%Y", "%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.warning(f"IEEE: could not parse date string {date_str!r}")
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
