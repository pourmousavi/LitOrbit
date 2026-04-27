"""RSS news ingestion job.

Fetches all enabled news sources, parses entries, embeds, scores,
deduplicates, and stores new items. Triggers lazy scrape for
high-relevance items.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from html import unescape
from time import struct_time

import feedparser
import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_item import NewsItem
from app.models.news_source import NewsSource
from app.services import news_sources_service
from app.services.news_dedup_service import assign_cluster
from app.services.relevance_service import compute_relevance_score, load_anchors
from app.services.ranking.embedder import embed_text

logger = logging.getLogger(__name__)

GLOBAL_DAILY_CAP = 25

# Strip HTML tags from RSS descriptions
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = _HTML_TAG_RE.sub("", unescape(text))
    cleaned = " ".join(cleaned.split())  # normalize whitespace
    return cleaned[:400] if cleaned else None


def _parse_pub_date(entry: dict) -> datetime:
    """Extract published date from a feedparser entry."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed: struct_time | None = entry.get(key)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
    return datetime.now(timezone.utc)


def _get_entry_url(entry: dict) -> str | None:
    """Get the best URL from a feedparser entry."""
    return entry.get("link") or entry.get("id")


def _get_entry_guid(entry: dict) -> str | None:
    """Get the GUID (unique ID) from an RSS entry."""
    return entry.get("id") or entry.get("guid")


def _get_entry_author(entry: dict) -> str | None:
    return entry.get("author") or entry.get("dc_creator")


def _get_entry_tags(entry: dict) -> list[str]:
    tags = entry.get("tags", [])
    return [t.get("term", "") for t in tags if t.get("term")]


def _get_entry_categories(entry: dict) -> list[str]:
    return [t.get("term", "") for t in entry.get("tags", []) if t.get("scheme")]


async def _fetch_feed(source: NewsSource) -> feedparser.FeedParserDict | None:
    """Fetch and parse an RSS feed."""
    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            resp = await client.get(source.feed_url)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            logger.warning(
                "Feed parse error for %s: %s", source.name, feed.bozo_exception
            )
            return None
        return feed

    except httpx.HTTPError as e:
        logger.error("Failed to fetch feed %s: %s", source.name, e)
        return None


async def _item_exists(db: AsyncSession, source_id: uuid.UUID, url: str, guid: str | None) -> bool:
    """Check if a news item already exists by URL or source+GUID."""
    # Check by URL
    result = await db.execute(
        select(NewsItem.id).where(NewsItem.url == url).limit(1)
    )
    if result.scalar_one_or_none():
        return True

    # Check by source + GUID
    if guid:
        result = await db.execute(
            select(NewsItem.id).where(
                NewsItem.source_id == source_id,
                NewsItem.guid == guid,
            ).limit(1)
        )
        if result.scalar_one_or_none():
            return True

    return False


async def _count_today_items(db: AsyncSession, source_id: uuid.UUID) -> int:
    """Count items ingested today for a source."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(NewsItem.id)).where(
            NewsItem.source_id == source_id,
            NewsItem.created_at >= today_start,
        )
    )
    return result.scalar() or 0


async def _process_batch(
    db: AsyncSession,
    source: NewsSource,
    entries: list[dict],
    run_id: "uuid.UUID | None" = None,
) -> dict:
    """Process a batch of feed entries for a single source.

    Returns summary stats.
    """
    stats = {"new": 0, "skipped_exists": 0, "skipped_cap": 0, "embedded": 0, "errors": 0}

    today_count = await _count_today_items(db, source.id)
    cap = int(source.per_source_daily_cap)
    remaining_cap = max(0, cap - today_count)

    # Sort by published date descending so we keep the most recent
    entries.sort(key=lambda e: _parse_pub_date(e), reverse=True)

    # Items to insert (before cap enforcement)
    items_to_insert: list[NewsItem] = []

    for entry in entries:
        url = _get_entry_url(entry)
        if not url:
            continue

        guid = _get_entry_guid(entry)
        if await _item_exists(db, source.id, url, guid):
            stats["skipped_exists"] += 1
            continue

        title = entry.get("title", "").strip()
        if not title:
            continue

        excerpt = _clean_html(entry.get("summary") or entry.get("description"))
        published_at = _parse_pub_date(entry)

        item = NewsItem(
            source_id=source.id,
            url=url,
            guid=guid,
            title=title,
            excerpt=excerpt,
            author=_get_entry_author(entry),
            published_at=published_at,
            tags=_get_entry_tags(entry),
            categories=_get_entry_categories(entry),
            ingest_run_id=run_id,
        )
        items_to_insert.append(item)

    # Embed and score
    for item in items_to_insert:
        try:
            text_to_embed = item.title
            if item.excerpt:
                text_to_embed = f"{item.title}. {item.excerpt}"

            emb = await embed_text(text_to_embed)
            if emb:
                item.embedding = emb
                item.relevance_score = compute_relevance_score(emb)
                stats["embedded"] += 1
        except Exception as e:
            logger.warning("Failed to embed news item '%s': %s", item.title[:50], e)
            stats["errors"] += 1

    # Sort by relevance score descending for cap enforcement
    items_to_insert.sort(
        key=lambda i: float(i.relevance_score or 0), reverse=True
    )

    inserted_count = 0
    for item in items_to_insert:
        if inserted_count >= remaining_cap:
            # Still insert but mark as non-primary (hidden from feed)
            item.is_cluster_primary = False
            stats["skipped_cap"] += 1

        db.add(item)
        await db.flush()  # Get the ID assigned

        # Dedup (assigns cluster)
        authority = float(source.authority_weight)
        await assign_cluster(db, item, authority)

        inserted_count += 1
        stats["new"] += 1

    await db.commit()

    # Score and summarise all primary items
    scored = 0
    for item in items_to_insert:
        if item.is_cluster_primary:
            try:
                from app.services.news_scorer import score_and_summarise_news_item
                await score_and_summarise_news_item(db, item, source.name)
                scored += 1
            except Exception as e:
                logger.warning("Score/summarise failed for '%s': %s", item.title[:50], e)
    stats["scored"] = scored

    return stats


async def _score_unscored_items(db: AsyncSession, source: NewsSource) -> int:
    """Score and summarise existing news items that haven't been LLM-scored yet."""
    from app.services.news_scorer import score_and_summarise_news_item

    result = await db.execute(
        select(NewsItem).where(
            NewsItem.source_id == source.id,
            NewsItem.is_cluster_primary == True,
            NewsItem.llm_score.is_(None),
            NewsItem.embedding.isnot(None),
        ).order_by(NewsItem.created_at.desc()).limit(25)
    )
    unscored = result.scalars().all()
    scored = 0
    for item in unscored:
        try:
            await score_and_summarise_news_item(db, item, source.name)
            scored += 1
        except Exception as e:
            logger.warning("Score/summarise failed for '%s': %s", item.title[:50], e)
    return scored


