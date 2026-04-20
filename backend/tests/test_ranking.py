import json
import math
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.ranking.prefilter import prefilter_papers
from app.services.ranking.scorer import score_paper_for_user
from app.services.ranking.embedder import knn_max_similarity, cosine_similarity


class TestPrefilter:
    def test_prefilter_passes_relevant(self):
        """Paper with 'battery degradation' in title passes."""
        papers = [
            {
                "title": "A Novel Approach to Battery Degradation Modelling",
                "abstract": "We propose a new method...",
            }
        ]
        result = prefilter_papers(papers)
        assert len(result) == 1

    def test_prefilter_blocks_irrelevant(self):
        """Paper with 'marine biology genome' is blocked."""
        papers = [
            {
                "title": "Genome Assembly of Deep-Sea Marine Biology Organisms",
                "abstract": "This paper studies coral reef genomes using RNA sequencing.",
            }
        ]
        result = prefilter_papers(papers)
        assert len(result) == 0

    def test_prefilter_matches_abstract(self):
        """Keywords in abstract should also pass."""
        papers = [
            {
                "title": "A Generic Framework for Analysis",
                "abstract": "We apply this to electricity market clearing problems.",
            }
        ]
        result = prefilter_papers(papers)
        assert len(result) == 1

    def test_prefilter_case_insensitive(self):
        """Keywords should match case-insensitively."""
        papers = [
            {
                "title": "BATTERY ENERGY STORAGE SYSTEMS",
                "abstract": "",
            }
        ]
        result = prefilter_papers(papers)
        assert len(result) == 1

    def test_prefilter_short_keywords_word_boundary(self):
        """Short keywords like 'EV' should use word boundaries."""
        papers = [
            {
                "title": "EV Charging Infrastructure Planning",
                "abstract": "",
            },
            {
                "title": "Eventually Consistent Systems",
                "abstract": "We study the eventual convergence.",
            },
        ]
        result = prefilter_papers(papers)
        # "EV" should match the first but not "Eventually"
        assert len(result) == 1
        assert result[0]["title"] == "EV Charging Infrastructure Planning"


def _make_mock_gemini_client(response_text: str):
    """Create a mock Google GenAI client that returns the given text."""
    mock_response = MagicMock()
    mock_response.text = response_text

    mock_aio = MagicMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)

    mock_client = MagicMock()
    mock_client.aio = mock_aio
    return mock_client


class TestScorer:
    @pytest.mark.asyncio
    async def test_scorer_returns_valid_score(self):
        """Mock Gemini response, assert score is float 0-10."""
        mock_client = _make_mock_gemini_client(
            '{"score": 7.5, "reasoning": "Highly relevant to battery research."}'
        )

        paper = {"title": "Battery Degradation Analysis", "abstract": "A study on lithium-ion battery aging."}
        user = {"full_name": "Ali Pourmousavi", "interest_keywords": ["battery", "degradation"], "interest_categories": ["energy storage"]}

        result = await score_paper_for_user(paper, user, client=mock_client)

        assert isinstance(result["score"], float)
        assert 0.0 <= result["score"] <= 10.0
        assert result["score"] == 7.5

    @pytest.mark.asyncio
    async def test_scorer_stores_reasoning(self):
        """Assert reasoning string is stored."""
        mock_client = _make_mock_gemini_client(
            '{"score": 8.0, "reasoning": "Directly addresses battery SOH estimation."}'
        )

        paper = {"title": "SOH Estimation Methods", "abstract": "State of health prediction."}
        user = {"full_name": "Test User", "interest_keywords": ["SOH"], "interest_categories": ["battery"]}

        result = await score_paper_for_user(paper, user, client=mock_client)

        assert result["reasoning"] == "Directly addresses battery SOH estimation."

    @pytest.mark.asyncio
    async def test_scorer_clamps_out_of_range(self):
        """Scores outside 0-10 should be clamped."""
        mock_client = _make_mock_gemini_client(
            '{"score": 15.0, "reasoning": "Off the charts"}'
        )

        paper = {"title": "Test", "abstract": "Test"}
        user = {"full_name": "Test", "interest_keywords": [], "interest_categories": []}

        result = await score_paper_for_user(paper, user, client=mock_client)
        assert result["score"] == 10.0

    @pytest.mark.asyncio
    async def test_scorer_returns_error_flag_on_success(self):
        """Successful score has error=False."""
        mock_client = _make_mock_gemini_client(
            '{"score": 5.0, "reasoning": "Legitimately scored 5.0"}'
        )
        paper = {"title": "Test", "abstract": "Test"}
        user = {"full_name": "Test", "interest_keywords": [], "interest_categories": []}
        result = await score_paper_for_user(paper, user, client=mock_client)
        # A legitimate 5.0 is NOT an error — score is float, not None
        assert result["score"] == 5.0
        assert result["error"] is False

    @pytest.mark.asyncio
    async def test_scorer_returns_error_on_raise(self):
        """When Gemini client raises, scorer returns score=None, error=True."""
        mock_aio = MagicMock()
        mock_aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API down"))
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        paper = {"title": "Test", "abstract": "Test"}
        user = {"full_name": "Test", "interest_keywords": [], "interest_categories": []}
        result = await score_paper_for_user(paper, user, client=mock_client)
        assert result["score"] is None
        assert result["error"] is True


