# backend/scraper.py
# Data real gratis untuk VoxSwarm:
#   - RSS feed berita Indonesia (Detik, BBC Indonesia, Tempo, Antara, CNN Indonesia)
#   - Reddit via JSON API publik (tanpa OAuth, gratis) — DINONAKTIFKAN
#   - Fallback graceful jika semua sumber gagal
#   - Disk cache by topic hash (TTL configurable via CONTEXT_CACHE_TTL_MINUTES)

import re
import time
import json
import hashlib
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _SKLEARN_OK = True
except ImportError:
    _SKLEARN_OK = False

# ---------------------------------------------------------------------------
# Konfigurasi sumber RSS — semua gratis, tidak butuh API key
# ---------------------------------------------------------------------------

RSS_SOURCES = [
    # ponytail: Detik moved from feed.detik.com → news.detik.com/rss (2025)
    {"nama": "Detik",         "url": "https://news.detik.com/rss",                           "bahasa": "id"},
    # ponytail: BBC Indonesia URL changed: indonesian → indonesia (no 'n')
    {"nama": "BBC Indonesia", "url": "https://feeds.bbci.co.uk/indonesia/rss.xml",           "bahasa": "id"},
    {"nama": "Tempo",         "url": "https://rss.tempo.co/nasional",                        "bahasa": "id"},
    {"nama": "Antara",        "url": "https://www.antaranews.com/rss/terkini.xml",           "bahasa": "id"},
    {"nama": "CNN Indonesia", "url": "https://www.cnnindonesia.com/rss",                     "bahasa": "id"},
    # ponytail: Kompas & Tirto removed — both dead (Kompas 404 all paths, Tirto 403 blocks all)
]

# Reddit — API JSON publik (gratis, tanpa OAuth)
REDDIT_SUBREDDITS = [
    "indonesia",
    "IndonesiaNews",
    "Ekonomi_Indonesia",
]

HEADERS = {
    "User-Agent": "VoxSwarm/2.0 (research tool; contact: voxswarm@example.com)",
    "Accept": "application/rss+xml, application/xml, text/xml, application/json, */*",
}

TIMEOUT = 8  # detik

# ---------------------------------------------------------------------------
# Similarity threshold for source diversity clustering
# ---------------------------------------------------------------------------

SIMILARITY_THRESHOLD = 0.15  # ponytail: 0.15 works for short headlines; tune up if too many false clusters

COMMENT_DELAY = 2.0  # seconds between fetch_article_comments calls

# ---------------------------------------------------------------------------
# Comment Cache — baca hasil batch comment fetcher dari JSONL
# ---------------------------------------------------------------------------

_COMMENTS_CACHE_FILE = Path(__file__).parent / "data" / "comments_cache.jsonl"
_COMMENTS_CACHE_TTL  = 86400  # 24 jam

# ---------------------------------------------------------------------------
# Polling Reference — data survei terverifikasi dari lembaga kredibel
# ---------------------------------------------------------------------------

_POLLING_FILE = Path(__file__).parent / "data" / "polling_reference.json"
_POLLING_DATA = None  # lazy load di fungsi pertama kali dipanggil
_POLLING_DATA_HASH = None  # hash file terakhir — buat deteksi perubahan


def _load_polling_data() -> dict:
    """Load polling_reference.json ke memory — auto-reload kalau file berubah."""
    global _POLLING_DATA, _POLLING_DATA_HASH
    current_hash = hashlib.md5(_POLLING_FILE.read_bytes()).hexdigest()[:12] if _POLLING_FILE.exists() else "no-file"

    if _POLLING_DATA is not None and _POLLING_DATA_HASH == current_hash:
        return _POLLING_DATA

    # File berubah atau belum pernah di-load → reload
    if not _POLLING_FILE.exists():
        _POLLING_DATA = {}
        _POLLING_DATA_HASH = current_hash
        return _POLLING_DATA
    try:
        _POLLING_DATA = json.loads(_POLLING_FILE.read_text(encoding="utf-8"))
        _POLLING_DATA_HASH = current_hash
        print(f"[polling] Loaded {len(_POLLING_DATA)} polling entries (hash={current_hash})")
    except Exception:
        _POLLING_DATA = {}
        _POLLING_DATA_HASH = current_hash
    return _POLLING_DATA


