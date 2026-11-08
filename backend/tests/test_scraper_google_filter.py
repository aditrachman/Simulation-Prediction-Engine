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
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": list(QUERIES), "kata_wajib": ["ptkp"]})
    monkeypatch.setattr(scraper, "fetch_google_news_search", lambda query, errors=None: [dict(a) for a in items])
    return items


def test_stem_naik_keluarga_sama():
    kata = ["naik", "kenaikan", "menaikkan", "dinaikkan", "dinaikan", "menaikan"]
    akar = {scraper._stem_id(k) for k in kata}
    assert akar == {"naik"}


def test_filter_per_query(fixture_google, capsys):
    """Test filter dengan strong kata_wajib PTKP.
    
    Sekarang "PTKP saja tanpa kata lain" LOLOS karena "ptkp" adalah strong kata_wajib
    (singkatan 4 huruf), jadi bypass min_kw per query.
    """
    hasil = scraper.fetch_berita(TOPIK)
    judul = {a["judul"] for a in hasil["articles"]}

    # Yang harus lolos
    assert "Pemerintah naikkan batas PTKP jadi Rp6 juta" in judul
    assert "PTKP naik tahun depan" in judul
    assert "Batas PTKP baru" in judul
    # "PTKP saja tanpa kata lain" sekarang LOLOS karena strong kata_wajib "ptkp"
    assert "PTKP saja tanpa kata lain" in judul
    
    # Yang harus ditolak
    assert "Pendaftaran gigi gratis dibuka" not in judul

    log = capsys.readouterr().out
    assert "google_news removed (no kata_wajib)" in log
    # "kw 1/2" tidak muncul lagi untuk item yang lolos karena strong kata_wajib bypass
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
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": [], "kata_wajib": []})

    def fake_fetch(url, headers=None, timeout=30, errors=None):
        if errors is not None:
            errors.append(f"{url}: URLError: boom")
        return None

    monkeypatch.setattr(scraper, "_fetch", fake_fetch)
    hasil = scraper.fetch_berita("topik apa saja")

    assert hasil["sumber_status"] == "gagal"
    assert "URLError" in hasil["sumber_pesan"]
    assert hasil["sumber_peringatan"] == ["x.invalid: URLError"]
    assert hasil["articles"] == []


def test_sumber_status_kosong(monkeypatch):
    monkeypatch.setattr(scraper, "RSS_SOURCES", [{"nama": "X", "url": "http://x.invalid", "bahasa": "id"}])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": [], "kata_wajib": []})
    monkeypatch.setattr(scraper, "_fetch", lambda url, headers=None, timeout=30, errors=None: None)

    hasil = scraper.fetch_berita("topik apa saja")

    assert hasil["sumber_status"] == "kosong"
    assert hasil["sumber_peringatan"] == []
    assert hasil["articles"] == []


def test_ok_walau_ada_sumber_gagal(monkeypatch):
    monkeypatch.setattr(scraper, "RSS_SOURCES", [{"nama": "X", "url": "http://x.invalid", "bahasa": "id"}])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": list(QUERIES), "kata_wajib": ["ptkp"]})
    monkeypatch.setattr(
        scraper, "fetch_google_news_search",
        lambda query, errors=None: [_artikel("PTKP naik tahun depan", query, "detik.com")],
    )

    def fake_fetch(url, headers=None, timeout=30, errors=None):
        if errors is not None:
            errors.append(f"{url}: URLError: boom")
        return None

    monkeypatch.setattr(scraper, "_fetch", fake_fetch)
    hasil = scraper.fetch_berita(TOPIK)

    assert hasil["sumber_status"] == "sedikit"
    assert hasil["sumber_peringatan"] == ["x.invalid: URLError"]
    assert "Hanya 1 artikel lolos filter" in hasil["sumber_pesan"]
    assert hasil["articles"]


def test_sumber_disabled_dilewati(monkeypatch, capsys):
    dipanggil = []
    monkeypatch.setattr(scraper, "RSS_SOURCES", [
        {"nama": "Tempo", "url": "https://rss.tempo.co/nasional", "bahasa": "id", "enabled": False},
    ])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": [], "kata_wajib": []})
    monkeypatch.setattr(scraper, "_fetch", lambda *a, **k: dipanggil.append(1))

    scraper.fetch_berita("topik apa saja")

    assert dipanggil == []
    assert "skip_disabled" in capsys.readouterr().out


# ===== NEW TESTS: Kata Wajib Alternatives (Hak Cipta) =====

