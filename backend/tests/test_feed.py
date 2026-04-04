"""Tests for the podcast RSS feed feature."""

import uuid
from xml.etree.ElementTree import fromstring

import pytest
import pytest_asyncio

from app.models.podcast import Podcast
from app.models.user_profile import UserProfile


ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


@pytest_asyncio.fixture
async def feed_user(db_session):
    """Create a user with podcast feed enabled and a feed token."""
    user = UserProfile(
        id=uuid.uuid4(),
        full_name="Feed Tester",
        email="feed@example.com",
        role="researcher",
        podcast_feed_enabled=True,
        podcast_feed_token="test-feed-token-abc",
        podcast_feed_title="My Research Digest",
        podcast_feed_description="A custom description",
        podcast_feed_author="Dr. Feed",
        podcast_feed_cover_url="https://example.com/cover.png",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def feed_with_podcasts(db_session, feed_user):
    """Create digest podcasts for the feed user."""
    podcasts = []
    for i in range(3):
        pod = Podcast(
            id=uuid.uuid4(),
            paper_id=None,
            user_id=feed_user.id,
            voice_mode="dual",
            podcast_type="digest",
            title=f"Weekly Digest — Episode {i + 1}",
            audio_path=f"https://storage.example.com/digest-{i}.mp3",
            duration_seconds=300 + i * 60,
        )
        podcasts.append(pod)
        db_session.add(pod)
    await db_session.commit()
    return feed_user, podcasts


class TestFeedXmlGeneration:
    """Test the RSS XML builder directly."""

    def test_build_feed_xml_basic(self, feed_user):
        """Feed XML contains channel metadata from user profile."""
        from app.routers.feed import _build_feed_xml

        xml_bytes = _build_feed_xml(feed_user, [])
        xml_str = xml_bytes.decode("utf-8")
        root = fromstring(xml_str)

        channel = root.find("channel")
        assert channel is not None
        assert channel.find("title").text == "My Research Digest"
        assert channel.find("description").text == "A custom description"
        assert channel.find(f"{{{ITUNES_NS}}}author").text == "Dr. Feed"
        assert channel.find(f"{{{ITUNES_NS}}}image").get("href") == "https://example.com/cover.png"

    def test_build_feed_xml_defaults(self):
        """Feed XML uses defaults when user hasn't customized."""
        from app.routers.feed import _build_feed_xml

        user = UserProfile(
            id=uuid.uuid4(),
            full_name="Jane Doe",
            email="jane@example.com",
            role="researcher",
            podcast_feed_enabled=True,
            podcast_feed_token="token-123",
        )
        xml_bytes = _build_feed_xml(user, [])
        root = fromstring(xml_bytes.decode("utf-8"))
        channel = root.find("channel")

        assert channel.find("title").text == "LitOrbit Digest — Jane Doe"
        assert "LitOrbit" in channel.find("description").text
        assert channel.find(f"{{{ITUNES_NS}}}author").text == "Jane Doe"
        # No cover art when not set
        assert channel.find(f"{{{ITUNES_NS}}}image") is None

    def test_build_feed_xml_with_episodes(self):
        """Feed XML includes podcast episodes as items."""
        from app.routers.feed import _build_feed_xml

        user = UserProfile(
            id=uuid.uuid4(),
            full_name="Test",
            email="test@example.com",
            role="researcher",
            podcast_feed_enabled=True,
            podcast_feed_token="token-456",
        )
        pod1 = Podcast(
            id=uuid.uuid4(),
            paper_id=None,
            user_id=user.id,
            voice_mode="dual",
            podcast_type="digest",
            title="Weekly Digest — Apr 04, 2026",
            audio_path="https://storage.example.com/ep1.mp3",
            duration_seconds=600,
        )
        pod2 = Podcast(
            id=uuid.uuid4(),
            paper_id=None,
            user_id=user.id,
            voice_mode="single",
            podcast_type="digest",
            title="Daily Digest — Apr 03, 2026",
            audio_path="https://storage.example.com/ep2.mp3",
            duration_seconds=180,
        )

        xml_bytes = _build_feed_xml(user, [pod1, pod2])
        root = fromstring(xml_bytes.decode("utf-8"))
        items = root.findall("channel/item")

        assert len(items) == 2
        assert items[0].find("title").text == "Weekly Digest — Apr 04, 2026"
        assert items[1].find("title").text == "Daily Digest — Apr 03, 2026"

        # Check enclosure
        enc = items[0].find("enclosure")
        assert enc.get("url") == "https://storage.example.com/ep1.mp3"
        assert enc.get("type") == "audio/mpeg"

        # Check duration
        duration = items[0].find(f"{{{ITUNES_NS}}}duration")
        assert duration.text == "10:00"

        # Check guid
        assert items[0].find("guid").text == str(pod1.id)

    def test_build_feed_xml_skips_no_audio(self):
        """Podcasts without audio_path are excluded."""
        from app.routers.feed import _build_feed_xml

        user = UserProfile(
            id=uuid.uuid4(), full_name="T", email="t@t.com", role="researcher",
            podcast_feed_enabled=True, podcast_feed_token="tok",
        )
        pod_no_audio = Podcast(
            id=uuid.uuid4(), paper_id=None, user_id=user.id,
            voice_mode="single", podcast_type="digest",
            title="No Audio", audio_path=None,
        )
        pod_with_audio = Podcast(
            id=uuid.uuid4(), paper_id=None, user_id=user.id,
            voice_mode="single", podcast_type="digest",
            title="Has Audio", audio_path="https://example.com/a.mp3",
            duration_seconds=120,
        )
        xml_bytes = _build_feed_xml(user, [pod_no_audio, pod_with_audio])
        root = fromstring(xml_bytes.decode("utf-8"))
        items = root.findall("channel/item")
        assert len(items) == 1
        assert items[0].find("title").text == "Has Audio"


class TestFeedHelpers:
    def test_format_duration_minutes(self):
        from app.routers.feed import _format_duration
        assert _format_duration(600) == "10:00"
        assert _format_duration(65) == "1:05"
        assert _format_duration(0) == "0:00"
        assert _format_duration(None) == "0:00"

    def test_format_duration_hours(self):
        from app.routers.feed import _format_duration
        assert _format_duration(3661) == "1:01:01"
        assert _format_duration(7200) == "2:00:00"

    def test_rfc2822(self):
        from datetime import datetime, timezone
        from app.routers.feed import _rfc2822
        dt = datetime(2026, 4, 4, 6, 0, 0, tzinfo=timezone.utc)
        result = _rfc2822(dt)
        assert "04 Apr 2026" in result
        assert "06:00:00" in result

    def test_rfc2822_none(self):
        from app.routers.feed import _rfc2822
        assert _rfc2822(None) == ""


class TestFeedEndpoint:
    @pytest.mark.asyncio
    async def test_valid_feed(self, test_client, db_session, feed_with_podcasts):
        """GET /feed/{token}.xml returns valid RSS XML with episodes."""
        user, podcasts = feed_with_podcasts

        resp = await test_client.get(f"/api/v1/feed/{user.podcast_feed_token}.xml")
        assert resp.status_code == 200
        assert "application/rss+xml" in resp.headers["content-type"]

        root = fromstring(resp.content)
        channel = root.find("channel")
        assert channel.find("title").text == "My Research Digest"

        items = root.findall("channel/item")
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_invalid_token(self, test_client, db_session):
        """GET /feed/{bad_token}.xml returns 404."""
        resp = await test_client.get("/api/v1/feed/nonexistent-token.xml")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_disabled_feed(self, test_client, db_session):
        """Feed returns 404 when disabled even with valid token."""
        user = UserProfile(
            id=uuid.uuid4(),
            full_name="Disabled Feed",
            email="disabled@example.com",
            role="researcher",
            podcast_feed_enabled=False,
            podcast_feed_token="disabled-token-xyz",
        )
        db_session.add(user)
        await db_session.commit()

        resp = await test_client.get("/api/v1/feed/disabled-token-xyz.xml")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_feed(self, test_client, db_session, feed_user):
        """Feed with no podcasts returns valid XML with zero items."""
        resp = await test_client.get(f"/api/v1/feed/{feed_user.podcast_feed_token}.xml")
        assert resp.status_code == 200

        root = fromstring(resp.content)
        items = root.findall("channel/item")
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_feed_excludes_paper_podcasts(self, test_client, db_session, feed_user):
        """Feed only includes digest podcasts, not paper podcasts."""
        from app.models.paper import Paper

        paper = Paper(
            id=uuid.uuid4(), title="Test Paper", authors=["A"],
            journal="J", journal_source="rss",
        )
        db_session.add(paper)
        await db_session.flush()

        # Paper podcast — should NOT appear in feed
        paper_pod = Podcast(
            id=uuid.uuid4(), paper_id=paper.id, user_id=feed_user.id,
            voice_mode="single", podcast_type="paper",
            audio_path="https://example.com/paper.mp3", duration_seconds=120,
        )
        # Digest podcast — should appear
        digest_pod = Podcast(
            id=uuid.uuid4(), paper_id=None, user_id=feed_user.id,
            voice_mode="dual", podcast_type="digest",
            title="Digest Episode", audio_path="https://example.com/digest.mp3",
            duration_seconds=600,
        )
        db_session.add_all([paper_pod, digest_pod])
        await db_session.commit()

        resp = await test_client.get(f"/api/v1/feed/{feed_user.podcast_feed_token}.xml")
        root = fromstring(resp.content)
        items = root.findall("channel/item")
        assert len(items) == 1
        assert items[0].find("title").text == "Digest Episode"


class TestFeedProfileAPI:
    @pytest.mark.asyncio
    async def test_enable_feed_generates_token(self, test_client, db_session):
        """Enabling feed auto-generates a feed token."""
        from app.auth import get_current_user
        from app.main import app

        user_id = uuid.uuid4()
        user = UserProfile(
            id=user_id, full_name="Token Test", email="token@test.com",
            role="researcher", podcast_feed_enabled=False,
        )
        db_session.add(user)
        await db_session.commit()

        fake_user = {"id": str(user_id), "email": "token@test.com", "role": "researcher"}
        app.dependency_overrides[get_current_user] = lambda: fake_user

        # Enable feed
        resp = await test_client.patch("/api/v1/users/me", json={"podcast_feed_enabled": True})
        assert resp.status_code == 200

        # Verify token was generated
        resp = await test_client.get("/api/v1/users/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["podcast_feed_enabled"] is True
        assert data["podcast_feed_token"] is not None
        assert len(data["podcast_feed_token"]) > 10

        del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_update_feed_settings(self, test_client, db_session):
        """Feed title, description, author, cover_url are updatable."""
        from app.auth import get_current_user
        from app.main import app

        user_id = uuid.uuid4()
        user = UserProfile(
            id=user_id, full_name="Settings Test", email="settings@test.com",
            role="researcher", podcast_feed_enabled=True,
            podcast_feed_token="settings-token",
        )
        db_session.add(user)
        await db_session.commit()

        fake_user = {"id": str(user_id), "email": "settings@test.com", "role": "researcher"}
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await test_client.patch("/api/v1/users/me", json={
            "podcast_feed_title": "My Custom Podcast",
            "podcast_feed_description": "Best research digest ever",
            "podcast_feed_author": "Dr. Custom",
            "podcast_feed_cover_url": "https://example.com/art.png",
        })
        assert resp.status_code == 200

        resp = await test_client.get("/api/v1/users/me")
        data = resp.json()
        assert data["podcast_feed_title"] == "My Custom Podcast"
        assert data["podcast_feed_description"] == "Best research digest ever"
        assert data["podcast_feed_author"] == "Dr. Custom"
        assert data["podcast_feed_cover_url"] == "https://example.com/art.png"

        del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_clear_feed_settings(self, test_client, db_session):
        """Empty strings clear feed settings to None."""
        from app.auth import get_current_user
        from app.main import app

        user_id = uuid.uuid4()
        user = UserProfile(
            id=user_id, full_name="Clear Test", email="clear@test.com",
            role="researcher", podcast_feed_enabled=True,
            podcast_feed_token="clear-token",
            podcast_feed_title="Old Title",
        )
        db_session.add(user)
        await db_session.commit()

        fake_user = {"id": str(user_id), "email": "clear@test.com", "role": "researcher"}
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await test_client.patch("/api/v1/users/me", json={
            "podcast_feed_title": "",
        })
        assert resp.status_code == 200

        resp = await test_client.get("/api/v1/users/me")
        assert resp.json()["podcast_feed_title"] is None

        del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_get_me_includes_feed_fields(self, test_client, db_session):
        """GET /me returns all feed fields."""
        from app.auth import get_current_user
        from app.main import app

        user_id = uuid.uuid4()
        user = UserProfile(
            id=user_id, full_name="Fields Test", email="fields@test.com",
            role="researcher", podcast_feed_enabled=True,
            podcast_feed_token="fields-token",
        )
        db_session.add(user)
        await db_session.commit()

        fake_user = {"id": str(user_id), "email": "fields@test.com", "role": "researcher"}
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await test_client.get("/api/v1/users/me")
        data = resp.json()

        assert "podcast_feed_enabled" in data
        assert "podcast_feed_token" in data
        assert "podcast_feed_title" in data
        assert "podcast_feed_description" in data
        assert "podcast_feed_author" in data
        assert "podcast_feed_cover_url" in data

        del app.dependency_overrides[get_current_user]
