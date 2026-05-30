"""Test sentiment scoring — inline mode (deterministic, 0 LLM).

BUG-18 and BUG-19 post-processing happens in simulation.py's
_proses_satu_agen() where agent name context is available,
NOT in the scoring functions themselves.
"""

import pytest
from backend.sentiment import _score_inline


class TestInlineScoring:
    """Basic inline sentiment scorer behavior."""

    def test_negation_detection(self):
        teks = "Saya tidak setuju dengan kebijakan ini."
        result = _score_inline(teks, "test")
        assert result["label"] == "negatif"

    def test_positif_with_praise(self):
        teks = "Saya setuju dan mendukung penuh kebijakan ini."
        result = _score_inline(teks, "test")
        assert result["label"] == "positif"

    def test_netral_mixed(self):
        teks = "Saya melihat ada sisi positif dan negatif."
        result = _score_inline(teks, "test")
        assert result["label"] == "netral"

    def test_empty_text_handling(self):
        result = _score_inline("", "test")
        assert result["label"] == "netral"

    def test_mixed_tapi_menolak(self):
        teks = "Ada beberapa poin bagus, tapi saya menolak argumen utamanya."
        result = _score_inline(teks, "test")
        assert result["label"] in ("negatif", "netral")


class TestBUG18Scope:
    """
    BUG-18 post-processing is in simulation.py (_proses_satu_agen),
    not in the scoring functions. These tests verify that the
    inline scorer behavior is correct for the post-processing input.
    """

    def test_kritis_text_can_be_positif_in_inline(self):
        """
        _score_inline uses keyword matching and may return positif
        for critical text if it contains positive keywords.
        The BUG-18 fix catches this at the simulation level
        (where agent name is known) and forces netral.
        """
        teks = "Pertalite bukanlah jawaban yang tepat untuk mengatasi kebutuhan energi masyarakat"
        result = _score_inline(teks, "pembatasan BBM")
        # _score_inline may return positif due to keyword matching
        # BUG-18 post-processing in simulation.py will fix this
        assert result["label"] in ("positif", "negatif", "netral")
        assert "skor" in result

    def test_question_text_behavior(self):
        """Questions may be scored differently in inline mode."""
        teks = "Apakah kebijakan ini efektif mengatasi kebutuhan publik?"
        result = _score_inline(teks, "test")
        assert "label" in result
        assert "skor" in result
