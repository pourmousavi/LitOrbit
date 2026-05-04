"""Tests for Phase 2 Chunk 1: reembed_corpus script."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.paper import Paper
from app.models.reference_paper import ReferencePaper
from app.models.user_profile import UserProfile
from app.services.ranking.embedder import EMBEDDING_TASK_TYPE, EmbeddingQuotaExhausted
from scripts.reembed_corpus import phase_a, phase_b, dry_run


FAKE_OLD_EMBEDDING = [0.1] * 10
FAKE_NEW_EMBEDDING = [0.9] * 10


def _now():
    return datetime.now(timezone.utc)


async def _seed_paper(db, paper_id=None, embedding=FAKE_OLD_EMBEDDING, task_type=None):
    pid = paper_id or uuid.uuid4()
    paper = Paper(
        id=pid, title=f"Paper {pid}", authors=["A"],
        journal="J", journal_source="rss",
        embedding=embedding,
        embedding_task_type=task_type,
    )
    db.add(paper)
    await db.flush()
    return pid


async def _seed_ref_paper(db, user_id, ref_id=None, embedding=FAKE_OLD_EMBEDDING, task_type=None):
    rid = ref_id or uuid.uuid4()
    ref = ReferencePaper(
        id=rid, user_id=user_id, title=f"Ref {rid}",
        source="manual", embedding=embedding,
        embedding_task_type=task_type,
    )
    db.add(ref)
    await db.flush()
    return rid


async def _seed_user(db, user_id=None):
    uid = user_id or uuid.uuid4()
    profile = UserProfile(id=uid, full_name="Test", email="test@test.com", role="researcher")
    db.add(profile)
    await db.flush()
    return uid


# ---------------------------------------------------------------------------
# Phase A tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase_a_reembeds_pending_papers(db_session):
    """5 pending papers get re-embedded; 2 already-done are untouched; 1 with no embedding is ignored."""
    # 5 pending (embedding set, task_type NULL)
    pending_ids = []
    for _ in range(5):
        pid = await _seed_paper(db_session, embedding=FAKE_OLD_EMBEDDING, task_type=None)
        pending_ids.append(pid)

    # 2 already done
    done_ids = []
    done_embedding = [0.5] * 10
    for _ in range(2):
        pid = await _seed_paper(db_session, embedding=done_embedding, task_type=EMBEDDING_TASK_TYPE)
        done_ids.append(pid)

    # 1 with no embedding
    no_emb_id = await _seed_paper(db_session, embedding=None, task_type=None)

    await db_session.commit()

    with patch("scripts.reembed_corpus.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = FAKE_NEW_EMBEDDING
        result = await phase_a(db_session)

    assert result is True  # complete

    # Verify pending papers are re-embedded.
    # Paper.embedding is deferred=True (egress optimisation), so we refresh
    # the column explicitly before reading rather than relying on implicit
    # lazy-load (which doesn't work in async without a greenlet bridge).
    for pid in pending_ids:
        paper = await db_session.get(Paper, pid)
        await db_session.refresh(paper, ["embedding"])
        assert paper.embedding == FAKE_NEW_EMBEDDING
        assert paper.embedding_task_type == EMBEDDING_TASK_TYPE

    # Verify already-done papers are untouched
    for pid in done_ids:
        paper = await db_session.get(Paper, pid)
        await db_session.refresh(paper, ["embedding"])
        assert paper.embedding == done_embedding
        assert paper.embedding_task_type == EMBEDDING_TASK_TYPE

    # Verify no-embedding paper is untouched
    paper = await db_session.get(Paper, no_emb_id)
    await db_session.refresh(paper, ["embedding"])
    assert paper.embedding is None
    assert paper.embedding_task_type is None

    # embed_text called exactly 5 times (for the 5 pending papers)
    assert mock_embed.call_count == 5


@pytest.mark.asyncio
async def test_phase_a_second_run_is_noop(db_session):
    """After full sweep, second run reports 0 pending."""
    for _ in range(3):
        await _seed_paper(db_session, embedding=FAKE_OLD_EMBEDDING, task_type=None)
    await db_session.commit()

    with patch("scripts.reembed_corpus.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = FAKE_NEW_EMBEDDING
        await phase_a(db_session)

        # Second run
        mock_embed.reset_mock()
        result = await phase_a(db_session)

    assert result is True
    assert mock_embed.call_count == 0


@pytest.mark.asyncio
async def test_phase_a_limit(db_session):
    """--limit 3 re-embeds only 3 of 5 papers."""
    for _ in range(5):
        await _seed_paper(db_session, embedding=FAKE_OLD_EMBEDDING, task_type=None)
    await db_session.commit()

    with patch("scripts.reembed_corpus.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = FAKE_NEW_EMBEDDING
        await phase_a(db_session, limit=3)

    # Count how many are done now
    result = await db_session.execute(
        select(Paper).where(Paper.embedding_task_type == EMBEDDING_TASK_TYPE)
    )
    done = result.scalars().all()
    assert len(done) == 3


@pytest.mark.asyncio
async def test_phase_a_quota_exhaustion(db_session):
    """Quota exhaustion on 3rd call: 2 papers re-embedded, 3 pending, exit code 0."""
    for _ in range(5):
        await _seed_paper(db_session, embedding=FAKE_OLD_EMBEDDING, task_type=None)
    await db_session.commit()

    call_count = 0

    async def _mock_embed(text):
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            return None  # quota exhausted
        return FAKE_NEW_EMBEDDING

    with patch("scripts.reembed_corpus.embed_text", side_effect=_mock_embed):
        result = await phase_a(db_session)

    assert result is False  # not complete

    done_result = await db_session.execute(
        select(Paper).where(Paper.embedding_task_type == EMBEDDING_TASK_TYPE)
    )
    assert len(done_result.scalars().all()) == 2

    pending_result = await db_session.execute(
        select(Paper).where(Paper.embedding.isnot(None), Paper.embedding_task_type.is_(None))
    )
    assert len(pending_result.scalars().all()) == 3


# ---------------------------------------------------------------------------
# Phase B tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase_b_refreshes_swept_anchors(db_session):
    """Anchors for swept papers get refreshed_at; unsswept are untouched."""
    uid = await _seed_user(db_session)

    # 2 swept papers
    p1 = await _seed_paper(db_session, embedding=FAKE_NEW_EMBEDDING, task_type=EMBEDDING_TASK_TYPE)
    p2 = await _seed_paper(db_session, embedding=FAKE_NEW_EMBEDDING, task_type=EMBEDDING_TASK_TYPE)
    # 1 unswept paper
    p3 = await _seed_paper(db_session, embedding=FAKE_OLD_EMBEDDING, task_type=None)

    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()

    profile.positive_anchors = [
        {"paper_id": str(p1), "embedding": FAKE_OLD_EMBEDDING, "source": "rating", "weight": 1.0, "added_at": _now().isoformat(), "tags": []},
        {"paper_id": str(p2), "embedding": FAKE_OLD_EMBEDDING, "source": "reference", "weight": 1.0, "added_at": _now().isoformat(), "tags": []},
        {"paper_id": str(p3), "embedding": FAKE_OLD_EMBEDDING, "source": "rating", "weight": 1.0, "added_at": _now().isoformat(), "tags": []},
    ]
    await db_session.commit()

    await phase_b(db_session)

    await db_session.refresh(profile)
    anchors = profile.positive_anchors

    # p1 and p2 anchors refreshed
    a1 = next(a for a in anchors if a["paper_id"] == str(p1))
    assert a1["embedding"] == FAKE_NEW_EMBEDDING
    assert "refreshed_at" in a1

    a2 = next(a for a in anchors if a["paper_id"] == str(p2))
    assert a2["embedding"] == FAKE_NEW_EMBEDDING
    assert "refreshed_at" in a2

    # p3 anchor untouched
    a3 = next(a for a in anchors if a["paper_id"] == str(p3))
    assert a3["embedding"] == FAKE_OLD_EMBEDDING
    assert "refreshed_at" not in a3


@pytest.mark.asyncio
async def test_skip_anchors_leaves_profiles_untouched(db_session):
    """--skip-anchors: Phase A runs but user_profiles are untouched."""
    uid = await _seed_user(db_session)
    p1 = await _seed_paper(db_session, embedding=FAKE_OLD_EMBEDDING, task_type=None)

    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.id == uid)
    )).scalar_one()
    profile.positive_anchors = [
        {"paper_id": str(p1), "embedding": FAKE_OLD_EMBEDDING, "source": "rating", "weight": 1.0, "added_at": _now().isoformat(), "tags": []},
    ]
    await db_session.commit()

    with patch("scripts.reembed_corpus.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = FAKE_NEW_EMBEDDING
        await phase_a(db_session)

    # Phase B NOT called — anchors should still have old embedding
    await db_session.refresh(profile)
    assert profile.positive_anchors[0]["embedding"] == FAKE_OLD_EMBEDDING


@pytest.mark.asyncio
async def test_dry_run_no_db_writes(db_session, capsys):
    """--dry-run prints stats but makes no DB changes."""
    uid = await _seed_user(db_session)
    for _ in range(3):
        await _seed_paper(db_session, embedding=FAKE_OLD_EMBEDDING, task_type=None)
    await _seed_paper(db_session, embedding=FAKE_NEW_EMBEDDING, task_type=EMBEDDING_TASK_TYPE)
    await db_session.commit()

    await dry_run(db_session)

    captured = capsys.readouterr()
    assert "3" in captured.out  # 3 pending
    assert "1 already done" in captured.out
    assert "dry-run" in captured.out.lower()

    # No papers should have changed
    result = await db_session.execute(
        select(Paper).where(Paper.embedding_task_type.is_(None), Paper.embedding.isnot(None))
    )
    assert len(result.scalars().all()) == 3


@pytest.mark.asyncio
async def test_phase_a_reembeds_reference_papers(db_session):
    """Reference papers are also re-embedded in Phase A."""
    uid = await _seed_user(db_session)
    rid = await _seed_ref_paper(db_session, uid, embedding=FAKE_OLD_EMBEDDING, task_type=None)
    await db_session.commit()

    with patch("scripts.reembed_corpus.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = FAKE_NEW_EMBEDDING
        await phase_a(db_session)

    ref = await db_session.get(ReferencePaper, rid)
    await db_session.refresh(ref, ["embedding"])
    assert ref.embedding == FAKE_NEW_EMBEDDING
    assert ref.embedding_task_type == EMBEDDING_TASK_TYPE
