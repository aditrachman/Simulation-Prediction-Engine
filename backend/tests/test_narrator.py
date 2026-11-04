"""Test narator CaseStudy (FASE 7).

Semua tes memakai mock di level llm_guard.chat.
"""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.services.narrator import (
    generate_narrative,
    _validate_narrative,
    _fallback_narrative,
    _build_narrator_prompt,
)
from backend.services.casestudy_builder import build_computed


FIXTURE = Path("backend/tests/fixtures/run_mbg_synthetic.json")


@pytest.fixture
def run_data():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def computed(run_data):
    return build_computed(run_data)


# ── Valid JSON response untuk mock ───────────────────────────────────────
VALID_NARRATIVE = {
    "vonis": "Mayoritas peserta menolak anggapan bahwa MBG sudah tepat sasaran.",
    "alasan": [
        "Angka kepuasan 72,8% tidak mencerminkan realita distribusi.",
        "Data konflik 78% naik vs turun menunjukkan pelaporan tidak standar.",
        "Butuh transparansi distribusi dan audit independen."
    ],
    "situasi": {
        "pemicu": {"angka": "72,8%", "teks": "Survei 72,8% puas tapi pertanyaan distribusi muncul."},
        "bahan": ["Keracunan berulang", "Keluarga miskin terpinggirkan", "Kepuasan bukan bukti tepat sasaran"]
    },
    "kubu_catatan": {
        "tolak": "Kepuasan survei bukan bukti program tepat sasaran.",
        "netral": "Terbuka bukti tambahan, data 78% kontradiktif.",
        "dukung": "Manfaat terlihat di posyandu."
    },
    "ronde": [
        {"no": 1, "judul": "Arti angka 72,8%", "ringkas": "Hampir semua mempertanyakan metodologi survei kepuasan."},
        {"no": 2, "judul": "Isu bergeser distribusi", "ringkas": "Debat pindah ke siapa menerima bantuan di desa vs kota."},
        {"no": 3, "judul": "Bukti lapangan kontradiktif", "ringkas": "Data 78% naik vs turun, tafsir berbeda per agen."}
    ],
    "skenario": [
        {"jika": "Jika pemerintah buka data distribusi", "maka": "Maka Oposisi Kritis jadi moderat", "dasar_agen": "Oposisi Kritis"},
        {"jika": "Jika audit keracunan menurun", "maka": "Maka Pengusaha/UMKM beralih netral", "dasar_agen": "Pengusaha/UMKM"},
        {"jika": "Jika data lapangan membaik", "maka": "Maka Jurnalis/Media ubah sikap", "dasar_agen": "Jurnalis/Media"},
        {"jika": "Jika anak terpencil terpinggirkan", "maka": "Maka protes kubu kritis naik", "dasar_agen": "Mahasiswa"}
    ]
}


class TestValidator:
    def test_valid_narrative_lolos(self, computed, run_data):
        errors = _validate_narrative(VALID_NARRATIVE, computed, run_data)
        assert errors == []

    def test_vonis_tidak_sesuai_distribusi(self, computed, run_data):
        bad = copy.deepcopy(VALID_NARRATIVE)
        bad["vonis"] = "Mayoritas peserta mendukung program MBG."
        errors = _validate_narrative(bad, computed, run_data)
        assert any("Vonis tidak sesuai" in e for e in errors)

    def test_kata_polarisasi_dilarang(self, computed, run_data):
        bad = copy.deepcopy(VALID_NARRATIVE)
        bad["vonis"] = "Polarisasi peserta tinggi."
        errors = _validate_narrative(bad, computed, run_data)
        assert any("polarisasi" in e for e in errors)

    def test_persentase_baru_dilarang(self, computed, run_data):
        bad = copy.deepcopy(VALID_NARRATIVE)
        bad["alasan"][0] = "90% peserta menolak."  # 90% tidak ada di data
        errors = _validate_narrative(bad, computed, run_data)
        assert any("persentase" in e for e in errors)

    def test_alasan_bukan_3_item(self, computed, run_data):
        bad = copy.deepcopy(VALID_NARRATIVE)
        bad["alasan"] = ["satu", "dua"]
        errors = _validate_narrative(bad, computed, run_data)
        assert any("3 string" in e for e in errors)

    def test_skenario_dasar_agen_tidak_kenal(self, computed, run_data):
        bad = copy.deepcopy(VALID_NARRATIVE)
        bad["skenario"][0]["dasar_agen"] = "Agen Tidak Ada"
        errors = _validate_narrative(bad, computed, run_data)
        assert any("dasar_agen tidak dikenal" in e for e in errors)

    def test_skenario_format_salah(self, computed, run_data):
        bad = copy.deepcopy(VALID_NARRATIVE)
        bad["skenario"][0] = {"jika": "kalau A", "maka": "maka B", "dasar_agen": "Mahasiswa"}
        errors = _validate_narrative(bad, computed, run_data)
        assert any("format salah" in e for e in errors)

    def test_ronde_judul_terlalu_panjang(self, computed, run_data):
        bad = copy.deepcopy(VALID_NARRATIVE)
        bad["ronde"][0]["judul"] = "Ini judul yang sangat panjang sekali melebihi delapan kata"
        errors = _validate_narrative(bad, computed, run_data)
        assert any("judul > 8 kata" in e for e in errors)

    def test_runde_ringkas_terlalu_panjang(self, computed, run_data):
        bad = copy.deepcopy(VALID_NARRATIVE)
        bad["ronde"][0]["ringkas"] = " ".join(["kata"] * 41)
        errors = _validate_narrative(bad, computed, run_data)
        assert any("ringkas > 40 kata" in e for e in errors)