TOPIK_HAK_CIPTA = "kami Pemerintah menggratiskan biaya layanan pendaftaran untuk 19 jenis hak cipta berdasarkan usulan dari masyarakat"
# Kata wajib disesuaikan agar stem-nya cocok dengan judul fixture
# "hak cipta" -> hak + cipta
# "hak pencipta" -> hak + ncipta (pencipta -> ncipta setelah stem pe-)
# "pencatatan ciptaan" -> ncatat + cipta
# "kekayaan intelektual" -> kekayaan + intelektual
KATA_WAJIB_HAK_CIPTA = ["hak cipta", "hak pencipta", "pencatatan ciptaan", "kekayaan intelektual"]
QUERIES_HAK_CIPTA = ["pendaftaran hak cipta gratis", "PNBP hak cipta 19 jenis", "Kemenkum hak cipta gratis"]


@pytest.fixture
def fixture_hak_cipta(monkeypatch):
    """Fixture untuk topik hak cipta dengan kasus positif dan negatif."""
    items = [
        # HARUS LOLOS - positif
        _artikel("Pendaftaran Hak Cipta Lagu Gratis Mulai 1 Agustus 2026", "pendaftaran hak cipta gratis", "tempo.co"),
        _artikel("Sah! Tarif PNBP Daftar Merek Naik, Hak Cipta Lagu Gratis", "PNBP hak cipta 19 jenis", "cnbcindonesia.com"),
        _artikel("Pengamat: Pencatatan hak cipta gratis perlu diikuti pembenahan royalti", "PNBP hak cipta 19 jenis", "antaranews.com"),
        _artikel("Jangan Berhenti di Sertifikat Gratis, Hak Ekonomi Pencipta Harus Dilindungi", "Kemenkum hak cipta gratis", "kompas.com"),
        # HARUS DITOLAK - negatif
        _artikel("Rekrutmen Sekolah Rakyat Berdasarkan Usulan dan Temuan di Masyarakat", "usulan masyarakat", "suaramerdeka.com"),
        _artikel("Punya Usulan Program Irigasi? Kementerian PU Buka Pendaftaran hingga 30 November 2026", "usulan masyarakat", "majalahlintas.com"),
        _artikel("7 Tokoh Jateng Diajukan Jadi Calon Pahlawan, Pemprov Tegaskan Itu Usulan Masyarakat", "usulan masyarakat", "ppid.jatengprov.go.id"),
        _artikel("Pendaftaran Pemasangan Gigi Gratis Pemko Pekanbaru", "pendaftaran gratis", "pekanbaru.go.id"),
    ]
    monkeypatch.setattr(scraper, "RSS_SOURCES", [])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": QUERIES_HAK_CIPTA, "kata_wajib": KATA_WAJIB_HAK_CIPTA})
    monkeypatch.setattr(scraper, "fetch_google_news_search", lambda query, errors=None: [dict(a) for a in items])
    return items


def test_hak_cipta_positif_lolos(fixture_hak_cipta, capsys):
    """Judul dengan kata_wajib alternatif ('hak cipta', 'pencatatan ciptaan', 'kekayaan intelektual') harus lolos."""
    hasil = scraper.fetch_berita(TOPIK_HAK_CIPTA)
    judul = {a["judul"] for a in hasil["articles"]}

    # Positif: harus lolos
    assert "Pendaftaran Hak Cipta Lagu Gratis Mulai 1 Agustus 2026" in judul
    assert "Sah! Tarif PNBP Daftar Merek Naik, Hak Cipta Lagu Gratis" in judul
    assert "Pengamat: Pencatatan hak cipta gratis perlu diikuti pembenahan royalti" in judul
    assert "Jangan Berhenti di Sertifikat Gratis, Hak Ekonomi Pencipta Harus Dilindungi" in judul

    # Negatif: harus ditolak
    assert "Rekrutmen Sekolah Rakyat Berdasarkan Usulan dan Temuan di Masyarakat" not in judul
    assert "Punya Usulan Program Irigasi? Kementerian PU Buka Pendaftaran hingga 30 November 2026" not in judul
    assert "7 Tokoh Jateng Diajukan Jadi Calon Pahlawan, Pemprov Tegaskan Itu Usulan Masyarakat" not in judul
    assert "Pendaftaran Pemasangan Gigi Gratis Pemko Pekanbaru" not in judul

    log = capsys.readouterr().out
    assert "google_news removed (no kata_wajib)" in log
    assert hasil["sumber_status"] == "ok"


# ===== NEW TESTS: Kata Wajib Alternatives (PTKP Synonyms) =====

