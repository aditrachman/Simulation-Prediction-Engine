# backend/scraper.py
# Data real gratis untuk VoxSwarm:
#   - RSS feed berita Indonesia (Detik, BBC Indonesia, Tempo, Antara, CNN Indonesia)
#   - Reddit via JSON API publik (tanpa OAuth, gratis) — DINONAKTIFKAN
#   - Fallback graceful jika semua sumber gagal
#   - Disk cache by topic hash (TTL configurable via CONTEXT_CACHE_TTL_MINUTES)

import re
import time
import traceback
import json
import hashlib
import math
import threading
from datetime import datetime, timezone, timedelta
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
    # 403 per 2026-11-07 — dimatikan, bukan dihapus, biar gampang diaktifkan lagi
    {"nama": "Tempo",         "url": "https://rss.tempo.co/nasional",                        "bahasa": "id", "enabled": False},
    {"nama": "Antara",        "url": "https://www.antaranews.com/rss/terkini.xml",           "bahasa": "id"},
    {"nama": "CNN Indonesia", "url": "https://www.cnnindonesia.com/rss",                     "bahasa": "id"},
    # Feed ekonomi — topik pajak/upah/UMKM jarang muncul di feed umum.
    {"nama": "Detik Finance", "url": "https://finance.detik.com/rss",                        "bahasa": "id"},
    {"nama": "Antara Ekonomi","url": "https://www.antaranews.com/rss/ekonomi.xml",           "bahasa": "id"},
    {"nama": "CNN Ekonomi",   "url": "https://www.cnnindonesia.com/ekonomi/rss",            "bahasa": "id"},
    {"nama": "CNBC Indonesia","url": "https://www.cnbcindonesia.com/rss",                    "bahasa": "id"},
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

# Google News Search filters
GOOGLE_NEWS_MAX_AGE_DAYS = 120  # maksimal umur artikel (hari)

def _extract_registrable_domain(url: str) -> str:
    """Ekstrak domain registrable (eTLD+1) dari URL.
    Contoh: kaltim.antaranews.com -> antaranews.com
            jambi.antaranews.com -> antaranews.com
            www.kemenkum.go.id -> kemenkum.go.id
            kemenkum.go.id -> kemenkum.go.id
    """
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if not host:
            return ""
        # Hapus port jika ada
        host = host.split(":")[0]
        # Hapus www prefix
        if host.startswith("www."):
            host = host[4:]
        # Daftar TLD Indonesia dua bagian
        parts = host.split(".")
        if len(parts) <= 2:
            return host
        # Cek TLD Indonesia dua bagian
        tld_2part = {"co.id", "go.id", "ac.id", "or.id", "web.id", "sch.id", "mil.id", "biz.id"}
        if len(parts) >= 3 and ".".join(parts[-2:]) in {"co.id", "go.id", "ac.id", "or.id", "web.id", "sch.id", "mil.id", "biz.id"}:
            return ".".join(parts[-3:])
        # Default: ambil 2 bagian terakhir
        return ".".join(parts[-2:])
    except Exception:
        return ""

def _domain_from_source(source: str, title: str, source_url: str = "") -> str:
    """Ekstrak domain dari source_url jika ada, fallback ke judul/sumber."""
    # Prioritas 1: source_url dari Google News RSS
    if source_url:
        domain = _extract_registrable_domain(source_url)
        if domain:
            return domain
    # Prioritas 2: fallback ke parsing judul/sumber (untuk backward compat)
    if source != "google_news_search":
        return source.lower()
    # Untuk google_news_search tanpa source_url, fallback ke parsing judul
    import re
    match = re.search(r'[-–|]\s*([A-Za-z0-9.]+(?:[.\-][A-Za-z0-9]+)*)\s*$', title)
    if match:
        domain = match.group(1).lower()
        # Normalisasi domain
        if 'antara' in domain:
            return 'antaranews.com'
        if 'detik' in domain:
            return 'detik.com'
        if 'rri' in domain:
            return 'rri.co.id'
        if 'tempo' in domain:
            return 'tempo.co'
        if 'cnn' in domain:
            return 'cnnindonesia.com'
        if 'cnbc' in domain:
            return 'cnbcindonesia.com'
        if 'balipost' in domain:
            return 'balipost.com'
        if 'mercusuar' in domain:
            return 'mercusuar.merdeka.com'
        if 'pont' in domain:
            return 'pontianakpost.com'
        if 'jati' in domain:
            return 'jati.or.id'
        if 'reda' in domain:
            return 'reda.co.id'
        if 'balipost' in domain:
            return 'balipost.com'
        if any(x in domain for x in ['kalimantan', 'kalbar', 'kaltim', 'sulteng', 'sulawesi', 'sumatera', 'papua']):
            return 'antaranews.com'
        return domain
    return source.lower()

def _is_kemenkum_domain(domain: str) -> bool:
    return 'kemenkum.go.id' in domain

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
    except Exception as e:
        print(f"[SOURCES] _load_polling_data error={type(e).__name__}: {e}")
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
    except Exception as e:
        print(f"[SOURCES] baca_komentar_cache error={type(e).__name__}: {e}")
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
    except Exception as e:
        print(f"[SOURCES] append_to_diversity_window error={type(e).__name__}: {e}")
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
    except Exception as e:
        print(f"[SOURCES] load_diversity_window error={type(e).__name__}: {e}")
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
    except Exception as e:
        print(f"[SOURCES] prune_diversity_window write error={type(e).__name__}: {e}")
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
CACHE_SCHEMA_VERSION = "v5-topic-keywords"


def _get_polling_reference_hash() -> str:
    """Hash isi polling_reference.json — cache auto-invalidate kalau file berubah."""
    if not _POLLING_FILE.exists():
        return "no-file"
    try:
        return hashlib.md5(_POLLING_FILE.read_bytes()).hexdigest()[:12]
    except Exception as e:
        print(f"[SOURCES] _get_polling_reference_hash error={type(e).__name__}: {e}")
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
    except Exception as e:
        print(f"[SOURCES] _load_cache error={type(e).__name__}: {e}")
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

