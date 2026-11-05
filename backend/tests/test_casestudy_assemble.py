"""Test penyimpanan CaseStudy ke disk (tanpa mock _atomic_write)."""

import json

import pytest

from backend.services import casestudy_assemble


def test_save_case_study_writes_json_without_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(casestudy_assemble, "DATA_DIR", tmp_path)
    data = {
        "id": "mbg-uji",
        "judul": "Apakah program MBG tepat sasaran?",
        "meta": {"tanggal": "2026-11-05"},
    }

    casestudy_assemble.save_case_study("mbg-uji", data)

    target = tmp_path / "mbg-uji.json"
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == data
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_failure_leaves_no_tmp(tmp_path, monkeypatch):
    def gagal_dump(*args, **kwargs):
        raise TypeError("objek tidak bisa diserialisasi")

    monkeypatch.setattr(casestudy_assemble.json, "dump", gagal_dump)

    with pytest.raises(OSError, match="Gagal menulis"):
        casestudy_assemble._atomic_write(tmp_path / "gagal.json", {"a": 1})

    assert not (tmp_path / "gagal.tmp").exists()