TOPIK_PTKP = "Pemerintah merencanakan pembaruan dan kenaikan batas PTKP yang akan berlaku 2027"
KATA_WAJIB_PTKP = ["ptkp", "penghasilan tidak kena pajak", "batas penghasilan bebas pajak", "batas gaji bebas pajak"]
QUERIES_PTKP = ["PTKP 2027", "kenaikan PTKP 2027", "batas PTKP 2027"]


@pytest.fixture
def fixture_ptkp_synonyms(monkeypatch):
    """Fixture untuk topik PTKP dengan sinonim yang harus lolos."""
    items = [
        # HARUS LOLOS - sinonim PTKP
        _artikel("Batas Penghasilan Tidak Kena Pajak Bakal Naik, Berlaku 2027?", "kenaikan PTKP 2027", "kompas.tv"),
        _artikel("Batas Gaji Bebas Pajak Berubah di 2027! Ini Bocoran Terbaru", "batas PTKP 2027", "cnbcindonesia.com"),
        _artikel("Pemerintah Siapkan PTKP Baru, Kapan Mulai Berlaku?", "PTKP 2027", "pajakku.id"),
        # Kontrol: judul dengan PTKP eksplisit juga harus lolos
        _artikel("PTKP 2027 Naik, Pemerintah Tetapkan Besaran", "PTKP 2027", "detik.com"),
    ]
    monkeypatch.setattr(scraper, "RSS_SOURCES", [])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": QUERIES_PTKP, "kata_wajib": KATA_WAJIB_PTKP})
    monkeypatch.setattr(scraper, "fetch_google_news_search", lambda query, errors=None: [dict(a) for a in items])
    return items


def test_ptkp_sinonim_lolos(fixture_ptkp_synonyms, capsys):
    """Judul dengan sinonim PTKP ('penghasilan tidak kena pajak', 'batas penghasilan bebas pajak', 'batas gaji bebas pajak') harus lolos."""
    hasil = scraper.fetch_berita(TOPIK_PTKP)
    judul = {a["judul"] for a in hasil["articles"]}

    # Sinonim harus lolos
    assert "Batas Penghasilan Tidak Kena Pajak Bakal Naik, Berlaku 2027?" in judul
    assert "Batas Gaji Bebas Pajak Berubah di 2027! Ini Bocoran Terbaru" in judul
    assert "Pemerintah Siapkan PTKP Baru, Kapan Mulai Berlaku?" in judul
    # PTKP eksplisit juga lolos
    assert "PTKP 2027 Naik, Pemerintah Tetapkan Besaran" in judul

    log = capsys.readouterr().out
    assert "google_news removed (no kata_wajib)" not in log  # tidak ada yang ditolak
    assert hasil["sumber_status"] == "ok"


# ===== NEW TESTS: Cross-domain dedup, domain cap, strong kata_wajib =====

TOPIK_DEDUP = "Test topik untuk dedup cross-domain"
QUERIES_DEDUP = ["test query"]
KATA_WAJIB_DEDUP = ["test query"]


@pytest.fixture
def fixture_dedup(monkeypatch):
    """Fixture untuk test cross-domain dedup."""
    items = [
        # Sama judul (dengan kata_wajib "test query"), domain berbeda
        _artikel("Judul Sama Test Query untuk Test", "test query", "domain1.com"),
        _artikel("Judul Sama Test Query untuk Test", "test query", "domain2.com"),
        # Berbeda judul
        _artikel("Judul Berbeda Lain Test Query", "test query", "domain3.com"),
    ]
    monkeypatch.setattr(scraper, "RSS_SOURCES", [])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": QUERIES_DEDUP, "kata_wajib": KATA_WAJIB_DEDUP})
    monkeypatch.setattr(scraper, "fetch_google_news_search", lambda query, errors=None: [dict(a) for a in items])
    return items


def test_cross_domain_dedup(fixture_dedup, capsys):
    """Judul identik dari dua domain berbeda -> hanya satu yang lolos (prioritaskan non-agregator, lalu lebih awal)."""
    hasil = scraper.fetch_berita(TOPIK_DEDUP)
    judul_list = [a["judul"] for a in hasil["articles"]]
    # Hanya satu "Judul Sama Test Query untuk Test" yang lolos (domain2.com dibuang oleh cross-dedup)
    assert judul_list.count("Judul Sama Test Query untuk Test") == 1
    assert "Judul Berbeda Lain Test Query" in judul_list
    # Status "sedikit" karena < 3 artikel
    assert hasil["sumber_status"] == "sedikit"


# Test: Domain cap untuk antaranews.com (subdomain dihitung satu)
TOPIK_ANTARA = "Test antaranews domain cap"
QUERIES_ANTARA = ["antara"]
KATA_WAJIB_ANTARA = ["antara"]


