"""Tests for the digest feature: email generation, digest podcast, digest runner, deduplication."""

import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.digest_log import DigestLog
from app.models.paper import Paper
from app.models.paper_score import PaperScore
from app.models.podcast import Podcast
from app.models.share import Share
from app.models.user_profile import UserProfile
from app.services.email_digest import generate_digest_html
from app.services.digest_podcast import (
    _build_papers_block,
    _estimate_minutes,
    generate_digest_script,
)


# ---------------------------------------------------------------------------
# Email template tests
# ---------------------------------------------------------------------------

class TestDigestEmailTemplate:
    def test_weekly_digest_html(self):
        """Weekly digest shows 'Weekly Digest' and 'Top Papers This Week'."""
        html = generate_digest_html(
            user_name="Alice",
            papers=[{"title": "Paper A", "journal": "J1", "score": 9.0, "summary_excerpt": "Excerpt A"}],
            shared_papers=[],
            dashboard_url="https://app.example.com",
            unsubscribe_url="https://app.example.com/unsub",
            frequency="weekly",
        )
        assert "Weekly Digest" in html
        assert "Top Papers This Week" in html
        assert "Paper A" in html

    def test_daily_digest_html(self):
        """Daily digest shows 'Daily Digest' and 'Top Papers This Day'."""
        html = generate_digest_html(
            user_name="Bob",
            papers=[{"title": "Paper B", "journal": "J2", "score": 6.0, "summary_excerpt": None}],
            shared_papers=[],
            dashboard_url="https://app.example.com",
            unsubscribe_url="https://app.example.com/unsub",
            frequency="daily",
        )
        assert "Daily Digest" in html
        assert "Top Papers This Day" in html

    def test_digest_with_podcast_section(self):
        """Digest email includes podcast section when podcast data is provided."""
        html = generate_digest_html(
            user_name="Charlie",
            papers=[{"title": "P", "journal": "J", "score": 7.0, "summary_excerpt": "..."}],
            shared_papers=[],
            dashboard_url="https://app.example.com",
            unsubscribe_url="https://app.example.com/unsub",
            frequency="weekly",
            podcast={
                "title": "Weekly Digest — Apr 04, 2026",
                "voice_label": "Dual voice",
                "duration_label": "5m 30s",
                "play_url": "https://app.example.com/podcasts?play=abc",
            },
        )
        assert "Weekly Digest — Apr 04, 2026" in html
        assert "Dual voice" in html
        assert "5m 30s" in html
        assert "Listen Now" in html
        assert "podcasts?play=abc" in html

    def test_digest_without_podcast(self):
        """Digest email omits podcast section when podcast=None."""
        html = generate_digest_html(
            user_name="Dave",
            papers=[],
            shared_papers=[],
            dashboard_url="https://app.example.com",
            unsubscribe_url="https://app.example.com/unsub",
            frequency="weekly",
            podcast=None,
        )
        assert "Listen Now" not in html

    def test_backward_compat_no_frequency(self):
        """Calling without frequency defaults to weekly (backward compat)."""
        html = generate_digest_html(
            user_name="Eve",
            papers=[],
            shared_papers=[],
            dashboard_url="https://app.example.com",
            unsubscribe_url="https://app.example.com/unsub",
        )
        assert "Weekly Digest" in html


# ---------------------------------------------------------------------------
# Digest podcast script generation
# ---------------------------------------------------------------------------

class TestDigestPodcastHelpers:
    def test_build_papers_block(self):
        """Papers block formats numbered entries with title, journal, score, summary."""
        papers = [
            {"title": "Paper 1", "journal": "J1", "score": 8.5, "summary": "Summary 1"},
            {"title": "Paper 2", "journal": "J2", "score": 6.0, "abstract": "Abstract 2"},
        ]
        block = _build_papers_block(papers)
        assert "[1] Title: Paper 1" in block
        assert "[2] Title: Paper 2" in block
        assert "Journal: J1" in block
        assert "Relevance: 8.5/10" in block
        assert "Summary: Summary 1" in block
        assert "Abstract: Abstract 2" in block

    def test_estimate_minutes(self):
        assert _estimate_minutes(1) == 5
        assert _estimate_minutes(3) == 5
        assert _estimate_minutes(5) == 8
        assert _estimate_minutes(10) == 12


