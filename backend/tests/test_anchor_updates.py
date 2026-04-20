"""Tests for Phase 1 Chunk 3: anchor updates from ratings and feedback."""

import uuid

import pytest
import pytest_asyncio

from app.models.paper import Paper
from app.models.user_profile import UserProfile
from app.models.reference_paper import ReferencePaper
from app.routers.ratings import feedback_to_anchor_spec, apply_anchor_update


FAKE_EMBEDDING = [0.1] * 10


async def _seed_user(db, user_id=None):
    uid = user_id or uuid.uuid4()
    profile = UserProfile(
        id=uid, full_name="Test User", email="test@test.com", role="researcher",
    )
    db.add(profile)
    await db.flush()
    return uid


_SENTINEL = object()


async def _seed_paper(db, paper_id=None, embedding=_SENTINEL):
    pid = paper_id or uuid.uuid4()
    paper = Paper(
        id=pid, title=f"Paper {pid}", authors=["Author"],
        journal="J", journal_source="rss",
        embedding=FAKE_EMBEDDING if embedding is _SENTINEL else embedding,
    )
    db.add(paper)
    await db.flush()
    return pid


# ---------------------------------------------------------------------------
# feedback_to_anchor_spec tests
# ---------------------------------------------------------------------------

class TestFeedbackToAnchorSpec:
    def test_rating_9_no_feedback(self):
        spec = feedback_to_anchor_spec(9, None)
        assert spec["polarity"] == "positive"
        assert spec["weight"] == 1.5
        assert spec["tags"] == []

    def test_rating_9_methods_gem(self):
        spec = feedback_to_anchor_spec(9, "Tag as methods gem")
        assert spec["weight"] == 1.5
        assert spec["tags"] == ["methods"]

    def test_rating_2_no_feedback(self):
        spec = feedback_to_anchor_spec(2, None)
        assert spec["polarity"] == "negative"
        assert spec["weight"] == 1.0

    def test_rating_2_right_topic_weak(self):
        spec = feedback_to_anchor_spec(2, "Right topic, weak paper")
        assert spec == {"remove": True}

    def test_rating_5_no_feedback(self):
        spec = feedback_to_anchor_spec(5, None)
        assert spec is None

    def test_rating_5_adjacent(self):
        spec = feedback_to_anchor_spec(5, "Adjacent topic, not quite my focus")
        assert spec["polarity"] == "negative"
        assert spec["weight"] == 0.3

    def test_rating_8_methodology(self):
        spec = feedback_to_anchor_spec(8, "The methodology / technique")
        assert spec["polarity"] == "positive"
        assert spec["tags"] == ["methods"]

    def test_rating_10_promote(self):
        spec = feedback_to_anchor_spec(10, "Promote to my reference papers")
        assert spec["promote_to_reference"] is True

    def test_rating_10_extra_weight(self):
        spec = feedback_to_anchor_spec(10, "Extra-weight positive anchor")
        assert spec["weight"] == 2.0


# ---------------------------------------------------------------------------
# apply_anchor_update integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rating_9_adds_positive_anchor(db_session):
    """Rate paper=9 (no feedback) → paper appears in positive_anchors with weight 1.5."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await db_session.commit()

    spec = feedback_to_anchor_spec(9, None)
    await apply_anchor_update(db_session, uid, pid, spec)

    await db_session.refresh(
        (await db_session.execute(
            __import__("sqlalchemy").select(UserProfile).where(UserProfile.id == uid)
        )).scalar_one()
    )
    profile = (await db_session.execute(
        __import__("sqlalchemy").select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()

    assert len(profile.positive_anchors) == 1
    assert profile.positive_anchors[0]["weight"] == 1.5
    assert profile.positive_anchors[0]["tags"] == []
    assert profile.positive_anchors[0]["source"] == "rating"


@pytest.mark.asyncio
async def test_feedback_updates_existing_anchor(db_session):
    """Submit feedback 'Tag as methods gem' → same paper, now tags=['methods']."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await db_session.commit()

    # First: rating=9, no feedback
    spec = feedback_to_anchor_spec(9, None)
    await apply_anchor_update(db_session, uid, pid, spec)

    # Then: feedback adds tags
    spec = feedback_to_anchor_spec(9, "Tag as methods gem")
    await apply_anchor_update(db_session, uid, pid, spec)

    from sqlalchemy import select
    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()

    assert len(profile.positive_anchors) == 1
    assert profile.positive_anchors[0]["tags"] == ["methods"]


@pytest.mark.asyncio
async def test_rating_2_adds_negative_anchor(db_session):
    """Rate paper=2, no feedback → paper appears in negative_anchors with weight 1.0."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await db_session.commit()

    spec = feedback_to_anchor_spec(2, None)
    await apply_anchor_update(db_session, uid, pid, spec)

    from sqlalchemy import select
    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()

    assert len(profile.negative_anchors) == 1
    assert profile.negative_anchors[0]["weight"] == 1.0


@pytest.mark.asyncio
async def test_rating_2_then_weak_paper_removes_anchor(db_session):
    """Rate paper=2, then feedback 'Right topic, weak paper' → removed from negative_anchors."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await db_session.commit()

    # Rating adds negative anchor
    spec = feedback_to_anchor_spec(2, None)
    await apply_anchor_update(db_session, uid, pid, spec)

    # Feedback removes it
    spec = feedback_to_anchor_spec(2, "Right topic, weak paper")
    await apply_anchor_update(db_session, uid, pid, spec)

    from sqlalchemy import select
    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()

    assert len(profile.negative_anchors) == 0


@pytest.mark.asyncio
async def test_promote_to_reference_succeeds(db_session):
    """Rate 9 + 'Promote to my reference papers' with <20 refs → added to reference_papers."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session)
    await db_session.commit()

    spec = feedback_to_anchor_spec(9, "Promote to my reference papers")
    await apply_anchor_update(db_session, uid, pid, spec)

    from sqlalchemy import select
    refs = (await db_session.execute(
        select(ReferencePaper).where(ReferencePaper.user_id == uid)
    )).scalars().all()
    assert len(refs) == 1
    assert refs[0].source == "promoted"

    # Also check positive_anchors has the reference-sourced entry
    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    ref_anchors = [a for a in profile.positive_anchors if a["source"] == "reference"]
    assert len(ref_anchors) == 1


@pytest.mark.asyncio
async def test_promote_to_reference_full_raises_409(db_session):
    """Rate 9 + 'Promote' with user at 20 refs → HTTP 409."""
    uid = await _seed_user(db_session)
    # Seed 20 reference papers
    for i in range(20):
        db_session.add(ReferencePaper(
            id=uuid.uuid4(), user_id=uid,
            title=f"Ref {i}", source="manual", embedding=FAKE_EMBEDDING,
        ))
    pid = await _seed_paper(db_session)
    await db_session.commit()

    spec = feedback_to_anchor_spec(9, "Promote to my reference papers")
    with pytest.raises(Exception) as exc_info:
        await apply_anchor_update(db_session, uid, pid, spec)
    assert "409" in str(exc_info.value.status_code) or exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_no_embedding_paper_skips(db_session):
    """Rating a paper with no embedding logs warning and doesn't crash."""
    uid = await _seed_user(db_session)
    pid = await _seed_paper(db_session, embedding=None)
    await db_session.commit()

    spec = feedback_to_anchor_spec(9, None)
    # Should not raise
    await apply_anchor_update(db_session, uid, pid, spec)

    from sqlalchemy import select
    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    # No anchor added because paper has no embedding
    assert len(profile.positive_anchors) == 0