@pytest.fixture
def fixture_antara_cap(monkeypatch):
    """Fixture untuk test domain cap antaranews.com (maks 2)."""
    items = [
        _artikel("Artikel Antara 1", "antara", "kaltim.antaranews.com"),
        _artikel("Artikel Antara 2", "antara", "jambi.antaranews.com"),
        _artikel("Artikel Antara 3", "antara", "www.antaranews.com"),
        _artikel("Artikel Antara 4", "antara", "sumut.antaranews.com"),
    ]
    monkeypatch.setattr(scraper, "RSS_SOURCES", [])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": QUERIES_ANTARA, "kata_wajib": KATA_WAJIB_ANTARA})
    monkeypatch.setattr(scraper, "fetch_google_news_search", lambda query, errors=None: [dict(a) for a in items])
    return items


def test_antaranews_domain_cap(fixture_antara_cap, capsys):
    """Subdomain antaranews.com dihitung satu domain induk -> maks 2 item lolos."""
    hasil = scraper.fetch_berita(TOPIK_ANTARA)
    # Domain cap membatasi ke 2
    assert len(hasil["articles"]) == 2  # domain cap = 2 untuk non-kemenkum
    # Cek domain induk
    for a in hasil["articles"]:
        d = scraper._domain_from_source(a.get("sumber", ""), a.get("judul", ""), a.get("source_url", ""))
        assert d == "antaranews.com"
    # Status "sedikit" karena < 3 artikel
    assert hasil["sumber_status"] == "sedikit"


# Test: Domain cap untuk kemenkum.go.id (subdomain dihitung satu, maks 3)
TOPIK_KEMENKUM = "Test kemenkum domain cap"
QUERIES_KEMENKUM = ["kemenkum"]
KATA_WAJIB_KEMENKUM = ["kemenkum"]


@pytest.fixture
def fixture_kemenkum_cap(monkeypatch):
    """Fixture untuk test domain cap kemenkum.go.id (maks 3)."""
    items = [
        _artikel("Artikel Kemenkum 1", "kemenkum", "kalteng.kemenkum.go.id"),
        _artikel("Artikel Kemenkum 2", "kemenkum", "jatim.kemenkum.go.id"),
        _artikel("Artikel Kemenkum 3", "kemenkum", "kemenkum.go.id"),
        _artikel("Artikel Kemenkum 4", "kemenkum", "sulsel.kemenkum.go.id"),
    ]
    monkeypatch.setattr(scraper, "RSS_SOURCES", [])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": QUERIES_KEMENKUM, "kata_wajib": KATA_WAJIB_KEMENKUM})
    monkeypatch.setattr(scraper, "fetch_google_news_search", lambda query, errors=None: [dict(a) for a in items])
    return items


def test_kemenkum_domain_cap(fixture_kemenkum_cap, capsys):
    """Subdomain kemenkum.go.id dihitung satu domain induk -> maks 3 item lolos (kemenkum cap = 3)."""
    hasil = scraper.fetch_berita(TOPIK_KEMENKUM)
    assert len(hasil["articles"]) == 3  # domain cap = 3 untuk kemenkum
    for a in hasil["articles"]:
        d = scraper._domain_from_source(a.get("sumber", ""), a.get("judul", ""), a.get("source_url", ""))
        assert d == "kemenkum.go.id"
    assert hasil["sumber_status"] == "ok"


# Test: Strong kata_wajib lolos tanpa min_kw dan tanpa kw_count
TOPIK_STRONG = "Test strong kata_wajib PTKP sinonim"
QUERIES_STRONG = ["pembaruan PTKP 2027", "kenaikan PTKP 2027", "PTKP batas 2027"]
KATA_WAJIB_STRONG = ["ptkp", "penghasilan tidak kena pajak", "batas penghasilan bebas pajak", "batas gaji bebas pajak"]


