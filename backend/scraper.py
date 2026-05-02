# backend/scraper.py
# Data real gratis untuk VoxSwarm:
#   - RSS feed berita Indonesia (Kompas, Detik, BBC Indonesia, Tempo, Antara)
#   - Reddit via JSON API publik (tanpa OAuth, gratis)
#   - Fallback graceful jika semua sumber gagal
#   - Disk cache by topic hash (TTL configurable via CONTEXT_CACHE_TTL_MINUTES)

import re
import time
import json
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Konfigurasi sumber RSS — semua gratis, tidak butuh API key
# ---------------------------------------------------------------------------

RSS_SOURCES = [
    {"nama": "Kompas",        "url": "https://rss.kompas.com/rss/breakingnews.xml",         "bahasa": "id"},
    {"nama": "Detik",         "url": "https://feed.detik.com/detikcom-index",                "bahasa": "id"},
    {"nama": "BBC Indonesia", "url": "https://feeds.bbci.co.uk/indonesian/rss.xml",          "bahasa": "id"},
    {"nama": "Tempo",         "url": "https://rss.tempo.co/nasional",                        "bahasa": "id"},
    {"nama": "Antara",        "url": "https://www.antaranews.com/rss/terkini.xml",           "bahasa": "id"},
    {"nama": "CNN Indonesia", "url": "https://www.cnnindonesia.com/rss",                     "bahasa": "id"},
    {"nama": "Tirto",         "url": "https://tirto.id/rss",                                 "bahasa": "id"},
]

# Reddit — pakai JSON API publik (tidak butuh OAuth untuk read-only)
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
# Disk Cache Config
# ---------------------------------------------------------------------------

import os

_CACHE_DIR  = Path(__file__).parent / "data"
_CACHE_FILE = _CACHE_DIR / "context_cache.json"
_CACHE_TTL  = int(os.getenv("CONTEXT_CACHE_TTL_MINUTES", "30")) * 60   # detik
_CACHE_MAX  = int(os.getenv("CONTEXT_CACHE_MAX_ENTRIES", "100"))        # maks topik disimpan

_cache_lock = threading.Lock()
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _topic_key(topik: str) -> str:
    """Hash MD5 dari topik lowercase — jadi key cache."""
    return hashlib.md5(topik.strip().lower().encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    """Baca cache dari disk. Return {} jika file belum ada atau corrupt."""
    if not _CACHE_FILE.exists():
        return {}
    try:
        return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    """Tulis cache ke disk. Silent fail jika tidak bisa write."""
    try:
        _CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=None),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[Cache] Gagal simpan cache: {e}")


