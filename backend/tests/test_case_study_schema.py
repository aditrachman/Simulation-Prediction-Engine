"""Test validasi schema CaseStudy dengan template frontend."""

import json
from pathlib import Path

import pytest

from backend.core.case_study_schema import CaseStudy


class TestCaseStudySchema:
    def test_template_mbg_json_valid(self):
        """Template mbg.json harus lolos validasi CaseStudy."""
        template_path = Path("frontend/template/mbg.json")
        assert template_path.exists(), f"Template tidak ditemukan: {template_path}"

        with open(template_path, encoding="utf-8") as f:
            data = json.load(f)

        case = CaseStudy.model_validate(data)
        assert case.judul == "Apakah program MBG sudah tepat sasaran?"
        assert case.kategori == "Kebijakan publik"
        assert case.meta.peserta == 12
        assert case.meta.ronde == 3
        assert case.meta.sumber == 1
        assert case.hasil.distribusi.menolak == 8
        assert case.hasil.distribusi.netral == 3
        assert case.hasil.distribusi.mendukung == 1
        assert len(case.kubu) == 3
        assert len(case.ronde) == 3
        assert len(case.titikBalik) == 3
        assert len(case.buktiDiperdebatkan) == 3
        assert len(case.skenario) == 4
        assert case.whatif is not None

    def test_roundtrip_serialization(self):
        """Serialisasi by_alias=True lalu baca ulang identik."""
        template_path = Path("frontend/template/mbg.json")
        with open(template_path, encoding="utf-8") as f:
            data = json.load(f)

        case = CaseStudy.model_validate(data)
        json_out = case.model_dump(by_alias=True, exclude_none=True)
        case2 = CaseStudy.model_validate(json_out)

        assert case2.model_dump(by_alias=True, exclude_none=True) == json_out

    def test_optional_fields_can_be_missing(self):
        """Field optional (whatif, kualitas, narator_fallback) boleh tidak ada."""
        minimal = {
            "judul": "Test",
            "kategori": "Test",
            "meta": {"peserta": 4, "ronde": 2, "sumber": 0, "tanggal": "4 Nov 2026"},
            "keterbatasan": "Test",
            "hasil": {
                "vonis": "Test",
                "distribusi": {"menolak": 2, "netral": 1, "mendukung": 1},
                "alasan": [],
                "kepercayaan": {"level": "Rendah", "catatan": "Test"},
            },
            "situasi": {
                "pemicu": {"angka": "", "teks": "Test"},
                "bahan": [],
                "sumber": "Test",
            },
        }
        case = CaseStudy.model_validate(minimal)
        assert case.whatif is None
        assert case.kualitas is None
        assert case.narator_fallback is None