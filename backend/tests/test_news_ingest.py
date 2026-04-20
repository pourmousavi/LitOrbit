"""Tests for news ingestion pipeline.

Covers:
- RSS feed parsing and entry extraction
- Item deduplication (URL and GUID)
- Per-source daily cap enforcement
- HTML cleaning in excerpts
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio

from app.models.news_source import NewsSource
from app.models.news_item import NewsItem


# --- Helper data ---

SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Energy News</title>
    <link>https://test.example.com</link>
    <item>
      <title>New BESS project announced in SA</title>
      <link>https://test.example.com/bess-sa</link>
      <guid>guid-001</guid>
      <description>&lt;p&gt;A major &lt;strong&gt;battery&lt;/strong&gt; project has been approved.&lt;/p&gt;</description>
      <pubDate>Mon, 20 Apr 2026 10:00:00 +0000</pubDate>
      <author>Jane Reporter</author>
      <category>Battery</category>
      <category>South Australia</category>
    </item>
    <item>
      <title>Solar farm expansion in QLD</title>
      <link>https://test.example.com/solar-qld</link>
      <guid>guid-002</guid>
      <description>Queensland's largest solar farm gets planning approval</description>
      <pubDate>Sun, 19 Apr 2026 08:30:00 +0000</pubDate>
    </item>
    <item>
      <title>Wind power record in VIC</title>
      <link>https://test.example.com/wind-vic</link>
      <guid>guid-003</guid>
      <description>Victoria sets new wind generation record overnight</description>
      <pubDate>Sat, 18 Apr 2026 22:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


# --- Tests for HTML cleaning ---

def test_clean_html_strips_tags():
    from app.services.news_ingest import _clean_html

    assert _clean_html("<p>Hello <strong>world</strong></p>") == "Hello world"
    assert _clean_html("&amp; &lt;b&gt;test&lt;/b&gt;") == "& test"
    assert _clean_html(None) is None
    assert _clean_html("") is None


def test_clean_html_truncates_to_400():
    from app.services.news_ingest import _clean_html

    long_text = "x" * 500
    result = _clean_html(long_text)
    assert len(result) == 400


# --- Tests for date parsing ---

def test_parse_pub_date_from_entry():
    import feedparser
    from app.services.news_ingest import _parse_pub_date

    feed = feedparser.parse(SAMPLE_RSS_XML)
    entry = feed.entries[0]
    dt = _parse_pub_date(entry)
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 20


def test_parse_pub_date_fallback():
    from app.services.news_ingest import _parse_pub_date

    # Entry with no date info should return current time
    dt = _parse_pub_date({})
    assert dt.year >= 2026


# --- Tests for entry extraction ---

def test_get_entry_url():
    from app.services.news_ingest import _get_entry_url

    assert _get_entry_url({"link": "https://a.com"}) == "https://a.com"
    assert _get_entry_url({"id": "https://b.com"}) == "https://b.com"
    assert _get_entry_url({}) is None


def test_get_entry_tags():
    from app.services.news_ingest import _get_entry_tags

    tags = _get_entry_tags({"tags": [{"term": "Battery"}, {"term": "Solar"}]})
    assert tags == ["Battery", "Solar"]
    assert _get_entry_tags({}) == []


# --- Tests for feedparser integration ---

def test_feedparser_parses_sample_rss():
    import feedparser

    feed = feedparser.parse(SAMPLE_RSS_XML)
    assert len(feed.entries) == 3
    assert feed.entries[0].title == "New BESS project announced in SA"
    assert feed.entries[0].link == "https://test.example.com/bess-sa"


# --- Tests for item existence check ---

@pytest.mark.asyncio
async def test_item_exists_by_url(db_session):
    source = NewsSource(
        name="Test Source",
        feed_url="https://test.com/feed/",
        website_url="https://test.com/",
    )
    db_session.add(source)
    await db_session.flush()

    item = NewsItem(
        source_id=source.id,
        url="https://test.com/article-1",
        title="Test Article",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(item)
    await db_session.commit()

    from app.services.news_ingest import _item_exists

    assert await _item_exists(db_session, source.id, "https://test.com/article-1", None) is True
    assert await _item_exists(db_session, source.id, "https://test.com/article-2", None) is False


@pytest.mark.asyncio
async def test_item_exists_by_guid(db_session):
    source = NewsSource(
        name="Test Source GUID",
        feed_url="https://test.com/feed/",
        website_url="https://test.com/",
    )
    db_session.add(source)
    await db_session.flush()

    item = NewsItem(
        source_id=source.id,
        url="https://test.com/article-guid",
        guid="unique-guid-123",
        title="Test Article GUID",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(item)
    await db_session.commit()

    from app.services.news_ingest import _item_exists

    assert await _item_exists(db_session, source.id, "https://other.com", "unique-guid-123") is True
    assert await _item_exists(db_session, source.id, "https://other.com", "different-guid") is False


# --- Tests for daily cap counting ---

@pytest.mark.asyncio
async def test_count_today_items(db_session):
    source = NewsSource(
        name="Test Count Source",
        feed_url="https://test.com/feed/",
        website_url="https://test.com/",
    )
    db_session.add(source)
    await db_session.flush()

    # Add 3 items today
    for i in range(3):
        item = NewsItem(
            source_id=source.id,
            url=f"https://test.com/today-{i}",
            title=f"Today Article {i}",
            published_at=datetime.now(timezone.utc),
        )
        db_session.add(item)
    await db_session.commit()

    from app.services.news_ingest import _count_today_items

    count = await _count_today_items(db_session, source.id)
    assert count == 3
