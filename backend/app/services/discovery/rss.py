import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser

logger = logging.getLogger(__name__)


async def fetch_rss_papers(
    feed_url: str,
    lookback_days: int = 7,
) -> list[dict[str, Any]]:
    """Parse an RSS feed and return papers published within the lookback window."""
    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        logger.error(f"RSS parse error for {feed_url}: {e}")
        return []

    if feed.bozo and not feed.entries:
        logger.error(f"RSS feed error for {feed_url}: {feed.bozo_exception}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    journal_name = feed.feed.get("title", "Unknown Journal")

    papers = []
    for entry in feed.entries:
        pub_date = _parse_entry_date(entry)
        if pub_date and pub_date < cutoff:
            continue

        # Extract DOI from link if present
        doi = None
        link = entry.get("link", "")
        if "doi.org/" in link:
            doi = link.split("doi.org/")[-1]

        authors = []
        if hasattr(entry, "authors"):
            authors = [a.get("name", "") for a in entry.authors if a.get("name")]
        elif hasattr(entry, "author"):
            authors = [entry.author]

        papers.append({
            "doi": doi,
            "title": entry.get("title", ""),
            "authors": authors,
            "abstract": entry.get("summary", ""),
            "journal": journal_name,
            "journal_source": "rss",
            "published_date": pub_date.strftime("%Y-%m-%d") if pub_date else None,
            "early_access": False,
            "url": link,
        })

    logger.info(f"RSS: Found {len(papers)} papers from {journal_name}")
    return papers


def _parse_entry_date(entry) -> datetime | None:
    """Parse the published date from an RSS entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return None


async def fetch_all_rss_journals(journals: list[dict]) -> list[dict[str, Any]]:
    """Fetch papers from all active RSS journal feeds."""
    all_papers = []
    for journal in journals:
        url = journal["source_identifier"]
        papers = await fetch_rss_papers(url)
        all_papers.extend(papers)
    return all_papers