MOCK_DIGEST_DUAL_SCRIPT = """ALEX: Welcome to this week's research digest.
SAM: We've got three really interesting papers to cover today.
ALEX: Let's dive right in. What's the first one about?
SAM: It's a study on battery degradation using neural networks."""

MOCK_DIGEST_SINGLE_SCRIPT = """In this week's research digest, we cover three important papers. \
The first examines battery degradation modelling using physics-informed neural networks."""


class TestDigestScriptGeneration:
    @pytest.mark.asyncio
    async def test_digest_script_dual(self):
        """Dual-voice digest script contains ALEX/SAM markers."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=MOCK_DIGEST_DUAL_SCRIPT)]
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        papers = [
            {"title": "Paper 1", "journal": "J1", "score": 8.0, "summary": "Summary 1"},
            {"title": "Paper 2", "journal": "J2", "score": 7.0, "summary": "Summary 2"},
        ]
        script = await generate_digest_script(papers, voice_mode="dual", client=mock_client)

        assert "ALEX:" in script
        assert "SAM:" in script
        # Verify the prompt included paper count
        call_args = mock_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "2 research papers" in user_msg

    @pytest.mark.asyncio
    async def test_digest_script_single(self):
        """Single-voice digest script is a plain text block."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=MOCK_DIGEST_SINGLE_SCRIPT)]
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        papers = [{"title": "P1", "journal": "J", "score": 9.0, "summary": "S1"}]
        script = await generate_digest_script(papers, voice_mode="single", client=mock_client)

        assert isinstance(script, str)
        assert len(script) > 20


# ---------------------------------------------------------------------------
# Digest runner — DB-level integration tests
# ---------------------------------------------------------------------------

class TestDigestRunner:
    @pytest_asyncio.fixture
    async def setup_data(self, db_session):
        """Create a user, papers, and scores for digest tests."""
        user = UserProfile(
            id=uuid.uuid4(),
            full_name="Test Researcher",
            email="test@example.com",
            role="researcher",
            email_digest_enabled=True,
            digest_frequency="weekly",
            digest_podcast_enabled=False,  # disable podcast for speed
            digest_podcast_voice_mode="dual",
        )
        db_session.add(user)

        papers = []
        for i in range(5):
            paper = Paper(
                id=uuid.uuid4(),
                title=f"Test Paper {i}",
                authors=[f"Author {i}"],
                journal=f"Journal {i}",
                journal_source="rss",
                summary=json.dumps({
                    "research_gap": f"Gap {i}",
                    "methodology": f"Method {i}",
                    "key_findings": f"Finding {i}",
                    "relevance_to_energy_group": f"Relevance {i}",
                }),
            )
            papers.append(paper)
            db_session.add(paper)

        await db_session.flush()

        # Score all papers for this user
        for i, paper in enumerate(papers):
            score = PaperScore(
                id=uuid.uuid4(),
                paper_id=paper.id,
                user_id=user.id,
                relevance_score=9.0 - i,  # 9, 8, 7, 6, 5
            )
            db_session.add(score)

        await db_session.commit()
        return user, papers

    @pytest.mark.asyncio
    async def test_get_digest_papers_returns_top_n(self, db_session, setup_data):
        """Digest fetches top-N papers by relevance score."""
        from app.services.digest_runner import _get_digest_papers

        user, papers = setup_data
        result = await _get_digest_papers(db_session, user.id, "weekly", top_n=3)

        assert len(result) == 3
        scores = [score for _, score in result]
        assert scores == sorted(scores, reverse=True)  # Ordered by score desc

    @pytest.mark.asyncio
    async def test_digest_deduplication(self, db_session, setup_data):
        """Papers already sent in a previous digest are excluded."""
        from app.services.digest_runner import _get_digest_papers

        user, papers = setup_data

        # Mark papers[0] as already sent
        db_session.add(DigestLog(
            id=uuid.uuid4(),
            user_id=user.id,
            paper_id=papers[0].id,
            digest_type="weekly",
        ))
        await db_session.commit()

        result = await _get_digest_papers(db_session, user.id, "weekly", top_n=10)

        result_paper_ids = {paper.id for paper, _ in result}
        assert papers[0].id not in result_paper_ids
        assert len(result) == 4  # 5 total - 1 already sent

    @pytest.mark.asyncio
    async def test_send_digest_for_user_no_podcast(self, db_session, setup_data):
        """Send digest email without podcast, verify digest_logs are created."""
        from app.services.digest_runner import send_digest_for_user

        user, papers = setup_data

        with patch("app.services.digest_runner.send_digest_email", return_value=True) as mock_send:
            with patch("app.services.digest_runner.get_settings") as mock_settings:
                settings = MagicMock()
                settings.frontend_url = "https://app.example.com"
                mock_settings.return_value = settings

                result = await send_digest_for_user(db_session, user)

        assert result["sent"] is True
        assert result["papers"] > 0
        assert result["podcast"] is False
        mock_send.assert_called_once()

        # Verify digest_logs were created
        from sqlalchemy import select
        logs_result = await db_session.execute(
            select(DigestLog).where(DigestLog.user_id == user.id)
        )
        logs = logs_result.scalars().all()
        assert len(logs) == result["papers"]

    @pytest.mark.asyncio
    async def test_send_digest_skips_when_no_papers(self, db_session):
        """If user has no scored papers, digest is skipped."""
        from app.services.digest_runner import send_digest_for_user

        user = UserProfile(
            id=uuid.uuid4(),
            full_name="Empty User",
            email="empty@example.com",
            role="researcher",
            email_digest_enabled=True,
            digest_frequency="weekly",
            digest_podcast_enabled=False,
        )
        db_session.add(user)
        await db_session.commit()

        result = await send_digest_for_user(db_session, user)
        assert result["sent"] is False
        assert result["papers"] == 0


