"""Tests for Phase 2 Chunk 2: title-only negative keyword filter."""

from app.services.ranking.negative_filter import paper_rejected_by_title


class TestPaperRejectedByTitle:
    def test_rejects_matching_title(self):
        result = paper_rejected_by_title(
            {"title": "Tumor heterogeneity in advanced cancer patients"},
            ["tumor"],
        )
        assert result == (True, "tumor")

    def test_passes_non_matching_title(self):
        result = paper_rejected_by_title(
            {"title": "Battery modelling with ML"},
            ["tumor"],
        )
        assert result == (False, None)

    def test_title_only_ignores_abstract(self):
        result = paper_rejected_by_title(
            {"title": "Battery modelling", "abstract": "We study tumors."},
            ["tumor"],
        )
        assert result == (False, None)

    def test_empty_keywords_always_passes(self):
        result = paper_rejected_by_title(
            {"title": "Anything at all"},
            [],
        )
        assert result == (False, None)

    def test_case_insensitive(self):
        result = paper_rejected_by_title(
            {"title": "TUMOR ANALYSIS IN MICE"},
            ["tumor"],
        )
        assert result == (True, "tumor")

    def test_short_keyword_word_boundary(self):
        """Short keywords (<=3 chars) use strict word boundaries."""
        # "PCR" should match "PCR analysis"
        result = paper_rejected_by_title(
            {"title": "PCR analysis of gene expression"},
            ["PCR"],
        )
        assert result == (True, "pcr")

        # "PCR" should NOT match "PCRB tech"
        result = paper_rejected_by_title(
            {"title": "PCRB tech for sequencing"},
            ["PCR"],
        )
        assert result == (False, None)

    def test_long_keyword_prefix_matching(self):
        """Longer keywords use prefix matching to catch suffixed forms."""
        # "crystallisation" should match "crystallisation method"
        result = paper_rejected_by_title(
            {"title": "A crystallisation method for proteins"},
            ["crystallisation"],
        )
        assert result == (True, "crystallisation")

        # Should also match suffixed forms like "crystallisation-based"
        result = paper_rejected_by_title(
            {"title": "Novel crystallisation-based procedure"},
            ["crystallisation"],
        )
        assert result == (True, "crystallisation")

    def test_empty_title_passes(self):
        result = paper_rejected_by_title(
            {"title": ""},
            ["tumor"],
        )
        assert result == (False, None)

    def test_none_title_passes(self):
        result = paper_rejected_by_title(
            {"title": None},
            ["tumor"],
        )
        assert result == (False, None)

    def test_multi_word_keyword(self):
        """Multi-word keywords like 'clinical trial' should match."""
        result = paper_rejected_by_title(
            {"title": "Results from a clinical trial of immunotherapy"},
            ["clinical trial"],
        )
        assert result == (True, "clinical trial")

    def test_multiple_keywords_first_match(self):
        """Returns the first matching keyword."""
        result = paper_rejected_by_title(
            {"title": "Cancer antibody therapy"},
            ["tumor", "cancer", "antibody"],
        )
        assert result[0] is True
        assert result[1] in ("cancer", "antibody")