def _fetch(url: str, headers: dict = None, timeout: int = TIMEOUT, errors: list | None = None) -> Optional[str]:
    """Fetch URL, return body string atau None jika gagal."""
    try:
        req = urllib.request.Request(url, headers=headers or HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1", errors="replace")
    except Exception as e:
        print(f"[SOURCES] fetch_exception url={url} error={type(e).__name__}: {e}")
        traceback.print_exc()
        if errors is not None:
            errors.append(f"{url}: {type(e).__name__}: {e}")
        return None


def _ringkas_error(err: str) -> str:
    """Ringkas pesan error fetch jadi bentuk pendek 'host: HTTP 403'."""
    host = re.sub(r"^https?://", "", err).split("/", 1)[0].split(": ", 1)[0].rstrip(":") or "sumber"
    status = re.search(r"HTTP Error (\d+)", err)
    if status:
        return f"{host}: HTTP {status.group(1)}"
    tipe = re.search(r":\s*([A-Za-z_]\w*(?:Error|Exception)):", err)
    if tipe:
        return f"{host}: {tipe.group(1)}"
    return f"{host}: gagal"


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


def _parse_rss_date(date_str: str) -> datetime | None:
    """Parse berbagai format tanggal RSS ke datetime UTC.
    Support: RFC 2822 (RFC 822), RFC 3339, ISO 8601, dan format umum RSS."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # Format umum yang sering dipakai RSS
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",      # RFC 2822: Mon, 02 Jan 2023 15:04:05 +0700
        "%a, %d %b %Y %H:%M:%S %Z",      # RFC 2822 dengan zona nama: Mon, 02 Jan 2023 15:04:05 GMT
        "%a, %d %b %Y %H:%M:%S",         # Tanpa zona
        "%d %b %Y %H:%M:%S %z",          # 02 Jan 2023 15:04:05 +0700
        "%d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",           # ISO 8601: 2023-01-02T15:04:05+07:00
        "%Y-%m-%dT%H:%M:%SZ",            # ISO 8601 UTC: 2023-01-02T15:04:05Z
        "%Y-%m-%dT%H:%M:%S.%f%z",        # ISO dengan microsecond
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",             # 2023-01-02 15:04:05
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


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

        print(f"[SOURCES] _parse_rss sumber={sumber} format={'atom' if is_atom else 'rss'} items_found={len(items)}")
        for item in items[:30]:
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

                # Google News RSS has <source url="..."> element
                source_el = item.find("source")
                source_url = source_el.get("url", "") if source_el is not None else ""

            judul     = _clean_html(judul)
            ringkasan = _clean_html(ringkasan)[:400]

            if not judul:
                continue

            articles.append({
                "id":         _artikel_id(link or judul),
                "judul":      judul,
                "ringkasan":  ringkasan,
                "link":       link,
                "sumber":     sumber,
                "tanggal":    tanggal,
                "tipe":       "berita",
                "source_url": source_url if not is_atom else "",
            })
    except ET.ParseError as e:
        print(f"[SOURCES] _parse_rss parse_error sumber={sumber} error={e}")
    except Exception as e:
        print(f"[SOURCES] _parse_rss exception sumber={sumber} error={type(e).__name__}: {e}")
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

# Kata yang terlalu umum di topik kebijakan — bikin hampir semua berita "cocok".
_GENERIC_TOPIC_WORDS = frozenset({
    "apakah", "bagaimana", "mengapa", "kenapa", "kapan", "dimana", "siapa",
    "berapa", "pemerintah", "pemda", "negara", "pusat", "daerah", "kebijakan",
    "program", "aturan", "dampak", "dampaknya", "pengaruh", "pengaruhnya",
    "akibat", "akibatnya", "solusi", "langkah", "upaya", "masalah", "isu",
    "topik", "menurut", "terhadap", "mengenai", "sebaiknya", "harus", "perlu",
    "bisa", "dapat", "akan", "tidak", "belum", "sudah", "lebih", "kurang",
    "sangat", "paling", "para", "bagi", "untuk", "dalam", "dengan", "atau",
    # kata generik dari ekor kalimat topik yang sering menyesatkan
    "usul", "usulan", "masyarakat", "berdasarkan", "kami", "warga",
    # kata generik tambahan untuk filter query
    "jenis", "macam", "bentuk", "layanan",
})


def _topic_keywords(topik: str) -> set[str]:
    """Content word topik tanpa kata umum — fokus ke kata yang benar-benar khas."""
    words = _extract_content_words(topik)
    specific = {w for w in words if w not in _GENERIC_TOPIC_WORDS}
    return specific or words


# ---------------------------------------------------------------------------
# Google News Search Query Generator
# ---------------------------------------------------------------------------

def _extract_kata_wajib(topik: str, queries: list[str]) -> list[str]:
    """
    Ekstrak 2-4 istilah inti (kata wajib) sebagai ALTERNATIF.
    Mencari bigram/trigram spesifik dari topik yang muncul di query.
    Fallback: bigram paling spesifik dari topik.
    """
    # Kumpulkan semua token dari query
    all_tokens = []
    for q in queries:
        all_tokens.extend(q.lower().split())
    
    # Cari bigram dari topik yang muncul di query
    topik_tokens = _extract_content_words(topik)
    topik_tokens = [t for t in topik_tokens if t not in _GENERIC_TOPIC_WORDS]
    
    alternatives = []
    
    # Cari bigram (2 kata) dari topik_tokens yang berurutan
    for i in range(len(topik_tokens) - 1):
        bg = topik_tokens[i] + " " + topik_tokens[i + 1]
        # Cek apakah bigram ini (atau stem-nya) muncul di query
        for tok in all_tokens:
            if tok.startswith(topik_tokens[i][:4]) or tok.startswith(topik_tokens[i+1][:4]):
                alternatives.append(bg)
                break
    
    # Cari trigram (3 kata) jika belum cukup
    if len(alternatives) < 2:
        for i in range(len(topik_tokens) - 2):
            tg = topik_tokens[i] + " " + topik_tokens[i + 1] + " " + topik_tokens[i + 2]
            for tok in all_tokens:
                if tok.startswith(topik_tokens[i][:4]):
                    alternatives.append(tg)
                    break
    
    # Tambahkan kata tunggal spesifik dari topik (panjang >= 5)
    for t in topik_tokens:
        if len(t) >= 5 and t not in [a.split()[0] for a in alternatives]:
            alternatives.append(t)
    
    # Uniq, max 4
    seen = set()
    uniq = []
    for a in alternatives:
        if a not in seen:
            seen.add(a)
            uniq.append(a)
    return uniq[:4]


def buat_query_pencarian(topik: str) -> dict:
    """
    Bangun 2-4 query pendek (2-4 kata kunci) untuk Google News RSS search.
    Pakai LLM (call_llm) dengan fallback rule-based dari _topic_keywords.

    Args:
        topik: Topik simulasi (kalimat penuh).

    Returns:
        Dict dengan keys:
        - "queries": list[str] max 3, siap untuk URL-encode ke Google News
        - "kata_wajib": list[str] 2-4 alternatif istilah inti (singkatan, kepanjangan, sebutan populer)
    """
    # Coba LLM dulu
    try:
        from backend.llm import call_llm
    except Exception:
        call_llm = None

    system_prompt = (
        "Kamu menghasilkan query pencarian Google News untuk topik kebijakan Indonesia. "
        "Aturan keras:\n"
        "1. Output HANYA JSON object dengan key \"queries\" dan \"kata_wajib\", tanpa teks lain.\n"
        "2. \"queries\": array string, max 3, tiap query 2-4 kata kunci pendek (bukan kalimat).\n"
        "3. Hapus kata generik: pemerintah, program, kebijakan, aturan, dampak, solusi, "
        "langkah, upaya, masalah, isu, topik, menurut, terhadap, mengenai, jenis, macam, bentuk, layanan.\n"
        "4. Fokus pada entitas spesifik, nama program, angka, singkatan, atau aksi konkret.\n"
        "5. \"kata_wajib\": array 2-4 string, alternatif istilah inti: singkatan, kepanjangan, "
        "sebutan populer. Contoh PTKP: [\"ptkp\", \"penghasilan tidak kena pajak\", "
        "\"batas penghasilan bebas pajak\", \"batas gaji bebas pajak\"]. "
        "Contok hak cipta: [\"hak cipta\", \"pencatatan ciptaan\", \"kekayaan intelektual\"].\n"
        "6. Setiap query HARUS mengandung minimal 1 token dari kata_wajib (setelah stem). "
        "Query yang tidak mengandung token kata_wajib akan dibuang.\n"
        "Contoh: topik 'Pemerintah menggratiskan biaya pendaftaran 19 jenis hak cipta' -> "
        '{"queries": ["pendaftaran hak cipta gratis", "PNBP hak cipta 19 jenis", "Kemenkum hak cipta gratis"], '
        '"kata_wajib": ["hak cipta", "pencatatan ciptaan", "kekayaan intelektual"]}'
    )
    user_prompt = f"Topik: {topik}"

    if call_llm:
        try:
            raw = call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=300,
                use_analysis_chain=False,
                use_cache=True,
                response_format={"type": "json_object"},
            )
            import json
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                queries = parsed.get("queries", [])
                kata_wajib = parsed.get("kata_wajib", [])
            else:
                queries = parsed
                kata_wajib = []
            if isinstance(queries, list):
                # Clean and validate queries
                cleaned = []
                for q in queries:
                    q = str(q).strip()
                    if 2 <= len(q.split()) <= 4 and len(q) <= 60:
                        cleaned.append(q)
                if cleaned:
                    # Ensure kata_wajib is list of strings
                    if isinstance(kata_wajib, list):
                        kw_clean = [str(k).strip().lower() for k in kata_wajib if str(k).strip()]
                        kw_clean = kw_clean[:4]
                    else:
                        kw_clean = _extract_kata_wajib(topik, cleaned)
                    # BUANG query yang tidak mengandung token apa pun dari kata_wajib
                    final_queries = []
                    for q in cleaned:
                        q_tokens = set(q.lower().split())
                        has_wajib_token = False
                        for kw in kw_clean:
                            kw_parts = kw.split()
                            if len(kw_parts) == 1:
                                if _stem_id(kw_parts[0]) in {_stem_id(t) for t in q_tokens}:
                                    has_wajib_token = True
                                    break
                            else:
                                # Frasa: cek apakah semua token frasa ada di query
                                if all(_stem_id(p) in {_stem_id(t) for t in q_tokens} for p in kw_parts):
                                    has_wajib_token = True
                                    break
                        if has_wajib_token:
                            final_queries.append(q)
                        else:
                            print(f"[SOURCES] buat_query_pencarian dropped query (no kata_wajib token): {q!r}")
                    if not final_queries:
                        final_queries = cleaned[:1]  # fallback: keep at least 1

                    # Pastikan minimal 2 query: jika LLM hanya return 1, buat query kedua
                    # Query kedua = kata_wajib[0] + satu kata kunci spesifik non-generik dari topik
                    if len(final_queries) == 1 and kw_clean:
                        first_wajib = kw_clean[0]
                        # Cari kata kunci spesifik dari topik (bukan generik, bukan kata_wajib)
                        topic_kw = _topic_keywords(topik)
                        specific_kw = [w for w in topic_kw if w not in _GENERIC_TOPIC_WORDS and w not in first_wajib]
                        if specific_kw:
                            second_query = f"{first_wajib} {specific_kw[0]}"
                            if second_query != final_queries[0]:
                                final_queries.append(second_query)
                                print(f"[SOURCES] buat_query_pencarian auto-generated second query: {second_query!r}")

                    print(f"[SOURCES] buat_query_pencarian LLM queries={final_queries} kata_wajib={kw_clean}")
                    return {"queries": final_queries[:3], "kata_wajib": kw_clean}
        except Exception as e:
            print(f"[SOURCES] buat_query_pencarian LLM error={type(e).__name__}: {e}, fallback rule-based")

    # Fallback rule-based: ambil kata kunci terkuat dari _topic_keywords
    keywords = sorted(_topic_keywords(topik), key=lambda w: -len(w))
    queries = []
    if len(keywords) >= 2:
        queries.append(" ".join(keywords[:2]))
    if len(keywords) >= 3:
        queries.append(" ".join(keywords[:3]))
    if len(keywords) >= 4:
        queries.append(" ".join(keywords[1:3]))  # variasi
    queries = [q for q in queries if q][:3]
    kata_wajib = _extract_kata_wajib(topik, queries) if queries else (keywords[:1] if keywords else [])
    print(f"[SOURCES] buat_query_pencarian rule-based queries={queries} kata_wajib={kata_wajib}")
    return {"queries": queries, "kata_wajib": kata_wajib}


# Kata sifat/penilaian yang terlalu lemah buat jadi satu-satunya alasan cocok.
_WEAK_ANCHOR_WORDS = frozenset({
    "gratis", "tepat", "sasaran", "baik", "buruk", "besar", "kecil", "baru",
    "lama", "tinggi", "rendah", "naik", "turun", "naiknya", "kenaikan",
    "meningkat", "menurun", "menguntungkan", "merugikan", "penting", "cukup",
    "layak", "efektif", "efisien", "sesuai", "berhasil", "gagal",
})


def _stem_id(kata: str) -> str:
    """Stemming ringan untuk pencocokan kata kunci rule-based tanpa dependency baru.
    Buang awalan me-/meng-/men-/mem-/di-/ke-/pe-/per-/ber-/ter- dan akhiran -kan/-an/-i/-nya.
    Panjang akar minimal 3 huruf.
    """
    kata = kata.lower().strip()
    if len(kata) < 3:
        return kata

    stemmed = kata
    
    # 1. Buang awalan
    if stemmed.startswith(("meng", "mem", "men", "per", "ber", "ter")):
        if stemmed.startswith("men") and len(stemmed) > 3 and stemmed[3] in "aeiou":
            stemmed = stemmed[2:]  # me- + n...
        elif stemmed.startswith("meng"):
            stemmed = stemmed[4:]
        elif stemmed.startswith(("mem", "men", "per", "ber", "ter")):
            stemmed = stemmed[3:]
    elif stemmed.startswith(("me", "di", "ke", "pe")):
        stemmed = stemmed[2:]

    # 2. Buang akhiran: -nya, -kan, -an, -i
    if stemmed.endswith("nya") and len(stemmed) - 3 >= 3:
        stemmed = stemmed[:-3]
    elif stemmed.endswith("kan") and len(stemmed) - 3 >= 3:
        if stemmed.endswith("aikan"):
            stemmed = stemmed[:-2]  # -an
        else:
            stemmed = stemmed[:-3]
    elif stemmed.endswith("an") and len(stemmed) - 2 >= 3:
        stemmed = stemmed[:-2]
    elif stemmed.endswith("i") and len(stemmed) - 1 >= 3:
        stemmed = stemmed[:-1]

    return stemmed if len(stemmed) >= 3 else kata


# Kata yang sering muncul di berita promo dan bukan penanda topik.
_ANCHOR_BLOCKLIST = frozenset({"pendaftaran", "daftar", "ndaftar"})


def _extract_anchor_keywords(query_keywords: set[str]) -> set[str]:
    """Ambil kata kunci jangkar (anchor) dari query keywords.
    Jangkar = kata kunci yang cukup spesifik, BUKAN generik/lemah.
    Filter: bentuk asli maupun akar stemming tidak boleh ada di daftar kata
    umum/lemah, panjang akar >= 4, bukan angka.
    """
    anchors = set()
    for kw in query_keywords:
        kw_raw = kw.strip().lower()
        kw_clean = _stem_id(kw_raw)
        if (len(kw_clean) >= 4
                and kw_raw not in _GENERIC_TOPIC_WORDS
                and kw_clean not in _GENERIC_TOPIC_WORDS
                and kw_raw not in _WEAK_ANCHOR_WORDS
                and kw_clean not in _WEAK_ANCHOR_WORDS
                and kw_raw not in _ANCHOR_BLOCKLIST
                and kw_clean not in _ANCHOR_BLOCKLIST
                and not kw_clean.isdigit()):
            anchors.add(kw_clean)
    return anchors


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
    print(f"[SOURCES] _hitung_relevansi_tfidf start topik={topik!r} items={len(items)} threshold={SIMILARITY_THRESHOLD:.2f} sklearn_ok={_SKLEARN_OK}")
    if not items:
        return []

    if not _SKLEARN_OK:
        print(f"[SOURCES] _hitung_relevansi_tfidf sklearn_not_available fallback_keyword")
        return _hitung_relevansi_keyword(topik, items, maks)

    # Build corpus: topic first, then each item's text.
    # Pakai kata kunci topik saja (tanpa "apakah/tidak/pemerintah"), supaya
    # kemiripan tidak tenggelam oleh kata umum.
    topic_content = _topic_keywords(topik)
    topic_clean = _bersih_teks(" ".join(sorted(topic_content)) if topic_content else topik)
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
        # Kata umum sudah dibuang dari topic_content. Minimal harus ada satu
        # kata kunci kuat yang sama, supaya berita cuma cocok di "gratis"
        # atau "pemerintah" tidak lolos.
        strong_anchors = topic_content - _WEAK_ANCHOR_WORDS

        passed = []
        for it in items:
            if it.get("relevansi", 0) < SIMILARITY_THRESHOLD:
                continue
            if topic_content:
                article_text = it.get("judul", "") + " " + it.get("ringkasan", "")
                overlap = topic_content & _extract_content_words(article_text)
                if not overlap:
                    continue
                if len(overlap) < 2 and strong_anchors and not (overlap & strong_anchors):
                    continue
            passed.append(it)

        print(f"[SOURCES] tfidf_done topic_keywords={sorted(topic_content)} threshold={SIMILARITY_THRESHOLD:.2f} passed={len(passed)}")
        if passed:
            top5 = [(p.get("relevansi", 0), p.get("judul", "")[:80], p.get("sumber", "")) for p in passed[:5]]
            for score, title, src in top5:
                print(f"[SOURCES]   top relevansi={score:.4f} sumber={src} judul={title}")

        return passed[:maks]

    except Exception as exc:
        print(f"[SOURCES] _hitung_relevansi_tfidf exception error={type(exc).__name__}: {exc}, fallback_keyword")
        return _hitung_relevansi_keyword(topik, items, maks)


def _hitung_relevansi_keyword(topik: str, items: list[dict], maks: int = 15) -> list[dict]:
    """Fallback: keyword counting sederhana."""
    print(f"[SOURCES] _hitung_relevansi_keyword start topik={topik!r} items={len(items)}")
    kata_kunci = [k.lower() for k in topik.split() if len(k) > 3]
    print(f"[SOURCES] keyword_fallback kata_kunci={kata_kunci}")
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
    print(f"[SOURCES] keyword_fallback hasil={len(hasil)}")
    return hasil[:maks]


# ---------------------------------------------------------------------------
# Fetch News (RSS)
# ---------------------------------------------------------------------------

def fetch_google_news_search(query: str, errors: list | None = None) -> list[dict]:
    """
    Ambil hasil Google News RSS search untuk satu query.
    URL: https://news.google.com/rss/search?q=<QUERY>&hl=id&gl=ID&ceid=ID:id

    Returns:
        List artikel dict dengan sumber="google_news_search" dan query_origin.
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=id&gl=ID&ceid=ID:id"
    print(f"[SOURCES] google_news_search query={query!r} url={url}")
    xml = _fetch(url, errors=errors)
    if not xml:
        print(f"[SOURCES] google_news_search fetch_failed query={query!r}")
        return []
    # Parse dengan _parse_rss yang sudah ada
    articles = _parse_rss(xml, "google_news_search")
    # Tandai sumber dan query asal
    for art in articles:
        art["sumber"] = "google_news_search"
        art["query_origin"] = query
    print(f"[SOURCES] google_news_search parsed query={query!r} items={len(articles)}")
    return articles


def fetch_berita(topik: str, maks_per_sumber: int = 3) -> dict:
    """
    Ambil berita terkini dari semua RSS source + Google News search.
    Filter relevan dengan TF-IDF (fallback keyword counting).

    Returns dict:
        {"articles": list[dict], "total_unik": int, "total_filtered": int,
         "sumber_status": str, "sumber_pesan": str, "sumber_peringatan": list[str]}
          articles          — artikel yg lolos threshold (sorted by relevance desc)
          total_unik        — total semua kandidat UNIK sebelum filter
          total_filtered    — jumlah artikel yg lolos threshold
          sumber_status     — "ok" | "kosong" | "gagal"
          sumber_pesan      — pesan singkat kondisi sumber
          sumber_peringatan — ringkasan sumber yang gagal, mis. ["rss.tempo.co: HTTP 403"]
    """
    import re
    print(f"[SOURCES] fetch_berita start topik={topik!r} sources={len(RSS_SOURCES)}")
    semua = []
    raw_counts = {}
    errors: list[str] = []

    def _status_sumber(jumlah_artikel: int) -> tuple[str, str, list[str]]:
        """Artikel final menang atas kegagalan sebagian sumber."""
        peringatan = [_ringkas_error(e) for e in errors]
        if jumlah_artikel > 0:
            if jumlah_artikel < 3:
                return "sedikit", f"Hanya {jumlah_artikel} artikel lolos filter (kurang dari 3).", peringatan
            return "ok", f"{jumlah_artikel} artikel lolos filter.", peringatan
        if errors:
            return "gagal", f"{len(errors)} sumber gagal: {errors[0][:160]}", peringatan
        return "kosong", "Sumber berhasil diambil tetapi tidak ada artikel yang lolos filter.", peringatan

    # 1. Portal RSS tradisional
    for src in RSS_SOURCES:
        if not src.get("enabled", True):
            print(f"[SOURCES] skip_disabled sumber={src['nama']} url={src['url']}")
            continue
        url = src["url"]
        print(f"[SOURCES] fetching url={url} sumber={src['nama']}")
        xml = _fetch(url, errors=errors)
        if not xml:
            print(f"[SOURCES] fetch_failed url={url} sumber={src['nama']}")
            continue
        articles = _parse_rss(xml, src["nama"])
        raw_counts[src["nama"]] = len(articles)
        print(f"[SOURCES] parsed sumber={src['nama']} items={len(articles)}")
        semua.extend(articles)

    # 2. Google News Search untuk tiap query
    query_result = buat_query_pencarian(topik)
    queries = query_result["queries"]
    kata_wajib = query_result.get("kata_wajib", [])
    print(f"[SOURCES] buat_query_pencarian queries={queries} kata_wajib={kata_wajib}")
    google_items = []
    for query in queries:
        g_items = fetch_google_news_search(query, errors=errors)
        google_items.extend(g_items)
    if google_items:
        raw_counts["google_news_search"] = len(google_items)
        print(f"[SOURCES] google_news_search total_items={len(google_items)} queries={queries}")
        semua.extend(google_items)

    print(f"[SOURCES] raw_items={sum(raw_counts.values())} per_source={raw_counts}")

    # Dedup by ID
    seen = set()
    unik = []
    for art in semua:
        if art["id"] not in seen:
            seen.add(art["id"])
            unik.append(art)

    total_unik = len(unik)
    print(f"[SOURCES] after_dedup unik={total_unik}")
    if not unik:
        sumber_status, sumber_pesan, sumber_peringatan = _status_sumber(0)
        print(f"[SOURCES] sumber_status={sumber_status} pesan={sumber_pesan} peringatan={sumber_peringatan}")
        return {
            "articles": [], "total_unik": 0, "total_filtered": 0,
            "sumber_status": sumber_status,
            "sumber_pesan": sumber_pesan,
            "sumber_peringatan": sumber_peringatan,
        }

    # Pisahkan item portal dan google_news_search
    portal_items = [a for a in unik if a.get("sumber") != "google_news_search"]
    google_items = [a for a in unik if a.get("sumber") == "google_news_search"]

    # Filter portal items dengan TF-IDF + threshold (seperti biasa)
    portal_filtered = _hitung_relevansi_tfidf(topik, portal_items, maks=15)
    print(f"[SOURCES] portal after_relevance_filter={len(portal_filtered)} threshold={SIMILARITY_THRESHOLD:.2f}")

    # Ambil query keywords dan anchor keywords SEBELUM filter portal (dibutuhkan oleh keduanya)
    # SEMUA kata dari queries jadi query_keywords (bukan 3 pertama)
    query_keywords = set()
    for q in queries:
        for kw in q.split():
            if len(kw) > 2:
                query_keywords.add(kw.lower())
    print(f"[SOURCES] shared query_keywords={sorted(query_keywords)}")

    # Ekstrak anchor keywords (spesifik, bukan generik/lemah)
    anchor_keywords = _extract_anchor_keywords(query_keywords)
    print(f"[SOURCES] shared anchor_keywords={sorted(anchor_keywords)}")

    # Terapkan anchor filter yang sama ke portal: min 1 anchor + min 2 query keyword
    portal_kept = []
    portal_removed_no_anchor = 0
    portal_removed_no_kw = 0
    for art in portal_filtered:
        judul_lower = art.get("judul", "").lower()
        has_anchor = any(ak in judul_lower for ak in anchor_keywords) if anchor_keywords else False
        kw_matches = [kw for kw in query_keywords if kw in judul_lower]
        kw_count = len(kw_matches)

        if not has_anchor:
            print(f"[SOURCES] portal removed (no anchor) judul={art.get('judul','')[:80]} | sumber={art.get('sumber','')}")
            portal_removed_no_anchor += 1
            continue
        if kw_count < 2:
            print(f"[SOURCES] portal removed (kw_count={kw_count} < 2) judul={art.get('judul','')[:80]} | sumber={art.get('sumber','')}")
            portal_removed_no_kw += 1
            continue
        portal_kept.append(art)

    print(f"[SOURCES] portal anchor_filter: kept={len(portal_kept)} removed_no_anchor={portal_removed_no_anchor} removed_no_kw={portal_removed_no_kw} from {len(portal_filtered)}")
    portal_filtered = portal_kept

    # Google News items: filter dengan kata_wajib + query keywords + tanggal
    # kata_wajib menggantikan anchor: lolos bila cocok SALAH SATU alternatif
    # DAN minimal 1 kata kunci non-generik lain dari query cocok.
    print(f"[SOURCES] google_news query_keywords={sorted(query_keywords)}")
    print(f"[SOURCES] google_news kata_wajib={kata_wajib}")
    print(f"[SOURCES] google_news anchor_keywords (logging only)={sorted(anchor_keywords)}")

    # Cutoff tanggal
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=GOOGLE_NEWS_MAX_AGE_DAYS)
    print(f"[SOURCES] google_news date_cutoff={cutoff_dt.date()} (max {GOOGLE_NEWS_MAX_AGE_DAYS} hari)")

    google_filtered = []
    removed_no_wajib = 0
    removed_no_kw = 0
    removed_old = 0
    tanggal_map: dict[int, Optional[datetime]] = {}

    def _stem_tokens(text: str) -> set[str]:
        """Token judul dinormalkan ke akar supaya 'kenaikan' cocok dengan 'naik'."""
        return {_stem_id(tok) for tok in re.findall(r"[a-z0-9]+", text.lower())}

    # Siapkan kata_wajib stems untuk pencocokan
    # Kata_wajib bisa berupa frasa 2 kata ("hak cipta") atau kata tunggal ("ptkp")
    def _check_kata_wajib(judul_stem: set[str], judul_lower: str) -> bool:
        """Cek apakah judul mengandung minimal 1 kata_wajib.
        - Kata tunggal: cocok jika stem ada di judul_stem
        - Frasa 2 kata: cocok jika kedua kata (setelah stem) ada di judul_stem
        - Frasa >2 kata: cek substring di judul_lower
        """
        if not kata_wajib:
            return True  # tidak ada kata_wajib berarti tidak difilter
        for kw in kata_wajib:
            kw_lower = kw.lower().strip()
            kw_parts = kw_lower.split()
            if len(kw_parts) == 1:
                if _stem_id(kw_parts[0]) in judul_stem:
                    return True
            elif len(kw_parts) == 2:
                # Frasa 2 kata: kedua kata harus ada (setelah stem)
                if _stem_id(kw_parts[0]) in judul_stem and _stem_id(kw_parts[1]) in judul_stem:
                    return True
            else:
                # Frasa >2 kata: cek substring di judul_lower
                if kw_lower in judul_lower:
                    return True
        return False

    # Query keywords non-generik (buang yang ada di _GENERIC_TOPIC_WORDS)
    non_generic_query_kw = {kw for kw in query_keywords if kw not in _GENERIC_TOPIC_WORDS}

    # Tentukan kata_wajib yang "kuat" (frasa >= 2 kata ATAU singkatan unik uppercase 3-5 char)
    # Item yang cocok kata_wajib kuat lolos tanpa min_kw per query dan tanpa kata kunci tambahan
    def _is_strong_wajib(kw: str) -> bool:
        parts = kw.lower().split()
        if len(parts) >= 2:
            return True  # frasa 2+ kata
        # singkatan unik: huruf besar semua (3-5 char) ATAU singkatan known lowercase
        # known Indonesian policy abbreviations (case-insensitive)
        known_abbrev = {"ptkp", "kpu", "dpr", "mpr", "bpk", "kpk", "ban", "bkn", "bakamla"}
        if len(kw) >= 3 and len(kw) <= 5 and (kw.isupper() or kw.lower() in known_abbrev):
            return True
        return False

    strong_wajib_set = {kw for kw in kata_wajib if _is_strong_wajib(kw)}

    for art in google_items:
        judul = art.get("judul", "")
        judul_lower = judul.lower()
        judul_stem = _stem_tokens(judul)

        # Cek kata_wajib (wajib ada di judul) - INI GANTI ANCHOR
        has_wajib = _check_kata_wajib(judul_stem, judul_lower)

        # Cek apakah judul cocok dengan KATA_WAJIB KUAT (frasa atau singkatan)
        # Jika ya, lolos tanpa min_kw per query dan tanpa kata kunci tambahan
        matched_strong_wajib = False
        for kw in strong_wajib_set:
            kw_lower = kw.lower().strip()
            kw_parts = kw_lower.split()
            if len(kw_parts) == 1:
                if _stem_id(kw_parts[0]) in judul_stem:
                    matched_strong_wajib = True
                    break
            elif len(kw_parts) == 2:
                if _stem_id(kw_parts[0]) in judul_stem and _stem_id(kw_parts[1]) in judul_stem:
                    matched_strong_wajib = True
                    break
            else:
                if kw_lower in judul_lower:
                    matched_strong_wajib = True
                    break

        # Cek minimal 1 query keyword non-generik (selain kata_wajib)
        kw_matches = [kw for kw in non_generic_query_kw if kw in judul_lower]
        kw_count = len(kw_matches)

        # Aturan per-query: minimal ceil(jumlah kata kunci query / 2) harus cocok
        q_kws = [kw for kw in art.get("query_origin", "").lower().split() if len(kw) > 2]
        q_stems = {_stem_id(kw) for kw in q_kws}
        matched = q_stems & judul_stem
        min_kw = math.ceil(len(q_kws) / 2) if q_kws else 0

        # Parse tanggal; yang disimpan di artikel hanya string ISO
        pub_dt = _parse_rss_date(art.get("tanggal", ""))
        tanggal_map[id(art)] = pub_dt
        art["tanggal_iso"] = pub_dt.isoformat() if pub_dt else ""
        is_recent = pub_dt is not None and pub_dt >= cutoff_dt

        if not has_wajib:
            print(f"[SOURCES] google_news removed (no kata_wajib) query={art.get('query_origin','')!r} kata_wajib={kata_wajib} judul={judul[:80]}")
            removed_no_wajib += 1
            continue

        # JIKA cocok kata_wajib KUAT (frasa >= 2 kata atau singkatan PTKP):
        # lolos tanpa min_kw per query DAN tanpa syarat kw_count >= 1
        if matched_strong_wajib:
            google_filtered.append(art)
            continue

        # JIKA KHAT kata_wajib biasa (satu kata): butuh kw_count >= 1 DAN min_kw
        if kw_count < 1:
            print(f"[SOURCES] google_news removed (no other query kw) query={art.get('query_origin','')!r} non_generic_kw={sorted(non_generic_query_kw)} judul={judul[:80]}")
            removed_no_kw += 1
            continue
        if len(matched) < min_kw:
            print(
                f"[SOURCES] google_news removed (kw {len(matched)}/{min_kw}) "
                f"query={art.get('query_origin','')!r} cocok={sorted(matched)} "
                f"judul={judul[:80]}"
            )
            removed_no_kw += 1
            continue

        google_filtered.append(art)

    print(f"[SOURCES] google_news filtered: kept={len(google_filtered)} removed_no_wajib={removed_no_wajib} removed_no_kw={removed_no_kw} removed_old={removed_old} from {len(google_items)}")

    # ====== Diversity Selection for Google News ======
    from difflib import SequenceMatcher

    def _normalize_title_for_dedup(title: str) -> str:
        """Hapus nama kantor wilayah/daerah dari judul untuk dedup."""
        import re
        # Hapus pola: "Kemenkum X", "Kanwil X", "X Barat", "X Timur", "X Utara", "X Selatan", "X Tengah"
        # "Kaltim", "DIY", "Sulteng", "Kalbar", "Jatim", "Lampung", "Bali", "Pontianak", "Malang", "Palu"
        normalized = re.sub(r'\b(Kemenkum|Kanwil|Kemenkumham)\s+[A-Za-z]+\b', 'Kemenkum', title, flags=re.IGNORECASE)
        normalized = re.sub(r'\b(Kaltim|DIY|Sulteng|Kalbar|Jatim|Lampung|Bali|Pontianak|Malang|Palu|Banten|Jabar|Jateng|Jateng|NTB|NTT|Papua|Sulawesi|Sumatera|Kalimantan)\b', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\b(buka|gelar|ajak|dorong|dampingi|perluas|gratis|gratis|gratis)\b', '', normalized, flags=re.IGNORECASE)
        # Hapus kata generik pendek
        normalized = re.sub(r'\b(untuk|dan|di|ke|dari|yang|dengan|pada|adalah|akan|telah|sudah|bisa|dapat|tidak|ada|juga|atau|karena|oleh|sebagai|serta|saat|dalam|secara|lebih|sangat|antara|setelah|seperti|hanya|mereka|kami|kita|saya|dia|ia|anda|bahwa|namun|tetapi|sedangkan|sementara|jika|kalau|maka|sehingga|mengapa|bagaimana|apa|siapa|mana|kapan|banyak|beberapa|seluruh|semua|para|si|sang|para|ia|pun|pernah|belum|agar|supaya|sebab|meski|walaupun|biar|hendak|mau|ingin)\b', '', normalized, flags=re.IGNORECASE)
        # Normalisasi whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized



    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def _priority_keywords(title: str) -> int:
        """Skor prioritas untuk keyword khusus."""
        priority_terms = ['pengamat', 'kritik', 'royalti', 'pp', 'pnbp', 'menkum', 'hak cipta', 'kekayaan intelektual', 'ki']
        title_lower = title.lower()
        score = sum(1 for term in priority_terms if term in title_lower)
        return score

    # 1. Dedup berdasarkan judul yang dinormalisasi
    # Urutkan berdasarkan tanggal terbaru dulu
    google_filtered.sort(key=lambda a: tanggal_map.get(id(a)) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    # Dedup: first pass - exact normalized title match (existing logic)
    seen_titles = {}  # normalized_title -> item terbaru
    dedup_removed = 0
    unique_items = []

    for art in google_filtered:
        norm_title = _normalize_title_for_dedup(art.get("judul", ""))
        if norm_title in seen_titles:
            # Sudah ada, bandingkan tanggal
            existing = seen_titles[norm_title]
            art_dt = tanggal_map.get(id(art))
            existing_dt = tanggal_map.get(id(existing))
            if art_dt and existing_dt:
                if art_dt > existing_dt:
                    print(f"[SOURCES] google_news dedup removed (newer kept): {art.get('judul','')[:80]} (existing: {existing.get('judul','')[:60]})")
                    dedup_removed += 1
                    seen_titles[norm_title] = art
                else:
                    print(f"[SOURCES] google_news dedup removed (older): {art.get('judul','')[:80]}")
                    dedup_removed += 1
            else:
                print(f"[SOURCES] google_news dedup removed (no date): {art.get('judul','')[:80]}")
                dedup_removed += 1
        else:
            seen_titles[norm_title] = art
            unique_items.append(art)

    print(f"[SOURCES] google_news dedup: kept={len(unique_items)} removed={dedup_removed}")

    # Helper functions for cross-dedup (must be defined before use)
    def _domain_key(art: dict) -> str:
        """Domain induk; item tanpa domain jelas dapat kunci unik sendiri."""
        d = _domain_from_source(art.get("sumber", ""), art.get("judul", ""), art.get("source_url", ""))
        if not d or d == "google_news_search":
            return f"unknown:{art.get('id', '')}"
        return d

    def _is_aggregator_domain(domain: str) -> bool:
        agg = {"google_news_search", "news.google.com", "feed", "rss"}
        return domain in agg or domain.startswith("unknown:")

    # Dedup: second pass - cross-domain identical core title
    # Jika dua item punya judul identik setelah buang akhiran "- Media", simpan satu
    # Prioritas: non-agregator domain, lalu yang lebih awal
    core_title_map = {}  # core_title -> (item, domain)
    cross_dedup_removed = 0
    final_items = []

    for art in unique_items:
        title = art.get("judul", "")
        # Extract core title: remove trailing "- Media Name" or "| Media Name"
        import re
        core = re.sub(r'\s*[-|]\s*[A-Za-z0-9.\s]+\s*$', '', title).strip()
        domain = _domain_key(art)

        if core in core_title_map:
            existing_art, existing_domain = core_title_map[core]
            # Prefer non-aggregator, then earlier date
            existing_is_agg = _is_aggregator_domain(existing_domain)
            current_is_agg = _is_aggregator_domain(domain)

            if existing_is_agg and not current_is_agg:
                # Replace with non-aggregator
                print(f"[SOURCES] google_news cross-dedup replaced aggregator: {existing_art.get('judul','')[:60]} -> {art.get('judul','')[:60]}")
                core_title_map[core] = (art, domain)
                cross_dedup_removed += 1
            elif not existing_is_agg and current_is_agg:
                # Keep existing non-aggregator
                print(f"[SOURCES] google_news cross-dedup kept non-aggregator: {existing_art.get('judul','')[:60]}")
                cross_dedup_removed += 1
            else:
                # Both same type, keep earlier date
                existing_dt = tanggal_map.get(id(existing_art))
                current_dt = tanggal_map.get(id(art))
                if existing_dt and current_dt and current_dt < existing_dt:
                    core_title_map[core] = (art, domain)
                    print(f"[SOURCES] google_news cross-dedup replaced older: {existing_art.get('judul','')[:60]} -> {art.get('judul','')[:60]}")
                cross_dedup_removed += 1
        else:
            core_title_map[core] = (art, domain)
            final_items.append(art)

    if cross_dedup_removed:
        print(f"[SOURCES] google_news cross-dedup removed={cross_dedup_removed}")

    unique_items = final_items

    print(f"[SOURCES] google_news dedup: kept={len(unique_items)} removed={dedup_removed + cross_dedup_removed}")

    # 2. Seleksi akhir: 8 item <30 hari terbaru + 4 item >=30 hari skor tertinggi
    now_utc    = datetime.now(timezone.utc)
    cutoff_30  = now_utc - timedelta(days=30)
    cutoff_120 = now_utc - timedelta(days=GOOGLE_NEWS_MAX_AGE_DAYS)

    def _domain_cap(domain: str) -> int:
        return 3 if _is_kemenkum_domain(domain) else 2

    pool = [a for a in unique_items if tanggal_map.get(id(a)) and tanggal_map[id(a)] >= cutoff_120]
    recent_pool = sorted(
        [a for a in pool if tanggal_map[id(a)] >= cutoff_30],
        key=lambda a: tanggal_map[id(a)],
        reverse=True,
    )
    older_pool = sorted(
        [a for a in pool if tanggal_map[id(a)] < cutoff_30],
        key=lambda a: (-_priority_keywords(a.get("judul", "")), -tanggal_map[id(a)].timestamp()),
    )

    selected = []
    selected_ids = set()
    domain_counts = {}
    drop_reason = {}

    def _take(candidates: list, kuota: int) -> None:
        for art in candidates:
            if kuota <= 0:
                return
            if id(art) in selected_ids:
                continue
            domain = _domain_key(art)
            if domain_counts.get(domain, 0) >= _domain_cap(domain):
                drop_reason[id(art)] = f"domain_cap: _domain_cap({domain})={_domain_cap(domain)}"
                continue
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            selected.append(art)
            selected_ids.add(id(art))
            kuota -= 1

    _take(recent_pool, 8)
    for art in recent_pool:
        if id(art) not in selected_ids and id(art) not in drop_reason:
            drop_reason[id(art)] = "kuota_habis: _take(recent_pool, 8)"

    _take(older_pool, 4)
    for art in older_pool:
        if id(art) not in selected_ids and id(art) not in drop_reason:
            drop_reason[id(art)] = "kuota_habis: _take(older_pool, 4)"

    # Kekurangan slot di salah satu kategori diisi kandidat berikutnya dari pool
    if len(selected) < 12:
        sisa = [a for a in recent_pool + older_pool if id(a) not in selected_ids]
        _take(sisa, 12 - len(selected))

    for art in pool:
        if id(art) not in selected_ids and id(art) not in drop_reason:
            drop_reason[id(art)] = "tidak_masuk_pool: _take(sisa, 12 - len(selected))"

    if len(pool) >= 12:
        assert len(selected) == 12, f"seleksi akhir harus 12 item, dapat {len(selected)}"
    for domain, count in domain_counts.items():
        assert count <= _domain_cap(domain), f"domain {domain} melebihi batas: {count}"

    # Kandidat skor tinggi yang tetap tidak masuk final: sebutkan aturannya
    for art in pool:
        prio = _priority_keywords(art.get("judul", ""))
        if id(art) in selected_ids or prio < 3:
            continue
        print(
            f"[SOURCES] google_news WARNING high_priority_dropped skor={prio} "
            f"domain={_domain_key(art)} alasan={drop_reason.get(id(art), 'tidak diketahui')} "
            f"judul={art.get('judul','')[:80]}"
        )

    # Log yang dibuang
    for art in pool:
        if id(art) in selected_ids:
            continue
        age = (now_utc - tanggal_map[id(art)]).days
        print(
            f"[SOURCES] google_news diversity_removed: {art.get('judul','')[:80]} | age={age} days "
            f"| priority={_priority_keywords(art.get('judul',''))} | alasan={drop_reason.get(id(art), 'tidak diketahui')}"
        )

    google_filtered = selected

    recent_kept = len([a for a in google_filtered if tanggal_map[id(a)] >= cutoff_30])
    older_kept = len([a for a in google_filtered if cutoff_120 <= tanggal_map[id(a)] < cutoff_30])
    print(f"[SOURCES] google_news final_kept={len(google_filtered)} (recent={recent_kept}, older={older_kept})")

    # Log 3 kolom untuk 12 item Google News: judul | pubDate mentah | ISO
    print(f"[SOURCES] google_news date_verification (judul | pubDate_raw | parsed | domain_key | source_url):")
    for art in google_filtered:
        judul = art.get("judul", "")[:80]
        pub_raw = art.get("tanggal", "no-date")
        dt = tanggal_map.get(id(art))
        parsed_str = dt.date().isoformat() if dt else "no-date"
        domain_key = _domain_key(art)
        source_url = art.get("source_url", "")
        print(f"[SOURCES]   {judul} | {pub_raw} | {parsed_str} | {domain_key} | {source_url}")

    # Artikel portal juga diberi tanggal ISO agar payload seragam & JSON-safe
    for art in portal_filtered:
        if not art.get("tanggal_iso"):
            dt = _parse_rss_date(art.get("tanggal", ""))
            art["tanggal_iso"] = dt.isoformat() if dt else ""

    # Gabungkan: portal_filtered + google_filtered
    filtered = portal_filtered + google_filtered

    print(f"[SOURCES] after_relevance_filter total_filtered={len(filtered)} (portal={len(portal_filtered)}, google={len(google_filtered)})")
    if filtered:
        top5 = [(f.get("relevansi", 0), f.get("judul", "")[:80], f.get("sumber", "")) for f in filtered[:5]]
        for score, title, src in top5:
            print(f"[SOURCES]   top relevansi={score:.4f} sumber={src} judul={title}")
    sumber_status, sumber_pesan, sumber_peringatan = _status_sumber(len(filtered))
    print(f"[SOURCES] sumber_status={sumber_status} pesan={sumber_pesan} peringatan={sumber_peringatan}")

    return {
        "articles": filtered,
        "total_unik": total_unik,
        "total_filtered": len(filtered),
        "sumber_status": sumber_status,
        "sumber_pesan": sumber_pesan,
        "sumber_peringatan": sumber_peringatan,
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
    print(f"[SOURCES] query_dikirim={topik!r} force_refresh={force_refresh} topik_asli={topik_asli!r}")
    # ── Cache lookup ──────────────────────────────────────────────────────
    if not force_refresh:
        cached = _get_cached(topik)
        if cached:
            print(f"[SOURCES] cache_hit=true topik={topik!r}")
            cached["from_cache"] = True
            # Cache lama belum punya sumber_status/sumber_peringatan
            if "sumber_status" not in cached:
                cached["sumber_status"] = "ok" if cached.get("berita") else "kosong"
                cached["sumber_pesan"] = ""
            cached.setdefault("sumber_peringatan", [])
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
        else:
            print(f"[SOURCES] cache_hit=false topik={topik!r}")
    # ─────────────────────────────────────────────────────────────────────

    print(f"[SOURCES] fetching_rss start topik={topik!r}")
    # Fetch berita dari RSS — 0 biaya, 0 API key
    fetch_result = fetch_berita(topik)
    berita = fetch_result["articles"]
    total_unik = fetch_result["total_unik"]
    total_filtered = fetch_result["total_filtered"]
    sumber_status = fetch_result.get("sumber_status", "")
    sumber_pesan = fetch_result.get("sumber_pesan", "")
    sumber_peringatan = fetch_result.get("sumber_peringatan", [])

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
        "sumber_status":       sumber_status,
        "sumber_pesan":        sumber_pesan,
        "sumber_peringatan":   sumber_peringatan,
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
        except Exception as e:
            print(f"[SOURCES] cluster_articles_by_topic tfidf error={type(e).__name__}: {e}, fallback_jaccard")
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