def baca_komentar_cache(article_url: str) -> list[str]:
    """
    Baca komentar dari cache JSONL untuk satu artikel.
    Return kosong jika tidak ada / cache expired.

    Format cache (tiap line):
        {"source":..., "article_url":..., "comment_text":..., "scraped_at":...}
    """
    if not _COMMENTS_CACHE_FILE.exists():
        return []
    try:
        now = time.time()
        comments: list[str] = []
        for line in _COMMENTS_CACHE_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("article_url") != article_url:
                continue
            # Cek TTL
            ts_str = entry.get("scraped_at", "")
            try:
                ts = datetime.fromisoformat(ts_str).timestamp()
            except (ValueError, TypeError):
                ts = 0
            if now - ts > _COMMENTS_CACHE_TTL:
                continue
            text = entry.get("comment_text", "").strip()
            if text and len(text) > 10:
                comments.append(text)
        return comments
    except Exception:
        return []

# ---------------------------------------------------------------------------
# Diversity Score — akumulasi window (JSONL)
#   Artikel dikumpulkan dari waktu ke waktu, bukan per batch.
# ---------------------------------------------------------------------------

_DIVERSITY_WINDOW_FILE = Path(__file__).parent / "data" / "diversity_window.jsonl"
_DIVERSITY_WINDOW_MAX  = 500   # max artikel di window
_DIVERSITY_WINDOW_DAYS = 7     # hapus artikel lebih lama dari ini


