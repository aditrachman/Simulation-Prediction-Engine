"""Tes untuk FAKTA TERKINI: penyusunan blok, fallback, guard, system prompt."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from backend.simulation import (
    _susun_fakta_terkini,
    _bangun_fakta_terkini,
    _cek_angka_asing,
    _cek_salinan_judul,
    _hapus_kalimat_dengan_angka,
)

# ── Fixture: kelompok berita palsu ────────────────────────────────────────

def _kelompok_berita_palsu():
    """Kelompok berita seperti output _susun_briefing."""
    return [
        {
            "baris": "- Pemerintah Kaji Kenaikan PTKP 2027 (cnbcindonesia.com, 8 Nov 2026; dilaporkan 3 media)",
            "tanggal": "2026-11-08T00:00:00+00:00",
            "lama": False,
            "kritis": False,
        },
        {
            "baris": "- Airlangga Terapkan Penyesuaian PTKP Setelah Januari 2027 (kompas.com, 6 Nov 2026; dilaporkan 1 media)",
            "tanggal": "2026-11-06T00:00:00+00:00",
            "lama": False,
            "kritis": True,
        },
        {
            "baris": "- PTKP 2027 Direncanakan Naik, Pemerintah Masih Hitung Besaran (tempo.co, 5 Okt 2026; dilaporkan 1 media)",
            "tanggal": "2026-10-05T00:00:00+00:00",
            "lama": True,
            "kritis": False,
        },
        {
            "baris": "- PTKP Baru Dihitung Ulang, Besaran Belum Jelas (detik.com, 4 Okt 2026; dilaporkan 1 media)",
            "tanggal": "2026-10-04T00:00:00+00:00",
            "lama": True,
            "kritis": False,
        },
    ]


def _judul_berita_palsu():
    """Judul wakil dari kelompok berita palsu di atas."""
    return [
        "Pemerintah Kaji Kenaikan PTKP 2027",
        "Airlangga Terapkan Penyesuaian PTKP Setelah Januari 2027",
        "PTKP 2027 Direncanakan Naik, Pemerintah Masih Hitung Besaran",
        "PTKP Baru Dihitung Ulang, Besaran Belum Jelas",
    ]


# ── (a) blok FAKTA dari LLM palsu berisi klaim <= 20 kata ────────────────

@patch("backend.simulation.call_llm")
def test_fakta_terkini_llm_palsu_klaim_pendek(mock_call_llm):
    """LLM mengembalikan klaim pendek; hasil akhir tetap klaim tervalidasi."""
    # LLM output: 4 baris, nomor 2 punya "Januari" (non-topik), 3 punya "belum" (non-topik)
    mock_call_llm.return_value = (
        "[1] Pemerintah meninjau kenaikan PTKP 2027.\n"
        "[2] Airlangga akan menyesuaikan PTKP setelah Januari 2027.\n"
        "[3] Pemerintah menyiapkan PTKP baru namun belum ada kepastian waktu.\n"
        "[4] Pemerintah masih menghitung besaran PTKP baru."
    )

    topik = "Apakah kenaikan batas PTKP 2027 menguntungkan pekerja?"

    klaim = _susun_fakta_terkini(_judul_berita_palsu(), topik)

    assert klaim is not None
    assert 1 <= len(klaim) <= 4
    for k in klaim:
        assert k["klaim"].strip()
        assert len(k["klaim"].split()) <= 20, f"Klaim terlalu panjang: {k['klaim']}"
        assert 0 <= k["sumber_idx"] < 4


# ── (b) fallback ke judul sumber saat LLM gagal ───────────────────────────

def test_fakta_terkini_fallback_llm_gagal():
    """Saat call_llm raise exception, judul sumber dipakai sebagai klaim."""
    with patch("backend.simulation.call_llm", side_effect=RuntimeError("LLM down")):
        judul = _judul_berita_palsu()
        topik = "Topik uji"

        klaim = _susun_fakta_terkini(judul, topik)

        assert klaim is not None
        assert len(klaim) == 4
        for k in klaim:
            assert k["klaim"] in judul


def test_bangun_fakta_terkini_fallback_baris_judul():
    """_bangun_fakta_terkini memakai judul dari baris kelompok bila klaim kosong."""
    briefing_dipakai = {
        "teks": "Sumber: hanya judul...\n- Judul 1 (media1, 1 Nov 2026; dilaporkan 1 media)\n- Judul 2 (media2, 2 Nov 2026; dilaporkan 1 media)",
        "baris": [
            "Sumber: hanya judul...",
            "- Judul 1 (media1, 1 Nov 2026; dilaporkan 1 media)",
            "- Judul 2 (media2, 2 Nov 2026; dilaporkan 1 media)",
        ],
        "kelompok": [
            {"baris": "- Judul 1 (media1, 1 Nov 2026; dilaporkan 1 media)"},
            {"baris": "- Judul 2 (media2, 2 Nov 2026; dilaporkan 1 media)"},
        ],
        "fakta_terkini": {"teks": "", "klaim": [], "catatan_istilah": None, "briefing_guard": {}},
    }
    topik = "Topik uji"

    from backend.simulation import _bangun_fakta_terkini
    hasil = _bangun_fakta_terkini(briefing_dipakai, topik)

    assert "FAKTA TERKINI:" in hasil["teks"]
    assert "Judul 1" in hasil["teks"]
    assert "Judul 2" in hasil["teks"]
    assert "Pilih SATU fakta" in hasil["teks"]
    assert [k["klaim"] for k in hasil["klaim"]] == ["Judul 1", "Judul 2"]


# ── (c) penjaga angka: regenerasi lalu hapus kalimat ────────────────────

def test_cek_angka_asing():
    """Deteksi angka di alasan yang tidak ada di klaim/topik."""
    klaim = [
        {"nomor": 1, "klaim": "PTKP naik 2027, pajak turun 5 persen."},
    ]
    angka_boleh = {"5"}  # dari klaim
    alasan = "PTKP naik 2027, pajak turun 10 persen dan 5 persen."
    asing = _cek_angka_asing(alasan, angka_boleh)
    assert "10" in asing
    assert "5" not in asing


def test_hapus_kalimat_dengan_angka():
    """Hapus kalimat yang mengandung angka asing."""
    teks = "Klaim pertama. PTKP naik 2027 pajak 10 persen. Klaim ketiga."
    hasil = _hapus_kalimat_dengan_angka(teks, ["10"])
    assert "10" not in hasil
    assert "Klaim pertama" in hasil
    assert "Klaim ketiga" in hasil


# ── (d) penjaga salinan: >= 6 kata berurutan ────────────────────────────

def test_cek_salinan_judul_true():
    """Deteksi >= 6 kata berurutan sama dengan klaim."""
    klaim = [{"klaim": "Pemerintah meninjau kenaikan batas PTKP tahun 2027"}]
    alasan = "Pemerintah meninjau kenaikan batas PTKP tahun 2027 karena ini penting."
    assert _cek_salinan_judul(alasan, klaim) is True


def test_cek_salinan_judul_false():
    """< 6 kata tidak dianggap salinan."""
    klaim = [{"klaim": "Pemerintah meninjau kenaikan batas PTKP tahun 2027"}]
    alasan = "Pemerintah meninjau kenaikan PTKP."
    assert _cek_salinan_judul(alasan, klaim) is False


def test_cek_salinan_judul_kosong():
    """Klaim kosong tidak error."""
    assert _cek_salinan_judul("teks biasa", []) is False


# ── (e) system prompt memuat aturan baru, tidak lagi "tulis 'perlu data'" ─────

def test_system_prompt_aturan_baru():
    """System prompt mengandung aturan FAKTA TERKINI, tidak lagi 'tulis perlu data'."""
    import inspect
    import backend.simulation as sim

    # Check the actual prompt building logic source
    source = inspect.getsource(sim)
    assert "FAKTA TERKINI memuat jawabannya" in source
    assert "tidak ada data" in source  # part of forbidden phrases
    assert "tidak ada bukti" in source
    assert "perlu data" in source  # as forbidden phrase
    # Old rule should be gone
    assert "Jika butuh data, tulis 'perlu data'" not in source


# ── Kasus bahan kosong: konteks_real tanpa berita ───────────────────────

def test_casestudy_builder_bahan_kosong():
    """Kasus bahan kosong: tampil 'Sumber: tanpa artikel berita; briefing terbatas.'"""
    from backend.services.casestudy_builder import build_computed

    run = {
        "topik": "Topik uji",
        "kategori": "Umum",
        "konteks_real": {"berita": [], "sumber_status": "kosong"},
        "briefing_dipakai": {"fakta_terkini": {"klaim": []}},
        "kualitas": {"status": "ok", "fallback_count": 0, "total_giliran": 10},
        "ronde_detail": [
            {"ronde": 1, "agen": [
                {"nama": "A", "pendapat": "Pendapat A", "sentimen": {"label": "positif", "skor": 0.5}, "pengaruh": 0.5, "angka_klaim": []},
                {"nama": "B", "pendapat": "Pendapat B", "sentimen": {"label": "negatif", "skor": -0.5}, "pengaruh": 0.5, "angka_klaim": []},
            ]}
        ],
        "agents": [
            {"nama": "A", "pengaruh": 0.5},
            {"nama": "B", "pengaruh": 0.5},
        ],
        "tanggal": "1 Jan 2026",
    }

    out = build_computed(run)
    situasi = out["situasi"]
    bahan = situasi["bahan"]

    # Seharusnya ada fallback baris
    assert len(bahan) == 1
    assert "Sumber: tanpa artikel berita; briefing terbatas." in bahan[0]


def test_narrator_bahan_kosong():
    """Narrator dengan bahan kosong (minItems=1): minItems=1 di schema, tapi fallback menangani."""
    # Schema sudah minItems=1, tapi narrator fallback akan pakai computed.bahan
    # Jika bahan kosong, fallback tetap bisa generate (minItems=1 di schema untuk LLM output,
    # tapi fallback bypass LLM)
    from backend.services.narrator import _fallback_narrative, generate_narrative
    from backend.services.casestudy_builder import build_computed

    run = {
        "topik": "Topik uji",
        "kategori": "Umum",
        "konteks_real": {"berita": [], "sumber_status": "kosong"},
        "briefing_dipakai": {"fakta_terkini": {"klaim": []}},
        "kualitas": {"status": "ok", "fallback_count": 0, "total_giliran": 10},
        "ronde_detail": [
            {"ronde": 1, "agen": [
                {"nama": "A", "pendapat": "Pendapat A", "sentimen": {"label": "positif", "skor": 0.5}, "pengaruh": 0.5, "angka_klaim": []},
                {"nama": "B", "pendapat": "Pendapat B", "sentimen": {"label": "negatif", "skor": -0.5}, "pengaruh": 0.5, "angka_klaim": []},
            ]}
        ],
        "agents": [
            {"nama": "A", "pengaruh": 0.5},
            {"nama": "B", "pengaruh": 0.5},
        ],
        "tanggal": "1 Jan 2026",
    }

    computed = build_computed(run)
    # fallback narator tidak butuh bahan dari LLM
    narrative = _fallback_narrative(computed)
    assert "situasi" in narrative
    assert "bahan" in narrative["situasi"]
    # fallback bisa handle bahan kosong


# Helper untuk build_system_prompt test
def _build_system_prompt_for_test(agen, ronde_ke=1, skor_ronde_lalu=None):
    """Replikasi logika system prompt untuk test."""
    from backend.simulation import _label_sentimen
    nama = agen["nama"]
    role_singkat = agen.get("role", "").split(". ")[0]
    # ... simplified
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])