# ---------------------------------------------------------------------------
# Podcast model — digest type
# ---------------------------------------------------------------------------

class TestDigestPodcastModel:
    @pytest.mark.asyncio
    async def test_digest_podcast_nullable_paper_id(self, db_session):
        """Digest podcasts can be created with paper_id=None."""
        podcast = Podcast(
            id=uuid.uuid4(),
            paper_id=None,
            user_id=None,
            voice_mode="dual",
            podcast_type="digest",
            title="Weekly Digest — Apr 04, 2026",
            script="ALEX: Hello\nSAM: Hi",
            audio_path="https://example.com/audio.mp3",
            duration_seconds=300,
        )
        db_session.add(podcast)
        await db_session.commit()

        from sqlalchemy import select
        result = await db_session.execute(select(Podcast).where(Podcast.id == podcast.id))
        saved = result.scalar_one()
        assert saved.paper_id is None
        assert saved.podcast_type == "digest"
        assert saved.title == "Weekly Digest — Apr 04, 2026"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestPodcastListEndpoint:
    @pytest.mark.asyncio
    async def test_list_includes_digest_podcasts(self, test_client, db_session):
        """GET /podcasts returns both paper and digest podcasts."""
        from app.auth import get_current_user
        from app.main import app

        user_id = uuid.uuid4()
        fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

        # Create a paper podcast
        paper = Paper(id=uuid.uuid4(), title="Paper X", authors=["A"], journal="J", journal_source="rss")
        db_session.add(paper)
        await db_session.flush()

        paper_podcast = Podcast(
            id=uuid.uuid4(),
            paper_id=paper.id,
            voice_mode="single",
            podcast_type="paper",
            audio_path="https://example.com/paper.mp3",
            duration_seconds=120,
        )
        db_session.add(paper_podcast)

        # Create a digest podcast
        digest_podcast = Podcast(
            id=uuid.uuid4(),
            paper_id=None,
            voice_mode="dual",
            podcast_type="digest",
            title="Weekly Digest — Apr 04",
            audio_path="https://example.com/digest.mp3",
            duration_seconds=600,
        )
        db_session.add(digest_podcast)
        await db_session.commit()

        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await test_client.get("/api/v1/podcasts")
        assert resp.status_code == 200
        data = resp.json()

        assert len(data) == 2

        types = {item["podcast_type"] for item in data}
        assert "digest" in types
        assert "paper" in types

        digest_item = next(i for i in data if i["podcast_type"] == "digest")
        assert digest_item["paper_id"] is None
        assert digest_item["paper_title"] == "Weekly Digest — Apr 04"

        del app.dependency_overrides[get_current_user]


class TestDigestTriggerEndpoint:
    @pytest.mark.asyncio
    async def test_trigger_digest_admin_only(self, test_client, db_session):
        """POST /admin/digest/trigger requires admin auth."""
        resp = await test_client.post("/api/v1/admin/digest/trigger", json={})
        assert resp.status_code in (401, 403)
