import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.ranking.prefilter import prefilter_papers
from app.services.ranking.scorer import score_paper_for_user


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


class TestScorer:
    @pytest.mark.asyncio
    async def test_scorer_returns_valid_score(self):
        """Mock Claude response, assert score is float 0-10."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"score": 7.5, "reasoning": "Highly relevant to battery research."}')]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        paper = {"title": "Battery Degradation Analysis", "abstract": "A study on lithium-ion battery aging."}
        user = {"full_name": "Ali Pourmousavi", "interest_keywords": ["battery", "degradation"], "interest_categories": ["energy storage"]}

        result = await score_paper_for_user(paper, user, client=mock_client)

        assert isinstance(result["score"], float)
        assert 0.0 <= result["score"] <= 10.0
        assert result["score"] == 7.5

    @pytest.mark.asyncio
    async def test_scorer_stores_reasoning(self):
        """Assert reasoning string is stored."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"score": 8.0, "reasoning": "Directly addresses battery SOH estimation."}')]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        paper = {"title": "SOH Estimation Methods", "abstract": "State of health prediction."}
        user = {"full_name": "Test User", "interest_keywords": ["SOH"], "interest_categories": ["battery"]}

        result = await score_paper_for_user(paper, user, client=mock_client)

        assert result["reasoning"] == "Directly addresses battery SOH estimation."

    @pytest.mark.asyncio
    async def test_scorer_clamps_out_of_range(self):
        """Scores outside 0-10 should be clamped."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"score": 15.0, "reasoning": "Off the charts"}')]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        paper = {"title": "Test", "abstract": "Test"}
        user = {"full_name": "Test", "interest_keywords": [], "interest_categories": []}

        result = await score_paper_for_user(paper, user, client=mock_client)
        assert result["score"] == 10.0
