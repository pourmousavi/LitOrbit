import uuid
import pytest
import pytest_asyncio

from sqlalchemy import select, func

from app.services.discovery.deduplicator import deduplicate_papers
from app.services.discovery.rss import fetch_rss_papers
from app.models.paper import Paper
from app.models.journal_config import JournalConfig
from app.pipeline.runner import run_discovery_pipeline, save_papers


def _make_paper(doi: str | None, title: str, source: str = "ieee") -> dict:
    return {
        "doi": doi,
        "title": title,
        "authors": ["Author A"],
        "abstract": "Test abstract",
        "journal": "Test Journal",
        "journal_source": source,
        "published_date": "2024-01-01",
        "early_access": False,
        "url": "https://example.com",
    }


class TestDeduplicator:
    def test_deduplicator_removes_doi_duplicates(self):
        """Feed papers with duplicate DOIs, assert dedup removes them."""
        papers = [
            _make_paper("10.1000/a", "Paper A"),
            _make_paper("10.1000/b", "Paper B"),
            _make_paper("10.1000/a", "Paper A (duplicate)"),  # duplicate
            _make_paper("10.1000/c", "Paper C"),
            _make_paper("10.1000/b", "Paper B from Scopus", "scopus"),  # duplicate
            _make_paper("10.1000/d", "Paper D"),
            _make_paper("10.1000/e", "Paper E"),
            _make_paper("10.1000/f", "Paper F"),
            _make_paper("10.1000/g", "Paper G"),
            _make_paper("10.1000/a", "Paper A again"),  # duplicate
        ]
        result = deduplicate_papers(papers)
        assert len(result) == 7

    def test_deduplicator_removes_title_duplicates(self):
        """Papers without DOIs but near-identical titles should be deduped."""
        papers = [
            _make_paper(None, "A Novel Approach to Battery Degradation Modelling"),
            _make_paper(None, "A Novel Approach to Battery Degradation Modelling"),  # exact dup
            _make_paper(None, "Something Completely Different"),
        ]
        result = deduplicate_papers(papers)
        assert len(result) == 2

    def test_deduplicator_skips_existing_dois(self):
        """Papers with DOIs already in DB should be skipped."""
        papers = [
            _make_paper("10.1000/existing", "Already in DB"),
            _make_paper("10.1000/new", "Brand New Paper"),
        ]
        result = deduplicate_papers(papers, existing_dois={"10.1000/existing"})
        assert len(result) == 1
        assert result[0]["doi"] == "10.1000/new"

    def test_deduplicator_removes_duplicates(self):
        """Feed 10 papers with 3 duplicates, assert output has 7."""
        papers = [
            _make_paper("10.1000/1", "Paper 1"),
            _make_paper("10.1000/2", "Paper 2"),
            _make_paper("10.1000/3", "Paper 3"),
            _make_paper("10.1000/4", "Paper 4"),
            _make_paper("10.1000/5", "Paper 5"),
            _make_paper("10.1000/6", "Paper 6"),
            _make_paper("10.1000/7", "Paper 7"),
            _make_paper("10.1000/1", "Paper 1 dup"),   # dup
            _make_paper("10.1000/3", "Paper 3 dup"),   # dup
            _make_paper("10.1000/5", "Paper 5 dup"),   # dup
        ]
        result = deduplicate_papers(papers)
        assert len(result) == 7


class TestRSS:
    @pytest.mark.asyncio
    async def test_rss_returns_papers(self):
        """Parse Nature Energy RSS, assert >= 1 result."""
        papers = await fetch_rss_papers(
            "https://www.nature.com/nenergy.rss",
            lookback_days=90,  # Use wider window for testing
        )
        assert len(papers) >= 1
        for paper in papers:
            assert "title" in paper
            assert paper["title"]


class TestIEEE:
    @pytest.mark.asyncio
    async def test_ieee_returns_papers(self):
        """Call IEEE API for Trans. Smart Grid, assert results have required keys."""
        from app.config import get_settings
        settings = get_settings()
        if not settings.ieee_api_key:
            pytest.skip("IEEE_API_KEY not configured")

        from app.services.discovery.ieee import fetch_ieee_papers
        papers = await fetch_ieee_papers("5165411", lookback_days=30)
        if len(papers) == 0:
            pytest.skip("IEEE API returned no results (key may be inactive — check https://developer.ieee.org/)")
        for paper in papers:
            assert "title" in paper
            assert "doi" in paper
            assert "abstract" in paper


class TestScopus:
    @pytest.mark.asyncio
    async def test_scopus_returns_papers(self):
        """Call Scopus for Applied Energy, assert >= 1 result."""
        from app.config import get_settings
        settings = get_settings()
        if not settings.scopus_api_key:
            pytest.skip("SCOPUS_API_KEY not configured")

        from app.services.discovery.scopus import fetch_scopus_papers
        papers = await fetch_scopus_papers("ISSN:0306-2619", lookback_days=30)
        assert len(papers) >= 1
        for paper in papers:
            assert "title" in paper


class TestPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_saves_to_db(self, db_session):
        """Save papers via save_papers and verify they're in the DB."""
        test_papers = [
            _make_paper("10.1000/test1", "Test Paper 1"),
            _make_paper("10.1000/test2", "Test Paper 2"),
            _make_paper("10.1000/test3", "Test Paper 3"),
        ]
        saved = await save_papers(db_session, test_papers)
        assert saved == 3

        result = await db_session.execute(select(func.count()).select_from(Paper))
        count = result.scalar()
        assert count == 3
