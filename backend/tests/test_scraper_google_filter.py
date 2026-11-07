"""Test jalur Google News: stemming, aturan per-query, dan status sumber.

Semua test memakai data fixture; tidak ada request jaringan.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend import scraper

TOPIK = "Pemerintah merencanakan pembaruan dan kenaikan batas PTKP yang akan berlaku 2027"
QUERIES = ["PTKP 2027", "kenaikan PTKP 2027"]


def _rfc2822(days_ago: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _artikel(judul: str, query: str, domain: str, days_ago: int = 1) -> dict:
    return {
        "id": f"{domain}|{judul}",
        "judul": judul,
        "ringkasan": judul,
        "link": f"https://{domain}/berita",
        "sumber": "google_news_search",
        "tanggal": _rfc2822(days_ago),
        "tipe": "berita",
        "source_url": f"https://{domain}",
        "query_origin": query,
    }


@pytest.fixture
def fixture_google(monkeypatch):
    """Ganti sumber jaringan dengan daftar artikel fixture."""
    items = [
        # Lolos: query 3 kata, cocok naik + ptkp (2 >= ceil(3/2))
        _artikel("Pemerintah naikkan batas PTKP jadi Rp6 juta", "kenaikan PTKP 2027", "kompas.com"),
        # Lolos: query 2 kata, cukup anchor
        _artikel("PTKP naik tahun depan", "PTKP 2027", "detik.com"),
        # Ditolak: tidak ada anchor
        _artikel("Pendaftaran gigi gratis dibuka", "kenaikan PTKP 2027", "cnbcindonesia.com"),
        # Ditolak: hanya 1 dari 3 kata kunci query
        _artikel("PTKP saja tanpa kata lain", "kenaikan PTKP 2027", "tempo.co"),
        # Lolos: query 2 kata, cukup anchor
        _artikel("Batas PTKP baru", "PTKP 2027", "antaranews.com"),
    ]
    monkeypatch.setattr(scraper, "RSS_SOURCES", [])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: list(QUERIES))
    monkeypatch.setattr(scraper, "fetch_google_news_search", lambda query, errors=None: [dict(a) for a in items])
    return items


def test_stem_naik_keluarga_sama():
    kata = ["naik", "kenaikan", "menaikkan", "dinaikkan", "dinaikan", "menaikan"]
    akar = {scraper._stem_id(k) for k in kata}
    assert akar == {"naik"}


def test_filter_per_query(fixture_google, capsys):
    hasil = scraper.fetch_berita(TOPIK)
    judul = {a["judul"] for a in hasil["articles"]}

    assert "Pemerintah naikkan batas PTKP jadi Rp6 juta" in judul
    assert "PTKP naik tahun depan" in judul
    assert "Batas PTKP baru" in judul
    assert "Pendaftaran gigi gratis dibuka" not in judul
    assert "PTKP saja tanpa kata lain" not in judul

    log = capsys.readouterr().out
    assert "google_news removed (no anchor)" in log
    assert "kw 1/2" in log
    assert hasil["sumber_status"] == "ok"


def test_hasil_fetch_berita_json_dumps(fixture_google):
    hasil = scraper.fetch_berita(TOPIK)
    dumped = json.dumps(hasil, ensure_ascii=False)
    assert isinstance(dumped, str)

    for art in hasil["articles"]:
        assert "_pub_dt" not in art
        assert isinstance(art.get("tanggal_iso"), str)
        # tanggal_iso harus string ISO yang bisa di-parse balik
        if art["tanggal_iso"]:
            datetime.fromisoformat(art["tanggal_iso"])


def test_sumber_status_gagal(monkeypatch):
    monkeypatch.setattr(scraper, "RSS_SOURCES", [{"nama": "X", "url": "http://x.invalid", "bahasa": "id"}])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: [])

    def fake_fetch(url, headers=None, timeout=30, errors=None):
        if errors is not None:
            errors.append(f"{url}: URLError: boom")
        return None

    monkeypatch.setattr(scraper, "_fetch", fake_fetch)
    hasil = scraper.fetch_berita("topik apa saja")

    assert hasil["sumber_status"] == "gagal"
    assert "URLError" in hasil["sumber_pesan"]
    assert hasil["articles"] == []


def test_sumber_status_kosong(monkeypatch):
    monkeypatch.setattr(scraper, "RSS_SOURCES", [{"nama": "X", "url": "http://x.invalid", "bahasa": "id"}])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: [])
    monkeypatch.setattr(scraper, "_fetch", lambda url, headers=None, timeout=30, errors=None: None)

    hasil = scraper.fetch_berita("topik apa saja")

    assert hasil["sumber_status"] == "kosong"
    assert hasil["articles"] == []
