"""Tests for Phase 2 Chunk 3: abstract quality heuristic guard."""

from app.services.ranking.abstract_quality import abstract_quality


class TestAbstractQuality:
    def test_none_is_missing(self):
        assert abstract_quality(None) == ("missing", None)

    def test_empty_string_is_missing(self):
        assert abstract_quality("") == ("missing", None)

    def test_whitespace_only_is_missing(self):
        assert abstract_quality("   ") == ("missing", None)

    def test_short_abstract(self):
        label, reason = abstract_quality("Short.")
        assert label == "too_short"
        assert "6 chars" in reason

    def test_author_bios_detected(self):
        bio_text = (
            "Dr. Jane Smith received her Ph.D. in Chemistry from MIT in 2005. "
            "She is currently a distinguished professor at Stanford University. "
            "Her main research interests include catalysis and polymer science. "
            "She has published over 200 papers in leading journals and holds "
            "several patents in the field of green chemistry."
        )
        label, reason = abstract_quality(bio_text)
        assert label == "author_bios"
        assert "bio patterns matched" in reason

    def test_real_abstract_ok(self):
        real_abstract = (
            "We propose a novel method for predicting battery degradation using "
            "deep learning architectures. Our approach combines convolutional "
            "neural networks with attention mechanisms to capture temporal "
            "patterns in charge-discharge cycles. Results show that the proposed "
            "model outperforms existing state-of-the-art methods on three public "
            "benchmark datasets, achieving a mean absolute error reduction of 23%."
        )
        label, reason = abstract_quality(real_abstract)
        assert label == "ok"
        assert reason is None

    def test_toc_entry_no_methods_verbs(self):
        toc_text = (
            "A comprehensive overview of recent developments in energy storage "
            "materials and their applications across multiple industrial sectors "
            "including automotive transportation and grid-level storage solutions "
            "for renewable energy integration."
        )
        # 200+ chars, no methods verbs, under 500 chars
        assert len(toc_text) > 150
        assert len(toc_text) < 500
        label, reason = abstract_quality(toc_text)
        assert label == "no_methods_verbs"

    def test_single_bio_pattern_not_enough(self):
        mixed_text = (
            "He is currently a professor at the university department of "
            "electrical engineering. In this paper, we propose a systematic analysis of "
            "power system stability under varying load conditions with detailed "
            "simulation results demonstrating the effectiveness of the approach "
            "across multiple test scenarios."
        )
        assert len(mixed_text) > 150
        label, reason = abstract_quality(mixed_text)
        assert label == "ok"

    def test_long_abstract_without_verbs_passes(self):
        """Abstracts >500 chars without methods verbs still pass (possible but rare)."""
        long_text = "x " * 300  # 600 chars, no methods verbs
        label, reason = abstract_quality(long_text)
        assert label == "ok"