@pytest.fixture
def fixture_strong_kata_wajib(monkeypatch):
    """Fixture untuk test strong kata_wajib (PTKP sinonim) lolos tanpa min_kw."""
    items = [
        # HARUS LOLOS - strong kata_wajib (frasa >= 2 kata atau singkatan PTKP)
        _artikel("Pemerintah Siapkan PTKP Baru, Kapan Mulai Berlaku?", "pembaruan PTKP 2027", "pajakku.id"),
        _artikel("Batas Penghasilan Bebas Pajak pada 2027 Masih Abu-Abu, Pemerintah Akui Belum Bah", "kenaikan PTKP 2027", "kontan.co.id"),
        _artikel("Pemerintah Tunda PTKP Baru di Tahun Depan, Janji Keringanan Pajak Belum Jelas", "PTKP batas 2027", "cnbcindonesia.com"),
        # HARUS DITOLAK - tidak ada kata_wajib
        _artikel("Tutorial Update E-SPT Masa PPh Pasal 21 Versi Terbaru", "pembaruan PTKP 2027", "ortax.com"),
        # HARUS DITOLAK - tidak ada kata_wajib
        _artikel("Pemerintah Telah Siapkan Sederet Insentif Pajak untuk 2027, Ini Rinciannya", "kenaikan PTKP 2027", "koran.co.id"),
    ]
    monkeypatch.setattr(scraper, "RSS_SOURCES", [])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": QUERIES_STRONG, "kata_wajib": KATA_WAJIB_STRONG})
    monkeypatch.setattr(scraper, "fetch_google_news_search", lambda query, errors=None: [dict(a) for a in items])
    return items


def test_strong_kata_wajib_lolos_tanpa_min_kw(fixture_strong_kata_wajib, capsys):
    """Strong kata_wajib (frasa >= 2 kata atau singkatan PTKP) lolos tanpa min_kw per query dan tanpa kw_count."""
    hasil = scraper.fetch_berita(TOPIK_STRONG)
    judul = {a["judul"] for a in hasil["articles"]}

    # Sinonim PTKP (strong) harus lolos meski hanya 1 query keyword cocok
    assert "Pemerintah Siapkan PTKP Baru, Kapan Mulai Berlaku?" in judul
    assert "Batas Penghasilan Bebas Pajak pada 2027 Masih Abu-Abu, Pemerintah Akui Belum Bah" in judul
    assert "Pemerintah Tunda PTKP Baru di Tahun Depan, Janji Keringanan Pajak Belum Jelas" in judul

    # Tanpa kata_wajib harus ditolak
    assert "Tutorial Update E-SPT Masa PPh Pasal 21 Versi Terbaru" not in judul
    assert "Pemerintah Telah Siapkan Sederet Insentif Pajak untuk 2027, Ini Rinciannya" not in judul

    log = capsys.readouterr().out
    # Pastikan tidak ada rejection karena "kw 1/2" atau "no other query kw" untuk item yang lolos
    assert "google_news removed (no kata_wajib)" in log  # untuk 2 item negatif
    assert hasil["sumber_status"] == "ok"


# Test: Junk titles tetap ditolak
TOPIK_JUNK = "kami Pemerintah menggratiskan biaya layanan pendaftaran untuk 19 jenis hak cipta berdasarkan usulan dari masyarakat"
KATA_WAJIB_JUNK = ["hak cipta", "hak pencipta", "pencatatan ciptaan", "kekayaan intelektual"]
QUERIES_JUNK = ["pendaftaran hak cipta gratis", "PNBP hak cipta 19 jenis", "Kemenkum hak cipta gratis"]


@pytest.fixture
def fixture_junk(monkeypatch):
    """Fixture untuk test judul sampah tetap ditolak."""
    items = [
        # HARUS DITOLAK - negatif (judul sampah)
        _artikel("Punya Usulan Program Irigasi? Kementerian PU Buka Pendaftaran hingga 30 November 2026", "usulan masyarakat", "majalahlintas.com"),
        _artikel("Pendaftaran Pemasangan Gigi Gratis Pemko Pekanbaru", "pendaftaran gratis", "pekanbaru.go.id"),
    ]
    monkeypatch.setattr(scraper, "RSS_SOURCES", [])
    monkeypatch.setattr(scraper, "buat_query_pencarian", lambda topik: {"queries": QUERIES_JUNK, "kata_wajib": KATA_WAJIB_JUNK})
    monkeypatch.setattr(scraper, "fetch_google_news_search", lambda query, errors=None: [dict(a) for a in items])
    return items


def test_junk_titles_ditolak(fixture_junk, capsys):
    """Judul sampah ('Punya Usulan Program Irigasi', 'Pendaftaran Pemasangan Gigi Gratis') tetap ditolak."""
    hasil = scraper.fetch_berita(TOPIK_JUNK)
    judul = {a["judul"] for a in hasil["articles"]}

    assert "Punya Usulan Program Irigasi? Kementerian PU Buka Pendaftaran hingga 30 November 2026" not in judul
    assert "Pendaftaran Pemasangan Gigi Gratis Pemko Pekanbaru" not in judul

    log = capsys.readouterr().out
    assert "google_news removed (no kata_wajib)" in log
    assert hasil["sumber_status"] == "kosong"  # 0 artikel -> kosong