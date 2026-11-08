"""Tes penyusunan briefing agen dari daftar berita (tanpa jaringan/LLM)."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.simulation import _susun_briefing


def _artikel(judul: str, media: str, tanggal: str) -> dict:
    return {
        "judul": judul,
        "sumber": "google_news_search",
        "source_url": f"https://{media}",
        "tanggal_iso": tanggal,
    }


SEKARANG = datetime(2026, 11, 8, tzinfo=timezone.utc)


def test_duplikat_peristiwa_dikelompokkan():
    berita = [
        _artikel("PTKP naik 2027, kata Airlangga - Kompas.com", "kompas.com", "2026-11-07T00:00:00+00:00"),
        _artikel("PTKP naik 2027, kata Airlangga - Detik", "detik.com", "2026-11-07T00:00:00+00:00"),
        _artikel("Airlangga: PTKP naik 2027 - CNN", "cnnindonesia.com", "2026-11-06T00:00:00+00:00"),
        _artikel("PTKP naik 2027 kata Airlangga - Antara", "antaranews.com", "2026-11-06T00:00:00+00:00"),
        _artikel("PTKP naik 2027, kata Airlangga - Tempo", "tempo.co", "2026-11-05T00:00:00+00:00"),
        _artikel("Pemerintah kaji ambang batas PTKP", "pajakku.com", "2026-11-04T00:00:00+00:00"),
        _artikel("DJP hitung ulang batas penghasilan bebas pajak", "cnbcindonesia.com", "2026-11-03T00:00:00+00:00"),
        _artikel("Slip gaji pekerja berubah setelah pajak", "bisnis.com", "2026-11-02T00:00:00+00:00"),
        _artikel("Serikat buruh minta pajak upah diturunkan", "kompas.com", "2026-11-01T00:00:00+00:00"),
        _artikel("Ekonom UI nilai insentif pajak belum tepat", "tirto.id", "2026-10-31T00:00:00+00:00"),
        _artikel("Kemenkeu sosialisasi aturan pajak baru", "antaranews.com", "2026-10-30T00:00:00+00:00"),
        _artikel("Petani harap pajak hasil panen dihapus", "tempo.co", "2026-10-29T00:00:00+00:00"),
    ]
    info = _susun_briefing(berita, sekarang=SEKARANG)
    assert info["jumlah_kelompok"] < 12
    assert info["jumlah_baris"] <= 8


def test_briefing_memuat_item_lama_dan_kata_kritis():
    berita = [
        _artikel("PTKP 2027 resmi naik - Kompas.com", "kompas.com", "2026-11-07T00:00:00+00:00"),
        _artikel("Airlangga pastikan PTKP naik - Detik", "detik.com", "2026-11-06T00:00:00+00:00"),
        _artikel("Pajak upah dikurangi tahun depan - CNBC", "cnbcindonesia.com", "2026-11-05T00:00:00+00:00"),
        _artikel("Pengamat pajak kritik hitungan PTKP - Tirto", "tirto.id", "2026-09-01T00:00:00+00:00"),
    ]
    info = _susun_briefing(berita, sekarang=SEKARANG)
    lama = [b for b in info["baris"] if "1 Sep 2026" in b]
    assert lama, info["baris"]
    assert any(b.lower().startswith("- pengamat pajak kritik") for b in info["baris"])


def test_baris_utuh_dan_anggaran():
    berita = [
        _artikel(
            f"Judul peristiwa nomor {i} yang cukup panjang untuk menguji anggaran baris",
            f"media{i}.com",
            f"2026-11-0{i}T00:00:00+00:00" if i < 10 else "2026-11-10T00:00:00+00:00",
        )
        for i in range(1, 13)
    ]
    info = _susun_briefing(berita, sekarang=SEKARANG)
    assert len(info["teks"]) <= 900
    assert info["baris"][0] == "Sumber: hanya judul berita, isi artikel belum dibaca."
    for baris in info["baris"][1:]:
        assert baris.startswith("- ")
        assert baris.endswith(")")
        assert "media)" in baris


def test_berita_kosong():
    info = _susun_briefing([], sekarang=SEKARANG)
    assert info == {"teks": "", "baris": [], "jumlah_kelompok": 0, "jumlah_baris": 0}
    assert _susun_briefing(None)["teks"] == ""
