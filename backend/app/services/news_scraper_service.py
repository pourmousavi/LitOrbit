"""Lazy full-text scraper for news articles.

Fires when relevance_score >= threshold, on Send-to-ScholarLib,
or when a user opens the detail view and full text is missing.
Uses trafilatura for content extraction.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_item import NewsItem
from app.services.ranking.embedder import embed_text
from app.services.relevance_service import compute_relevance_score

logger = logging.getLogger(__name__)

# Rate limit: 1 request per 3s per source domain
_domain_last_request: dict[str, float] = {}
_POLITENESS_DELAY = 3.0

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0"
ACCEPT_LANGUAGE = "en-US,en;q=0.9"


def _get_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc


async def _wait_for_politeness(domain: str) -> None:
    import time
    last = _domain_last_request.get(domain, 0)
    elapsed = time.monotonic() - last
    if elapsed < _POLITENESS_DELAY:
        await asyncio.sleep(_POLITENESS_DELAY - elapsed)
    _domain_last_request[domain] = time.monotonic()


async def scrape_full_text(db: AsyncSession, item_id) -> bool:
    """Scrape and store full text for a news item.

    Returns True if full text was successfully extracted.
    Also re-embeds and re-scores using the full text.
    """
    item = await db.get(NewsItem, item_id)
    if not item:
        logger.warning("News item %s not found for scraping", item_id)
        return False

    if item.full_text:
        return True  # Already scraped

    domain = _get_domain(item.url)
    await _wait_for_politeness(domain)

    # Honor the source's use_proxy flag for the article fetch.
    from app.models.news_source import NewsSource
    source = await db.get(NewsSource, item.source_id)
    use_proxy = bool(source and source.use_proxy)

    try:
        if use_proxy:
            from app.services.news_fetch_proxy import proxy_get
            resp = await proxy_get(item.url)
            if resp.status_code in (403, 429):
                logger.warning("Scrape blocked via proxy (%d) for %s", resp.status_code, item.url)
                return False
            resp.raise_for_status()
        else:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANGUAGE},
            ) as client:
                resp = await client.get(item.url)
                if resp.status_code in (403, 429):
                    logger.warning("Scrape blocked (%d) for %s", resp.status_code, item.url)
                    return False
                resp.raise_for_status()

        try:
            import trafilatura
            text = trafilatura.extract(
                resp.text,
                include_links=False,
                include_images=False,
                favor_recall=False,
                output_format="txt",
            )
        except ImportError:
            logger.warning("trafilatura not installed, skipping full-text extraction")
            return False

        if not text or len(text) < 300:
            logger.info("Scrape of %s yielded too little text (%d chars)", item.url, len(text) if text else 0)
            return False

        item.full_text = text
        item.full_text_scraped_at = datetime.now(timezone.utc)

        # Re-embed using full text (often materially changes score)
        emb = await embed_text(text[:8000])
        if emb:
            item.embedding = emb
            score = compute_relevance_score(emb)
            item.relevance_score = score
            logger.info(
                "Re-embedded '%s' with full text, new score=%.3f",
                item.title[:50], score,
            )

        await db.commit()
        return True

    except httpx.HTTPError as e:
        logger.warning("Failed to scrape %s: %s", item.url, e)
        return False
    except Exception as e:
        logger.exception("Unexpected error scraping %s: %s", item.url, e)
        return False