class TestKnnSemanticGate:
    """Tests for the knn_max_similarity helper."""

    def test_empty_anchors_returns_zero(self):
        """knn_max_similarity with empty anchors returns (0.0, None, 0.0)."""
        result = knn_max_similarity([1.0, 0.0, 0.0], [])
        assert result == (0.0, None, 0.0)

    def test_none_embedding_returns_zero(self):
        """knn_max_similarity with None paper_embedding returns (0.0, None, 0.0)."""
        anchors = [{"paper_id": "a", "embedding": [1.0, 0.0], "weight": 1.0}]
        result = knn_max_similarity(None, anchors)
        assert result == (0.0, None, 0.0)

    def test_single_anchor_weight_1(self):
        """With weight=1.0, returns cosine similarity."""
        # Identical vectors → cosine sim = 1.0
        emb = [1.0, 0.0, 0.0]
        anchors = [{"paper_id": "a1", "embedding": [1.0, 0.0, 0.0], "weight": 1.0}]
        sim, pid, weight = knn_max_similarity(emb, anchors)
        assert abs(sim - 1.0) < 1e-6
        assert pid == "a1"
        assert weight == 1.0

    def test_weight_2_doubles_similarity(self):
        """With weight=2.0, returns 2× cosine similarity."""
        emb = [1.0, 0.0, 0.0]
        anchors = [{"paper_id": "a1", "embedding": [1.0, 0.0, 0.0], "weight": 2.0}]
        sim, pid, weight = knn_max_similarity(emb, anchors)
        assert abs(sim - 2.0) < 1e-6

    def test_effective_score_boundary(self):
        """positive sim 0.6, negative sim 0.5, λ=0.5 → effective = 0.35."""
        # Use normalized vectors for predictable cosine values
        # We'll set up vectors to get specific cosine similarities
        import math
        # Create a paper embedding and two anchors with specific similarities
        paper_emb = [1.0, 0.0]

        # Positive anchor: cosine sim = 0.6 → need anchor_emb such that
        # dot(paper_emb, anchor_emb) = 0.6 (assuming unit vectors)
        pos_anchor = [{"paper_id": "pos", "embedding": [0.6, math.sqrt(1 - 0.36)], "weight": 1.0}]
        neg_anchor = [{"paper_id": "neg", "embedding": [0.5, math.sqrt(1 - 0.25)], "weight": 1.0}]

        max_pos, _, _ = knn_max_similarity(paper_emb, pos_anchor)
        max_neg, _, _ = knn_max_similarity(paper_emb, neg_anchor)

        assert abs(max_pos - 0.6) < 1e-6
        assert abs(max_neg - 0.5) < 1e-6

        lam = 0.5
        effective = max_pos - lam * max_neg
        assert abs(effective - 0.35) < 1e-6

        # With threshold=0.35, passes
        assert effective >= 0.35
        # With threshold=0.36, rejects
        assert effective < 0.36

    def test_picks_best_anchor(self):
        """With multiple anchors, returns the one with highest weighted similarity."""
        paper_emb = [1.0, 0.0]
        anchors = [
            {"paper_id": "far", "embedding": [0.0, 1.0], "weight": 1.0},  # sim ≈ 0
            {"paper_id": "close", "embedding": [1.0, 0.0], "weight": 1.0},  # sim = 1
        ]
        sim, pid, _ = knn_max_similarity(paper_emb, anchors)
        assert pid == "close"
        assert abs(sim - 1.0) < 1e-6
