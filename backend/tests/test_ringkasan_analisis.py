"""Tes pembersihan JSON dari keluaran analisis dan penyusunan ringkasan kalimat."""

from __future__ import annotations

import pytest


AGENTS = [
    {"nama": "A", "pengaruh": 0.5},
    {"nama": "B", "pengaruh": 0.5},
]
SENTIMEN = {"A": [0.5], "B": [-0.5]}


def _jalankan(monkeypatch, keluaran_llm):
    import backend.simulation as simulation

    monkeypatch.setattr(simulation, "call_llm", lambda *a, **k: keluaran_llm)
    monkeypatch.setattr(simulation, "call_llm_json", lambda *a, **k: {})
    return simulation._analisis_dan_aktor(
        "Topik uji", "log diskusi", AGENTS, SENTIMEN
    )


def test_analisis_buang_json_code_fence(monkeypatch):
    keluaran = (
        "Pembuka analisis.\n"
        "```json\n"
        '{"A": "bisa berubah jika data baru"}\n'
        "```\n"
        "Penutup."
    )
    analisis, _, struktur = _jalankan(monkeypatch, keluaran)
    assert "{" not in analisis
    assert '":' not in analisis
    assert "Pembuka analisis." in analisis
    assert struktur == {"A": "bisa berubah jika data baru"}


def test_analisis_tanpa_json(monkeypatch):
    analisis, _, struktur = _jalankan(monkeypatch, "Pembuka analisis tanpa JSON.")
    assert "{" not in analisis
    assert '":' not in analisis
    assert "Pembuka analisis tanpa JSON." in analisis
    assert struktur == {}


def test_analisis_json_rusak_tidak_tampil(monkeypatch):
    keluaran = 'Pembuka.\n{"A": "rusak\nPenutup.'
    analisis, _, struktur = _jalankan(monkeypatch, keluaran)
    assert "{" not in analisis
    assert '":' not in analisis
    assert "Pembuka." in analisis
    assert struktur == {}


def test_ringkasan_kalimat_format_dan_fallback():
    import backend.simulation as simulation

    hasil = simulation._susun_ringkasan_kalimat(
        {"A": [0.5], "B": [-0.5], "C": [0.0]},
        {"A": "bisa berubah jika data baru", "B": ""},
    )
    assert hasil[0] == (
        "A bersikap mendukung (skor akhir 0.50); bisa berubah jika data baru."
    )
    assert "syarat berubah tidak tersedia." in hasil[1]
    assert "syarat berubah tidak tersedia." in hasil[2]