def append_to_diversity_window(articles: list[dict]) -> None:
    """Append artikel baru ke window file (JSONL)."""
    if not articles:
        return
    try:
        _DIVERSITY_WINDOW_FILE.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        with open(_DIVERSITY_WINDOW_FILE, "a", encoding="utf-8") as f:
            for art in articles:
                art["_window_ts"] = now
                f.write(json.dumps(art, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_diversity_window() -> list[dict]:
    """Load semua artikel dari window file, dedup by ID (keep latest)."""
    if not _DIVERSITY_WINDOW_FILE.exists():
        return []
    try:
        articles = []
        for line in _DIVERSITY_WINDOW_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    articles.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        # Dedup by ID — keep latest occurrence
        seen: dict = {}
        for art in articles:
            aid = art.get("id")
            if aid:
                seen[aid] = art
        return list(seen.values()) if seen else articles
    except Exception:
        return []


def prune_diversity_window() -> int:
    """Hapus artikel tua/berlebih dari window. Return jumlah dihapus."""
    articles = load_diversity_window()
    if not articles:
        return 0

    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - (_DIVERSITY_WINDOW_DAYS * 86400)
    kept = []
    pruned = 0

    for art in articles:
        ts = art.get("_window_ts", "")
        try:
            t = datetime.fromisoformat(ts).timestamp()
        except (ValueError, TypeError):
            t = 0
        if t >= cutoff:
            kept.append(art)
        else:
            pruned += 1

    # Trim ke max — buang paling tua
    if len(kept) > _DIVERSITY_WINDOW_MAX:
        kept.sort(key=lambda a: a.get("_window_ts", ""), reverse=True)
        pruned += len(kept) - _DIVERSITY_WINDOW_MAX
        kept = kept[:_DIVERSITY_WINDOW_MAX]

    try:
        with open(_DIVERSITY_WINDOW_FILE, "w", encoding="utf-8") as f:
            for art in kept:
                f.write(json.dumps(art, ensure_ascii=False) + "\n")
    except Exception:
        pass

    return pruned

# ---------------------------------------------------------------------------
# Disk Cache Config
# ---------------------------------------------------------------------------

import os

_CACHE_DIR  = Path(__file__).parent / "data"
_CACHE_FILE = _CACHE_DIR / "context_cache.json"
_CACHE_TTL  = int(os.getenv("CONTEXT_CACHE_TTL_MINUTES", "30")) * 60   # detik
_CACHE_MAX  = int(os.getenv("CONTEXT_CACHE_MAX_ENTRIES", "100"))        # maks topik disimpan

# ponytail: bump tiap kali logic relevansi/filter berubah → force refetch cache
CACHE_SCHEMA_VERSION = "v4-content-overlap"


def _get_polling_reference_hash() -> str:
    """Hash isi polling_reference.json — cache auto-invalidate kalau file berubah."""
    if not _POLLING_FILE.exists():
        return "no-file"
    try:
        return hashlib.md5(_POLLING_FILE.read_bytes()).hexdigest()[:12]
    except Exception:
        return "no-file"


def _current_schema() -> str:
    """Combined schema: kode version + polling_reference.json hash."""
    return f"{CACHE_SCHEMA_VERSION}_{_get_polling_reference_hash()}"

_cache_lock = threading.Lock()
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Key reserved buat metadata cache (bukan entry topik)
_META_KEY = "_schema_version"


def _topic_key(topik: str) -> str:
    """Hash MD5 dari topik lowercase — jadi key cache."""
    return hashlib.md5(topik.strip().lower().encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    """
    Baca cache dari disk. Return {} jika:
    - file belum ada / corrupt
    - schema version tidak cocok (force refetch)
    """
    expected = _current_schema()
    if not _CACHE_FILE.exists():
        return {}
    try:
        cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        # Schema versioning: jika gak cocok, return {} biar di-refetch
        if cache.get(_META_KEY) != expected:
            print(f"[Cache] Schema mismatch (have={cache.get(_META_KEY)!r}, need={expected!r}) — force refetch")
            return {}
        return cache
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    """Tulis cache ke disk. Silent fail jika tidak bisa write."""
    # Pastikan schema version (kode + polling hash) selalu tersimpan
    cache[_META_KEY] = _current_schema()
    try:
        _CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=None),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[Cache] Gagal simpan cache: {e}")


def _cache_entries(cache: dict) -> list[tuple]:
    """Return list of (key, entry) pairs, excluding metadata keys."""
    return [(k, v) for k, v in cache.items() if not k.startswith("_")]


def _get_cached(topik: str) -> Optional[dict]:
    """
    Ambil konteks dari cache jika masih valid (belum expired).
    Return None jika miss, schema mismatch, atau TTL terlewat.
    """
    with _cache_lock:
        cache = _load_cache()
        key   = _topic_key(topik)
        entry = cache.get(key)
        if not entry:
            return None

        age = time.time() - entry.get("cached_at", 0)
        if age > _CACHE_TTL:
            # Expired — hapus entry
            cache.pop(key, None)
            _save_cache(cache)
            return None

        return entry.get("data")


def _set_cache(topik: str, data: dict) -> None:
    """
    Simpan konteks ke cache dengan timestamp sekarang.
    Trim entri terlama jika melebihi CACHE_MAX.
    """
    with _cache_lock:
        cache = _load_cache()
        key   = _topic_key(topik)

        cache[key] = {
            "topik":     topik,
            "cached_at": time.time(),
            "data":      data,
        }

        # Trim: buang entri terlama jika cache terlalu besar (skip metadata key)
        entries = _cache_entries(cache)
        if len(entries) > _CACHE_MAX:
            sorted_entries = sorted(entries, key=lambda e: e[1].get("cached_at", 0))
            for old_key, _ in sorted_entries[:len(entries) - _CACHE_MAX]:
                cache.pop(old_key, None)

        _save_cache(cache)


def clear_context_cache(topik: Optional[str] = None) -> int:
    """
    Hapus cache.
    - topik=None  → hapus semua (metadata tetap)
    - topik=str   → hapus hanya topik itu

    Return: jumlah entri topik yang dihapus.
    """
    with _cache_lock:
        cache = _load_cache()
        if topik is None:
            n = len(_cache_entries(cache))
            # Reset: simpan cuma metadata
            new_cache = {}
            if _META_KEY in cache:
                new_cache[_META_KEY] = cache[_META_KEY]
            _save_cache(new_cache)
            return n
        key = _topic_key(topik)
        if key in cache:
            cache.pop(key)
            _save_cache(cache)
            return 1
        return 0


def get_cache_stats() -> dict:
    """Info ringkas tentang kondisi cache saat ini."""
    with _cache_lock:
        cache = _load_cache()
        entries = _cache_entries(cache)
        now   = time.time()
        valid = sum(1 for _, e in entries if now - e.get("cached_at", 0) <= _CACHE_TTL)
        return {
            "total_entries": len(entries),
            "valid_entries": valid,
            "expired_entries": len(entries) - valid,
            "ttl_minutes": _CACHE_TTL // 60,
            "max_entries": _CACHE_MAX,
            "schema_version": cache.get(_META_KEY),
            "cache_file": str(_CACHE_FILE),
        }


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _fetch(url: str, headers: dict = None, timeout: int = TIMEOUT) -> Optional[str]:
    """Fetch URL, return body string atau None jika gagal."""
    try:
        req = urllib.request.Request(url, headers=headers or HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1", errors="replace")
    except Exception:
        return None


def _clean_html(text: str) -> str:
    """Hapus tag HTML dan normalisasi whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;",  "&",  text)
    text = re.sub(r"&lt;",   "<",  text)
    text = re.sub(r"&gt;",   ">",  text)
    text = re.sub(r"&quot;", '"',  text)
    text = re.sub(r"&#\d+;", " ",  text)
    text = re.sub(r"\s+",    " ",  text)
    return text.strip()


def _artikel_id(url: str) -> str:
    """ID unik dari URL artikel."""
    return hashlib.md5(url.encode()).hexdigest()[:10]


# ---------------------------------------------------------------------------
# RSS Parser
# ---------------------------------------------------------------------------

def _parse_rss(xml_text: str, sumber: str) -> list[dict]:
    """Parse RSS/Atom XML → list artikel."""
    articles = []
    try:
        xml_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)
        root     = ET.fromstring(xml_text)

        ns      = {"atom": "http://www.w3.org/2005/Atom"}
        is_atom = root.tag.endswith("feed")

        if is_atom:
            items = root.findall("atom:entry", ns) or root.findall("entry")
        else:
            items = root.findall(".//item")

        for item in items[:10]:
            if is_atom:
                judul     = item.findtext("atom:title", "", ns) or item.findtext("title", "")
                link_el   = item.find("atom:link", ns) or item.find("link")
                link      = link_el.get("href", "") if link_el is not None else ""
                ringkasan = (
                    item.findtext("atom:summary", "", ns)
                    or item.findtext("atom:content", "", ns)
                    or item.findtext("summary", "")
                )
                tanggal = item.findtext("atom:published", "", ns) or item.findtext("published", "")
            else:
                judul     = item.findtext("title", "")
                link      = item.findtext("link", "")
                ringkasan = item.findtext("description", "") or item.findtext("content:encoded", "")
                tanggal   = item.findtext("pubDate", "")

            judul     = _clean_html(judul)
            ringkasan = _clean_html(ringkasan)[:400]

            if not judul:
                continue

            articles.append({
                "id":        _artikel_id(link or judul),
                "judul":     judul,
                "ringkasan": ringkasan,
                "link":      link,
                "sumber":    sumber,
                "tanggal":   tanggal,
                "tipe":      "berita",
            })
    except ET.ParseError:
        pass
    return articles


# ---------------------------------------------------------------------------
# TF-IDF Relevance Scoring (0 LLM call, lebih akurat dari keyword counting)
# ---------------------------------------------------------------------------

# Indonesian stopwords — minimal set buat content-word overlap check
_CONTENT_STOPWORDS = frozenset({
    "dan", "di", "ke", "dari", "yang", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "akan", "telah", "sudah", "bisa", "dapat", "tidak",
    "ada", "juga", "atau", "karena", "oleh", "sebagai", "serta", "saat",
    "dalam", "secara", "lebih", "sangat", "antara", "setelah", "seperti",
    "hanya", "mereka", "kami", "kita", "saya", "dia", "ia", "anda",
    "bahwa", "namun", "tetapi", "sedangkan", "sementara", "jika", "kalau",
    "maka", "sehingga", "mengapa", "bagaimana", "apa", "siapa", "mana",
    "kapan", "banyak", "beberapa", "seluruh", "semua", "para", "si",
    "sang", "para", "ia", "pun", "pernah", "belum", "agar", "supaya",
    "sebab", "meski", "walaupun", "biar", "hendak", "mau", "ingin",
})

_CONTENT_MIN_WORD_LEN = 3  # minimal panjang kata buat dianggap content word


def _is_numeric_token(token: str) -> bool:
    """True kalo token cuma angka (tahun, nominal, dll)."""
    return token.isdigit()


def _extract_content_words(teks: str) -> set:
    """
    Ambil kata-kata bermakna (bukan stopword, bukan angka, min length).
    """
    words = teks.lower().split()
    result = set()
    for w in words:
        w_clean = w.strip(".,!?;:\"'()[]{}")
        if (len(w_clean) >= _CONTENT_MIN_WORD_LEN
                and w_clean not in _CONTENT_STOPWORDS
                and not _is_numeric_token(w_clean)):
            result.add(w_clean)
    return result


def _count_content_overlap(topic_content: set, article_teks: str) -> int:
    """Hitung berapa content word dari topic yg muncul di article."""
    article_words = _extract_content_words(article_teks)
    return len(topic_content & article_words)


def _bersih_teks(teks: str) -> str:
    """Lowercase, hapus non-alfanumerik, normalize whitespace."""
    return "".join(
        c if (c.isascii() and c.isalnum()) or c.isspace() else " "
        for c in teks.lower().strip()
    )


def _hitung_relevansi_tfidf(topik: str, items: list[dict], maks: int = 15) -> list[dict]:
    """
    Hitung relevansi items (berita/Reddit) terhadap topik
    menggunakan TF-IDF + cosine similarity.

    Fallback ke keyword counting sederhana jika sklearn tidak tersedia.
    """
    if not items:
        return []

    if not _SKLEARN_OK:
        return _hitung_relevansi_keyword(topik, items, maks)

    # Build corpus: topic first, then each item's text
    topic_clean = _bersih_teks(topik)
    texts = [topic_clean]

    for item in items:
        teks = _bersih_teks(item.get("judul", "") + " " + item.get("ringkasan", item.get("selftext", "")))
        texts.append(teks)

    if len(texts) < 2:
        for item in items:
            item["relevansi"] = 0.0
        return items[:maks]

    try:
        vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        matrix = vectorizer.fit_transform(texts)
        topic_vec = matrix[0:1]
        article_vecs = matrix[1:]

        sims = cosine_similarity(topic_vec, article_vecs)[0]

        for i, item in enumerate(items):
            item["relevansi"] = round(float(sims[i]), 4)

        items.sort(key=lambda x: -x.get("relevansi", 0))

        # ── Content-word overlap filter ──────────────────────────────────
        # Prevent false positive where only numeric token (tahun) matches.
        # Article must share at least 2 content words with topic (if topic
        # has >= 2 content words), or at least 1 (if topic has 1).
        # Skip check if topic has 0 content words (all stopwords/numbers).
        topic_content = _extract_content_words(topik)
        if len(topic_content) >= 2:
            min_overlap = 2
        elif len(topic_content) == 1:
            min_overlap = 1
        else:
            min_overlap = 0  # no content words to match — skip check

        passed = []
        for it in items:
            if it.get("relevansi", 0) < SIMILARITY_THRESHOLD:
                continue
            if min_overlap > 0:
                article_text = it.get("judul", "") + " " + it.get("ringkasan", "")
                overlap = _count_content_overlap(topic_content, article_text)
                if overlap < min_overlap:
                    continue
            passed.append(it)

        return passed[:maks]

    except Exception as exc:
        print(f"[scraper] TF-IDF relevance error: {exc}, fallback keyword")
        return _hitung_relevansi_keyword(topik, items, maks)


def _hitung_relevansi_keyword(topik: str, items: list[dict], maks: int = 15) -> list[dict]:
    """Fallback: keyword counting sederhana."""
    kata_kunci = [k.lower() for k in topik.split() if len(k) > 3]
    for item in items:
        teks = (item.get("judul", "") + " " + item.get("ringkasan", item.get("selftext", ""))).lower()
        item["relevansi"] = sum(1 for k in kata_kunci if k in teks)

    items.sort(key=lambda x: -x.get("relevansi", 0))
    seen = set()
    hasil = []
    for it in items:
        idd = it.get("id", "")
        if idd not in seen:
            seen.add(idd)
            hasil.append(it)
    return hasil[:maks]


# ---------------------------------------------------------------------------
# Fetch News (RSS)
# ---------------------------------------------------------------------------

def fetch_berita(topik: str, maks_per_sumber: int = 3) -> dict:
    """
    Ambil berita terkini dari semua RSS source.
    Filter relevan dengan TF-IDF (fallback keyword counting).

    Returns dict:
        {"articles": list[dict], "total_unik": int, "total_filtered": int}
          articles         — artikel yg lolos threshold (sorted by relevance desc)
          total_unik       — total semua kandidat UNIK sebelum filter
          total_filtered   — jumlah artikel yg lolos threshold
    """
    semua = []

    for src in RSS_SOURCES:
        xml = _fetch(src["url"])
        if not xml:
            continue
        articles = _parse_rss(xml, src["nama"])
        semua.extend(articles)

    # Dedup by ID
    seen = set()
    unik = []
    for art in semua:
        if art["id"] not in seen:
            seen.add(art["id"])
            unik.append(art)

    total_unik = len(unik)
    if not unik:
        return {"articles": [], "total_unik": 0, "total_filtered": 0}

    filtered = _hitung_relevansi_tfidf(topik, unik, maks=15)
    return {
        "articles": filtered,
        "total_unik": total_unik,
        "total_filtered": len(filtered),
    }


# ---------------------------------------------------------------------------
# Polling Reference Lookup — cari data survei terverifikasi untuk topik
# ---------------------------------------------------------------------------

def cari_polling_reference(topik: str) -> dict | None:
    """
    Cek apakah topik match salah satu entry di polling_reference.json.
    Case-insensitive substring match terhadap keywords.
    Return entry pertama yg match (dengan field 'key'), atau None.
    """
    data = _load_polling_data()
    if not data:
        return None

    topik_lower = topik.lower()

    for key, entry in data.items():
        for kw in entry.get("keywords", []):
            if kw.lower() in topik_lower:
                result = dict(entry)
                result["key"] = key
                return result
    return None


# ---------------------------------------------------------------------------
# Fungsi utama: gabungkan berita + Reddit → briefing untuk agen
# (dengan disk cache — tidak fetch ulang jika topik sama & TTL belum habis)
# ---------------------------------------------------------------------------

def ambil_konteks_real(topik: str, force_refresh: bool = False, topik_asli: str | None = None) -> dict:
    """
    Ambil data real dari berita RSS, gabungkan jadi briefing
    yang siap dipakai sebagai konteks agen sebelum simulasi dimulai.

    Reddit dinonaktifkan — tidak representatif dan API tidak stabil.

    Cache:
      - Hit  → return langsung dari disk, 0 HTTP request
      - Miss → fetch RSS, simpan ke cache, return
      - TTL  → default 30 menit (CONTEXT_CACHE_TTL_MINUTES di .env)
      - force_refresh=True → skip cache, fetch ulang

    Returns:
        {
            "berita":    [...],
            "reddit":    [],
            "briefing":  str,
            "total":     int,
            "timestamp": str,
            "from_cache": bool,
        }
    """
    # ── Cache lookup ──────────────────────────────────────────────────────
    if not force_refresh:
        cached = _get_cached(topik)
        if cached:
            cached["from_cache"] = True
            # ponytail: inject data_transparency if missing (old cache before field existed)
            if "data_transparency" not in cached:
                rss_passed = len(cached.get("berita", []))
                polling_matched = cached.get("polling_reference") is not None
                if rss_passed == 0 and not polling_matched:
                    cached["data_transparency"] = {
                        "rss_articles_found": 0,
                        "rss_articles_passed_threshold": 0,
                        "polling_reference_matched": False,
                        "briefing_status": "empty",
                        "note": "Tidak ditemukan berita relevan maupun data survei untuk topik ini. Hasil simulasi berdasarkan pengetahuan umum agent, bukan data real-time.",
                    }
                elif rss_passed == 0 and polling_matched:
                    cached["data_transparency"] = {
                        "rss_articles_found": 0,
                        "rss_articles_passed_threshold": 0,
                        "polling_reference_matched": True,
                        "briefing_status": "limited",
                        "note": "Tidak ada berita RSS relevan. Briefing menggunakan data survei tervalidasi sebagai gantinya.",
                    }
                elif rss_passed < 3:
                    cached["data_transparency"] = {
                        "rss_articles_found": 0,
                        "rss_articles_passed_threshold": rss_passed,
                        "polling_reference_matched": polling_matched,
                        "briefing_status": "limited",
                        "note": f"Hanya {rss_passed} artikel RSS relevan ditemukan. Briefing terbatas.",
                    }
                else:
                    cached["data_transparency"] = {
                        "rss_articles_found": 0,
                        "rss_articles_passed_threshold": rss_passed,
                        "polling_reference_matched": polling_matched,
                        "briefing_status": "full",
                        "note": f"{rss_passed} artikel RSS relevan + data survei tersedia.",
                    }
            return cached
    # ─────────────────────────────────────────────────────────────────────

    # Fetch berita dari RSS — 0 biaya, 0 API key
    fetch_result = fetch_berita(topik)
    berita = fetch_result["articles"]
    total_unik = fetch_result["total_unik"]
    total_filtered = fetch_result["total_filtered"]

    print(f"[relevance-debug] topik={topik!r} | {total_unik} unik, {total_filtered} lolos threshold (>= {SIMILARITY_THRESHOLD:.2f})")
    for b in berita[:5]:
        print(f"  - [{b.get('relevansi', 'N/A')}] {b['judul'][:60]}")

    # Simpan ke diversity window (akumulasi lintas sesi)
    append_to_diversity_window(berita)
    reddit = []

    # Inject komentar dari cache untuk artikel Detik (yang komentar real-nya valid)
    for art in berita:
        if art.get("sumber") == "Detik":
            komentar = baca_komentar_cache(art.get("link", ""))
            if komentar:
                art["komentar_cache"] = komentar

    # ── Cari polling reference: match ke topik ASLI (sebelum ekspansi akronim) ──
    # ponytail: topik_asli dipisah biar match substring gak terganggu ekspansi
    #           misal "BBM" → "Bahan Bakar Minyak (BBM)", "subsidi bbm" tetap match
    polling = cari_polling_reference(topik_asli or topik)
    # ────────────────────────────────────────────────────────────────────────────

    # Bangun teks briefing ringkas — include polling jika ada
    baris = []

    if berita:
        baris.append("📰 BERITA TERKINI:")
        for i, art in enumerate(berita[:5], 1):
            ring = f" — {art['ringkasan'][:120]}..." if art["ringkasan"] else ""
            baris.append(f"  {i}. [{art['sumber']}] {art['judul']}{ring}")
            # Tempel komentar dari cache kalau ada
            komen = art.get("komentar_cache", [])
            for k in komen[:3]:
                baris.append(f"       💬 {k[:100]}")

    # Sisipkan polling reference — data lebih kredibel dari RSS
    if polling:
        baris.append("")
        baris.append("📊 DATA SURVEI TERVERIFIKASI:")
        baris.append(f"  [{polling['sumber']}] — {polling['tanggal']}")
        baris.append(f"  {polling['ringkasan']}")
        baris.append(f"  (kategori: {polling['kategori']})")

    briefing = (
        f"=== DATA REAL TERKAIT TOPIK: {topik} ===\n"
        + "\n".join(baris)
        + "\n=== GUNAKAN DATA INI SEBAGAI REFERENSI, BUKAN SATU-SATUNYA FAKTA ==="
    ) if baris else ""

    # ── Transparency field — biar operator tau kondisi briefing ─────────────
    polling_matched = polling is not None
    rss_passed = total_filtered

    if rss_passed == 0 and not polling_matched:
        briefing_status = "empty"
        note = "Tidak ditemukan berita relevan maupun data survei untuk topik ini. Hasil simulasi berdasarkan pengetahuan umum agent, bukan data real-time."
    elif rss_passed == 0 and polling_matched:
        briefing_status = "limited"
        note = "Tidak ada berita RSS relevan. Briefing menggunakan data survei tervalidasi sebagai gantinya."
    elif rss_passed < 3:
        briefing_status = "limited"
        note = f"Hanya {rss_passed} artikel RSS relevan ditemukan. Briefing terbatas."
    else:
        briefing_status = "full"
        note = f"{rss_passed} artikel RSS relevan + data survei tersedia."

    data_transparency = {
        "rss_articles_found": total_unik,
        "rss_articles_passed_threshold": rss_passed,
        "polling_reference_matched": polling_matched,
        "briefing_status": briefing_status,
        "note": note,
    }
    # ───────────────────────────────────────────────────────────────────────

    result = {
        "berita":              berita,
        "reddit":              reddit,
        "briefing":            briefing,
        "total":               rss_passed + len(reddit),
        "timestamp":           datetime.now(timezone.utc).isoformat(),
        "from_cache":          False,
        "polling_reference":   polling,
        "data_transparency":   data_transparency,
    }

    # ── Simpan ke cache ───────────────────────────────────────────────────
    _set_cache(topik, result)
    # ─────────────────────────────────────────────────────────────────────

    return result


# ---------------------------------------------------------------------------
# Source Diversity Score (Fase 1)
#   Kelompokkan artikel dari berbagai sumber berdasarkan kemiripan topik,
#   lalu hitung berapa sumber unik yang memberitakan isu yang sama.
#   Tidak menggunakan LLM — murni TF-IDF + cosine similarity.
# ---------------------------------------------------------------------------

_SIM_CACHE: dict = {}  # ponytail: memoize pairwise sims dalam 1 batch


def _teks_artikel(art: dict) -> str:
    """Gabung judul + ringkasan jadi satu string untuk dibandingkan."""
    return f"{art.get('judul', '')} {art.get('ringkasan', '')}"


def cluster_articles_by_topic(
    articles: list[dict],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[list[dict]]:
    """
    Kelompokkan artikel yang membahas isu yang mirip.

    Pakai TF-IDF + cosine similarity pairwise.
    Fallback ke Jaccard word overlap kalau sklearn nggak available.
    Return list of clusters, tiap cluster = list artikel.
    """
    if len(articles) < 2:
        return [articles] if articles else []

    texts = [_teks_artikel(a) for a in articles]

    if _SKLEARN_OK and len(texts) >= 2:
        try:
            vec = TfidfVectorizer(max_features=1000, ngram_range=(1, 2), sublinear_tf=True)
            matrix = vec.fit_transform(texts)
            sims = cosine_similarity(matrix)
        except Exception:
            sims = _jaccard_similarity_matrix(texts)
    else:
        sims = _jaccard_similarity_matrix(texts)

    # Connected components via DFS (gangguan kecil, manual aja)
    n = len(articles)
    visited = [False] * n
    clusters = []

    for i in range(n):
        if visited[i]:
            continue
        cluster = []
        stack = [i]
        while stack:
            idx = stack.pop()
            if visited[idx]:
                continue
            visited[idx] = True
            cluster.append(articles[idx])
            for j in range(n):
                if not visited[j] and sims[idx][j] >= threshold:
                    stack.append(j)
        clusters.append(cluster)

    return clusters


def _jaccard_similarity_matrix(texts: list[str]) -> list[list[float]]:
    """Fallback Jaccard similarity — stdlib aja, ga perlu sklearn."""
    n = len(texts)
    tokens = [set(t.lower().split()) for t in texts]
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        mat[i][i] = 1.0
        for j in range(i + 1, n):
            a, b = tokens[i], tokens[j]
            if not a or not b:
                continue
            intersection = len(a & b)
            union = len(a | b)
            sim = intersection / union if union else 0.0
            mat[i][j] = mat[j][i] = sim
    return mat


def compute_source_diversity_scores(
    articles: Optional[list[dict]] = None,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """
    Hitung source diversity score untuk setiap kluster topik.

    Jika articles=None, pakai window artikel akumulasi dari JSONL.
    Jika articles=list, hitung dari list tersebut (backward compat).

    Returns:
        [
            {
                "topik_cluster_id": int,
                "source_count": int,
                "sources": [str, ...],
                "score": float,         # source_count / total available sources
                "articles": [dict, ...], # artikel di kluster ini
            },
            ...
        ]
    """
    if articles is None:
        prune_diversity_window()
        articles = load_diversity_window()

    clusters = cluster_articles_by_topic(articles, threshold)
    total_sources = len(RSS_SOURCES)
    results = []

    for cid, cluster in enumerate(clusters):
        sources = sorted({a.get("sumber", "Unknown") for a in cluster})
        sc = len(sources)
        results.append({
            "topik_cluster_id": cid,
            "source_count": sc,
            "sources": sources,
            "score": round(sc / total_sources, 4) if total_sources else 0.0,
            "articles": cluster,
        })

    # Sort: most diverse first
    results.sort(key=lambda r: -r["score"])
    return results


