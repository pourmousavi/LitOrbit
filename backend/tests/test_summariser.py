import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.summariser import generate_summary, REQUIRED_KEYS


MOCK_SUMMARY = {
    "research_gap": "This paper addresses the lack of accurate battery degradation models.",
    "methodology": "The authors use a hybrid physics-informed neural network approach.",
    "key_findings": "1. 15% improvement in prediction accuracy. 2. Model generalises across chemistries.",
    "relevance_to_energy_group": "Directly relevant to BESS degradation forecasting research.",
    "suggested_action": "read_fully",
    "categories": ["battery", "degradation", "machine learning"],
}


class TestSummariser:
    @pytest.mark.asyncio
    async def test_summary_has_required_keys(self):
        """Assert summary JSON has all 6 required keys."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(MOCK_SUMMARY))]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        paper = {
            "title": "Battery Degradation Modelling with Neural Networks",
            "authors": ["A. Smith", "B. Jones"],
            "journal": "Applied Energy",
            "abstract": "We propose a novel approach to battery degradation prediction.",
        }

        result = await generate_summary(paper, client=mock_client)

        assert result is not None
        for key in REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_summary_categories_are_list(self):
        """Categories should be a list of strings."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(MOCK_SUMMARY))]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        paper = {
            "title": "Test Paper",
            "authors": ["Author"],
            "journal": "Test Journal",
            "abstract": "Test abstract.",
        }

        result = await generate_summary(paper, client=mock_client)
        assert isinstance(result["categories"], list)
        assert len(result["categories"]) >= 1

    @pytest.mark.asyncio
    async def test_summary_handles_markdown_code_blocks(self):
        """Summary should parse correctly even if wrapped in markdown code blocks."""
        wrapped = f"```json\n{json.dumps(MOCK_SUMMARY)}\n```"
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=wrapped)]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        paper = {
            "title": "Test Paper",
            "authors": ["Author"],
            "journal": "Test Journal",
            "abstract": "Test abstract.",
        }

        result = await generate_summary(paper, client=mock_client)
        assert result is not None
        assert "research_gap" in result

    @pytest.mark.asyncio
    async def test_summary_stored_in_db(self, db_session):
        """Run summariser on test paper, assert DB record updated."""
        import uuid
        from app.models.paper import Paper

        # Create a test paper in DB
        paper_id = uuid.uuid4()
        paper = Paper(
            id=paper_id,
            title="Battery SOH Prediction",
            authors=["Author A"],
            journal="Applied Energy",
            journal_source="scopus",
            abstract="A study on state of health.",
        )
        db_session.add(paper)
        await db_session.commit()

        # Generate summary (mocked)
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(MOCK_SUMMARY))]
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        summary = await generate_summary(
            {"title": paper.title, "authors": paper.authors, "journal": paper.journal, "abstract": paper.abstract},
            client=mock_client,
        )

        # Save to DB
        paper.summary = json.dumps(summary)
        paper.categories = summary["categories"]
        await db_session.commit()

        # Verify
        await db_session.refresh(paper)
        assert paper.summary is not None
        stored = json.loads(paper.summary)
        assert "research_gap" in stored
