"""Test Phase 2 — ExplainabilityReport structure."""

import pytest
from backend.core.reporting import ExplainabilityReport, generate_report


class TestExplainabilityReport:
    """ExplainabilityReport dataclass — harus menjawab 6 pertanyaan."""

    def test_dataclass_has_required_fields(self):
        report = ExplainabilityReport(
            skenario="Polarisasi",
            skenario_probability={"Konsensus": 25, "Polarisasi": 52, "Status Quo": 23},
            skenario_definition="",
            phenomenon_summary="Test summary",
        )
        assert report.skenario == "Polarisasi"
        assert report.phenomenon_summary == "Test summary"
        assert report.to_dict() is not None

    def test_to_dict_includes_legacy_fields(self):
        """Backward compat: legacy fields untuk frontend existing."""
        report = ExplainabilityReport(
            skenario="Konsensus",
            skenario_probability={"Konsensus": 65, "Polarisasi": 15, "Status Quo": 20},
            skenario_definition="",
            phenomenon_summary="Konsensus terdeteksi",
        )
        d = report.to_dict()
        assert "ringkasan" in d
        assert "penyebab" in d
        assert "konflik" in d
        assert "keyakinan" in d
        assert "disclaimer" in d

    def test_to_dict_has_new_fields(self):
        report = ExplainabilityReport(
            skenario="Konsensus",
            skenario_probability={"Konsensus": 65, "Polarisasi": 15, "Status Quo": 20},
            skenario_definition="",
            phenomenon_summary="Test",
            group_breakdown=[{"nama": "A", "final_stance": "mendukung", "score": 0.5}],
            key_driver="A",
            key_driver_impact="Sangat berpengaruh",
            swing_voters=["B"],
            main_conflict="A vs B",
            confidence={"score": 0.7, "label": "tinggi", "reason": "OK"},
            limitations=["Test limitation"],
        )
        d = report.to_dict()
        assert d["phenomenon_summary"] == "Test"
        assert d["key_driver"] == "A"
        assert len(d["swing_voters"]) == 1
        assert d["confidence"]["score"] == 0.7
        assert len(d["limitations"]) == 1

    def test_generate_report_returns_dict(self):
        """Smoke test: generate_report dari dict hasil simulasi."""
        sample_hasil = {
            "topik": "Test",
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
        result = generate_report(sample_hasil)
        assert isinstance(result, dict)
        assert "ringkasan" in result
        assert "phenomenon_summary" in result
        assert "group_breakdown" in result
        assert "confidence" in result
