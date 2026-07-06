"""Test Phase 2 — generate_report structure."""
import pytest
from backend.core.reporting import generate_report


class TestExplainabilityReport:
    """generate_report harus return dict dengan field yang sesuai."""

    def test_required_fields_present(self):
        """generate_report returns dict with legacy and new fields."""
        sample = {
            "sentimen_agregat": {"A": [0.5, 0.6], "B": [-0.3, -0.4]},
            "aktor_analisis": {
                "aktor_kunci": [{"nama": "A", "sikap_label": "mendukung"}],
            },
            "prediksi": {"Konsensus": 50, "Polarisasi": 30, "Status Quo": 20},
            "events": [],
            "prediction_confidence": 0.7,
            "prediction_reasoning": "Test reasoning",
            "ronde_detail": [
                {"ronde": 1, "agen": [
                    {"nama": "A", "pendapat": "Saya setuju", "sentimen": {"label": "positif", "skor": 0.5}},
                    {"nama": "B", "pendapat": "Saya menolak", "sentimen": {"label": "negatif", "skor": -0.3}},
                ]},
            ],
        }
        result = generate_report(sample)
        assert isinstance(result, dict)
        assert "ringkasan" in result
        assert "penyebab" in result
        assert "konflik" in result
        assert "keyakinan" in result
        assert "disclaimer" in result
        assert "phenomenon_summary" in result
        assert "group_breakdown" in result
        assert "confidence" in result

    def test_empty_data_returns_defaults(self):
        """generate_report with minimal input should not crash."""
        result = generate_report({
            "sentimen_agregat": {},
            "aktor_analisis": {},
            "prediksi": {},
            "events": [],
        })
        assert isinstance(result, dict)
        assert "ringkasan" in result

    def test_phenomenon_summary_present(self):
        """phenomenon_summary field should exist even with minimal data."""
        result = generate_report({
            "sentimen_agregat": {"A": [0.5]},
            "aktor_analisis": {"aktor_kunci": []},
            "prediksi": {"Konsensus": 50, "Polarisasi": 30, "Status Quo": 20},
            "events": [],
            "prediction_confidence": 0.7,
            "prediction_reasoning": "OK",
            "ronde_detail": [],
        })
        assert "phenomenon_summary" in result
        assert "group_breakdown" in result
        assert "confidence" in result