def _get_cached(topik: str) -> Optional[dict]:
    """
    Ambil konteks dari cache jika masih valid (belum expired).
    Return None jika miss atau TTL terlewat.
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

        # Trim: buang entri terlama jika cache terlalu besar
        if len(cache) > _CACHE_MAX:
            sorted_keys = sorted(cache, key=lambda k: cache[k].get("cached_at", 0))
            for old_key in sorted_keys[:len(cache) - _CACHE_MAX]:
                cache.pop(old_key, None)

        _save_cache(cache)


def clear_context_cache(topik: Optional[str] = None) -> int:
    """
    Hapus cache.
    - topik=None  → hapus semua
    - topik=str   → hapus hanya topik itu

    Return: jumlah entri yang dihapus.
    """
    with _cache_lock:
        cache = _load_cache()
        if topik is None:
            n = len(cache)
            _save_cache({})
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
        now   = time.time()
        valid = sum(1 for e in cache.values() if now - e.get("cached_at", 0) <= _CACHE_TTL)
        return {
            "total_entries": len(cache),
            "valid_entries": valid,
            "expired_entries": len(cache) - valid,
            "ttl_minutes": _CACHE_TTL // 60,
            "max_entries": _CACHE_MAX,
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


def fetch_berita(topik: str, maks_per_sumber: int = 3) -> list[dict]:
    """
    Ambil berita terkini dari semua RSS source.
    Filter yang relevan dengan topik (keyword matching sederhana).
    """
    kata_kunci = [k.lower() for k in topik.split() if len(k) > 3]
    semua = []

    for src in RSS_SOURCES:
        xml = _fetch(src["url"])
        if not xml:
            continue
        articles = _parse_rss(xml, src["nama"])

        relevan = []
        for art in articles:
            teks = (art["judul"] + " " + art["ringkasan"]).lower()
            skor = sum(1 for k in kata_kunci if k in teks)
            if skor > 0:
                art["relevansi"] = skor
                relevan.append(art)

        relevan.sort(key=lambda x: -x.get("relevansi", 0))
        semua.extend(relevan[:maks_per_sumber])

    semua.sort(key=lambda x: -x.get("relevansi", 0))
    seen  = set()
    hasil = []
    for art in semua:
        if art["id"] not in seen:
            seen.add(art["id"])
            hasil.append(art)

    return hasil[:15]


# ---------------------------------------------------------------------------
# Reddit JSON API (tanpa OAuth — read-only publik)
# ---------------------------------------------------------------------------

def fetch_reddit(topik: str, maks: int = 10) -> list[dict]:
    """
    Ambil post Reddit relevan menggunakan JSON API publik.
    """
    kata_kunci = urllib.parse.quote(topik)
    hasil = []
    seen  = set()

    url_search = f"https://www.reddit.com/search.json?q={kata_kunci}&sort=hot&limit=10&restrict_sr=false"
    data = _fetch(url_search)
    if data:
        hasil.extend(_parse_reddit_json(data, "Reddit Search"))

    for sub in REDDIT_SUBREDDITS:
        url_sub = f"https://www.reddit.com/r/{sub}/search.json?q={kata_kunci}&sort=hot&limit=5&restrict_sr=true"
        data = _fetch(url_sub)
        if data:
            hasil.extend(_parse_reddit_json(data, f"r/{sub}"))
        time.sleep(0.3)

    kata_list = [k.lower() for k in topik.split() if len(k) > 3]
    dedup = []
    for post in hasil:
        if post["id"] in seen:
            continue
        seen.add(post["id"])
        teks = (post["judul"] + " " + post.get("ringkasan", "")).lower()
        skor = sum(1 for k in kata_list if k in teks)
        post["relevansi"] = skor
        if skor > 0 or not kata_list:
            dedup.append(post)

    dedup.sort(key=lambda x: (-x.get("relevansi", 0), -x.get("upvotes", 0)))
    return dedup[:maks]


def _parse_reddit_json(json_text: str, sumber: str) -> list[dict]:
    """Parse response JSON Reddit listing."""
    posts = []
    try:
        data     = json.loads(json_text)
        children = data.get("data", {}).get("children", [])
        for child in children:
            d        = child.get("data", {})
            post_id  = d.get("id", "")
            judul    = _clean_html(d.get("title", ""))
            selftext = _clean_html(d.get("selftext", ""))[:300]
            upvotes  = d.get("ups", 0)
            komentar = d.get("num_comments", 0)
            subreddit = d.get("subreddit_name_prefixed", sumber)
            url      = "https://reddit.com" + d.get("permalink", "")

            if not judul or post_id in ("", None):
                continue

            posts.append({
                "id":        f"reddit_{post_id}",
                "judul":     judul,
                "ringkasan": selftext,
                "link":      url,
                "sumber":    subreddit,
                "upvotes":   upvotes,
                "komentar":  komentar,
                "tipe":      "reddit",
            })
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return posts


# ---------------------------------------------------------------------------
# Fungsi utama: gabungkan berita + Reddit → briefing untuk agen
# (dengan disk cache — tidak fetch ulang jika topik sama & TTL belum habis)
# ---------------------------------------------------------------------------

def ambil_konteks_real(topik: str, force_refresh: bool = False) -> dict:
    """
    Ambil data real dari berita + Reddit, gabungkan jadi briefing
    yang siap dipakai sebagai konteks agen sebelum simulasi dimulai.

    Cache:
      - Hit  → return langsung dari disk, 0 HTTP request
      - Miss → fetch RSS + Reddit, simpan ke cache, return
      - TTL  → default 30 menit (CONTEXT_CACHE_TTL_MINUTES di .env)
      - force_refresh=True → skip cache, fetch ulang

    Returns:
        {
            "berita":    [...],
            "reddit":    [...],
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
            return cached
    # ─────────────────────────────────────────────────────────────────────

    from concurrent.futures import ThreadPoolExecutor

    # Fetch paralel — berita & Reddit bersamaan
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_berita = ex.submit(fetch_berita, topik)
        fut_reddit = ex.submit(fetch_reddit, topik)
        berita = fut_berita.result()
        reddit = fut_reddit.result()

    # Bangun teks briefing ringkas
    baris = []

    if berita:
        baris.append("📰 BERITA TERKINI:")
        for i, art in enumerate(berita[:5], 1):
            ring = f" — {art['ringkasan'][:120]}..." if art["ringkasan"] else ""
            baris.append(f"  {i}. [{art['sumber']}] {art['judul']}{ring}")

    if reddit:
        baris.append("\n💬 DISKUSI PUBLIK (Reddit):")
        for i, post in enumerate(reddit[:5], 1):
            ring = f" — {post['ringkasan'][:100]}..." if post.get("ringkasan") else ""
            meta = f" (👍 {post.get('upvotes', 0)}, 💬 {post.get('komentar', 0)})"
            baris.append(f"  {i}. [{post['sumber']}] {post['judul']}{ring}{meta}")

    briefing = (
        f"=== DATA REAL TERKAIT TOPIK: {topik} ===\n"
        + "\n".join(baris)
        + "\n=== GUNAKAN DATA INI SEBAGAI REFERENSI, BUKAN SATU-SATUNYA FAKTA ==="
    ) if baris else ""

    result = {
        "berita":     berita,
        "reddit":     reddit,
        "briefing":   briefing,
        "total":      len(berita) + len(reddit),
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "from_cache": False,
    }

    # ── Simpan ke cache ───────────────────────────────────────────────────
    _set_cache(topik, result)
    # ─────────────────────────────────────────────────────────────────────

    return result