class TestFallbackNarrative:
    def test_fallback_structure_valid(self, computed, run_data):
        fb = _fallback_narrative(computed)
        assert "vonis" in fb
        assert "alasan" in fb
        assert len(fb["alasan"]) == 3
        assert "situasi" in fb
        assert "kubu_catatan" in fb
        assert set(fb["kubu_catatan"].keys()) == {"tolak", "netral", "dukung"}
        assert "ronde" in fb
        assert len(fb["ronde"]) == 3
        assert "skenario" in fb
        for s in fb["skenario"]:
            assert "dasar_agen" in s
            assert s["dasar_agen"] in {a["nama"] for a in run_data["agen"]}

    def test_fallback_lolos_validator(self, computed, run_data):
        fb = _fallback_narrative(computed)
        errors = _validate_narrative(fb, computed, run_data)
        assert errors == []


class TestPromptBuilder:
    def test_prompt_mengandung_data_kunci(self, computed, run_data):
        prompt = _build_narrator_prompt(computed, run_data)
        assert "72,8%" in prompt
        assert "Menolak: 8" in prompt  # distribusi di prompt
        assert "Oposisi Kritis" in prompt
        assert "titik balik" in prompt.lower()
        assert "Jika" in prompt and "maka" in prompt


class TestGenerateNarrative:
    def test_generate_narrative_sukses_pertama_kali(self, run_data, computed, monkeypatch):
        """Mock call_llm return valid narrative di percobaan pertama."""
        def mock_call_llm(system_prompt, user_prompt, **kwargs):
            return json.dumps(VALID_NARRATIVE)

        monkeypatch.setattr("backend.services.narrator.call_llm", mock_call_llm)

        result = generate_narrative(run_data, computed)
        assert result["narator_fallback"] is False
        assert result["vonis"] == VALID_NARRATIVE["vonis"]
        assert len(result["alasan"]) == 3

    def test_generate_narrative_retry_kedua_sukses(self, run_data, computed, monkeypatch):
        """Percobaan pertama gagal validasi, kedua sukses."""
        call_count = {"n": 0}

        def mock_call_llm(system_prompt, user_prompt, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                bad = copy.deepcopy(VALID_NARRATIVE)
                bad["vonis"] = "Semua peserta mendukung."
                return json.dumps(bad)
            return json.dumps(VALID_NARRATIVE)

        monkeypatch.setattr("backend.services.narrator.call_llm", mock_call_llm)

        result = generate_narrative(run_data, computed)
        assert result["narator_fallback"] is False
        assert call_count["n"] == 2

    def test_generate_narrative_fallback_kedua_gagal(self, run_data, computed, monkeypatch):
        """Kedua percobaan gagal → fallback template."""
        def mock_call_llm(system_prompt, user_prompt, **kwargs):
            raise RuntimeError("LLM error")

        monkeypatch.setattr("backend.services.narrator.call_llm", mock_call_llm)

        result = generate_narrative(run_data, computed)
        assert result["narator_fallback"] is True
        assert result["vonis"] == computed["hasil"]["vonis"]
        assert set(result["kubu_catatan"].keys()) == {"tolak", "netral", "dukung"}

    def test_generate_narrative_json_parse_error(self, run_data, computed, monkeypatch):
        """Response bukan valid JSON → fallback."""
        def mock_call_llm(system_prompt, user_prompt, **kwargs):
            return "bukan json {"

        monkeypatch.setattr("backend.services.narrator.call_llm", mock_call_llm)

        result = generate_narrative(run_data, computed)
        assert result["narator_fallback"] is True


class TestNarratorSmoke:
    """Smoke test dengan MOCK di level llm_guard.chat (bukan call_llm), supaya
    lapisan pemotong ikut teruji (pelajaran dari bug JSON terpotong)."""

    def test_mock_llm_guard_chat(self, run_data, computed, monkeypatch):
        """Mock llm_guard.chat langsung untuk test lapisan pemotong."""
        from backend.llm_guard import MockGroq, _install_mock_client, _restore_real_client

        _restore_real_client()
        mock = MockGroq({
            "openai/gpt-oss-20b": [(json.dumps(VALID_NARRATIVE), None)],
        })
        _install_mock_client(mock)

        try:
            result = generate_narrative(run_data, computed)
            assert result["narator_fallback"] is False
            assert result["vonis"] == VALID_NARRATIVE["vonis"]
            assert mock.call_count["openai/gpt-oss-20b"] == 1
        finally:
            _restore_real_client()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])