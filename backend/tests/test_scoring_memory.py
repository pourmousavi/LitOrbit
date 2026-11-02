"""score_and_summarise_papers must only load embeddings for papers that need scoring."""

import uuid
from unittest.mock import patch

import pytest

from app.models.paper import Paper
from app.models.paper_score import PaperScore
from app.models.user_profile import UserProfile
from app.pipeline.runner import score_and_summarise_papers


class _Stop(Exception):
    pass


@pytest.mark.asyncio
async def test_only_unscored_papers_carry_embeddings(db_session):
    uid = uuid.uuid4()
    db_session.add(UserProfile(id=uid, full_name="T", email="t@example.com", role="researcher"))
    scored = Paper(id=uuid.uuid4(), title="Scored", authors=["A"], journal="J", journal_source="rss", embedding=[0.1, 0.2])
    fresh = Paper(id=uuid.uuid4(), title="Fresh", authors=["A"], journal="J", journal_source="rss", embedding=[0.3, 0.4])
    db_session.add_all([scored, fresh])
    await db_session.flush()
    db_session.add(PaperScore(id=uuid.uuid4(), paper_id=scored.id, user_id=uid, relevance_score=5.0))
    await db_session.commit()

    seen = {}

    def capture(paper_dicts, **_):
        seen.update({d["title"]: d["embedding"] for d in paper_dicts})
        raise _Stop

    with patch("app.pipeline.runner.prefilter_papers", side_effect=capture):
        with pytest.raises(_Stop):
            await score_and_summarise_papers(db_session, run=None)

    assert seen == {"Fresh": [0.3, 0.4]}