async def ingest_source(db: AsyncSession, source: NewsSource, run_id: "uuid.UUID | None" = None) -> dict:
    """Ingest news from a single source. Returns stats dict."""
    feed = await _fetch_feed(source)
    if not feed:
        await news_sources_service.mark_fetched(db, source.id, status="error", error="Feed fetch/parse failed")
        return {"source": source.name, "error": "Feed fetch/parse failed"}

    stats = await _process_batch(db, source, feed.entries, run_id=run_id)

    # Also score any existing items that haven't been LLM-scored yet
    backfill_scored = await _score_unscored_items(db, source)
    stats["scored"] = stats.get("scored", 0) + backfill_scored

    await news_sources_service.mark_fetched(db, source.id, status="ok")

    logger.info(
        "Ingested %s: %d new, %d skipped (exists), %d skipped (cap), %d embedded, %d scored, %d errors",
        source.name, stats["new"], stats["skipped_exists"],
        stats["skipped_cap"], stats["embedded"], stats.get("scored", 0), stats["errors"],
    )
    return {"source": source.name, **stats}


async def ingest_all_enabled_sources(db: AsyncSession) -> list[dict]:
    """Ingest news from all enabled sources.

    Loads anchors once, then processes each source.
    Creates a NewsIngestRun to track the batch.
    Returns list of per-source stats.
    """
    from app.models.news_ingest_run import NewsIngestRun
    from datetime import datetime, timezone

    await load_anchors(db)
    sources = await news_sources_service.get_enabled_sources(db)

    if not sources:
        logger.info("No enabled news sources found")
        return []

    # Create a run record
    run = NewsIngestRun(
        started_at=datetime.now(timezone.utc),
        status="running",
        sources_total=len(sources),
    )
    db.add(run)
    await db.flush()

    results = []
    succeeded = 0
    failed = 0
    totals = {"new": 0, "skipped": 0, "embedded": 0, "scored": 0, "errors": 0}

    for source in sources:
        try:
            stats = await ingest_source(db, source, run_id=run.id)
            results.append(stats)
            if stats.get("error"):
                failed += 1
            else:
                succeeded += 1
                totals["new"] += stats.get("new", 0)
                totals["skipped"] += stats.get("skipped_exists", 0) + stats.get("skipped_cap", 0)
                totals["embedded"] += stats.get("embedded", 0)
                totals["scored"] += stats.get("scored", 0)
                totals["errors"] += stats.get("errors", 0)
        except Exception as e:
            logger.exception("News ingest failed for %s: %s", source.name, e)
            await news_sources_service.mark_fetched(
                db, source.id, status="error", error=str(e)
            )
            results.append({"source": source.name, "error": str(e)})
            failed += 1

    # Update run record
    run.completed_at = datetime.now(timezone.utc)
    run.status = "success" if failed == 0 else ("partial" if succeeded > 0 else "failed")
    run.sources_succeeded = succeeded
    run.sources_failed = failed
    run.items_new = totals["new"]
    run.items_skipped = totals["skipped"]
    run.items_embedded = totals["embedded"]
    run.items_scored = totals["scored"]
    run.items_errors = totals["errors"]
    run.run_log = results
    if failed > 0 and succeeded == 0:
        run.error_message = f"All {failed} sources failed"
    await db.commit()

    return results
