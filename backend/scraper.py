# backend/scraper.py
# Data real gratis untuk VoxSwarm:
#   - RSS feed berita Indonesia (Kompas, Detik, BBC Indonesia, Tempo, Antara)
#   - Reddit via JSON API publik (tanpa OAuth, gratis)
#   - Fallback graceful jika semua sumber gagal

import re
import time
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Konfigurasi sumber RSS — semua gratis, tidak butuh API key
# ---------------------------------------------------------------------------

RSS_SOURCES = [
    # Berita Indonesia
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
# HTTP helper
# ---------------------------------------------------------------------------

def _fetch(url: str, headers: dict = None, timeout: int = TIMEOUT) -> Optional[str]:
    """Fetch URL, return body string atau None jika gagal."""
    try:
        req = urllib.request.Request(url, headers=headers or HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            # Coba decode UTF-8 dulu, fallback ke latin-1
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
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text)
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
        # Bersihkan karakter tidak valid sebelum parse
        xml_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)
        root = ET.fromstring(xml_text)

        # Deteksi RSS vs Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        is_atom = root.tag.endswith("feed")

        if is_atom:
            items = root.findall("atom:entry", ns) or root.findall("entry")
        else:
            items = root.findall(".//item")

        for item in items[:10]:  # maks 10 artikel per sumber
            if is_atom:
                judul  = item.findtext("atom:title", "", ns) or item.findtext("title", "")
                link_el = item.find("atom:link", ns) or item.find("link")
                link   = link_el.get("href", "") if link_el is not None else ""
                ringkasan = (
                    item.findtext("atom:summary", "", ns)
                    or item.findtext("atom:content", "", ns)
                    or item.findtext("summary", "")
                )
                tanggal = item.findtext("atom:published", "", ns) or item.findtext("published", "")
            else:
                judul    = item.findtext("title", "")
                link     = item.findtext("link", "")
                ringkasan = item.findtext("description", "") or item.findtext("content:encoded", "")
                tanggal  = item.findtext("pubDate", "")

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

        # Filter relevan
        relevan = []
        for art in articles:
            teks = (art["judul"] + " " + art["ringkasan"]).lower()
            skor = sum(1 for k in kata_kunci if k in teks)
            if skor > 0:
                art["relevansi"] = skor
                relevan.append(art)

        relevan.sort(key=lambda x: -x.get("relevansi", 0))
        semua.extend(relevan[:maks_per_sumber])

    # Urutkan by relevansi, dedup by ID
    semua.sort(key=lambda x: -x.get("relevansi", 0))
    seen = set()
    hasil = []
    for art in semua:
        if art["id"] not in seen:
            seen.add(art["id"])
            hasil.append(art)

    return hasil[:15]  # maks 15 artikel total


# ---------------------------------------------------------------------------
# Reddit JSON API (tanpa OAuth — read-only publik)
# ---------------------------------------------------------------------------

def fetch_reddit(topik: str, maks: int = 10) -> list[dict]:
    """
    Ambil post Reddit relevan menggunakan JSON API publik.
    Cari di r/indonesia, r/IndonesiaNews, dan endpoint search global.
    """
    kata_kunci = urllib.parse.quote(topik)
    hasil = []
    seen  = set()

    # 1. Search global di Reddit
    url_search = f"https://www.reddit.com/search.json?q={kata_kunci}&sort=hot&limit=10&restrict_sr=false"
    data = _fetch(url_search)
    if data:
        hasil.extend(_parse_reddit_json(data, "Reddit Search"))

    # 2. Cari di subreddit spesifik
    for sub in REDDIT_SUBREDDITS:
        url_sub = f"https://www.reddit.com/r/{sub}/search.json?q={kata_kunci}&sort=hot&limit=5&restrict_sr=true"
        data = _fetch(url_sub)
        if data:
            hasil.extend(_parse_reddit_json(data, f"r/{sub}"))
        time.sleep(0.3)  # rate limit Reddit

    # Dedup & filter relevan
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
        data = json.loads(json_text)
        children = data.get("data", {}).get("children", [])
        for child in children:
            d = child.get("data", {})
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
# ---------------------------------------------------------------------------

def ambil_konteks_real(topik: str) -> dict:
    """
    Ambil data real dari berita + Reddit, gabungkan jadi briefing
    yang siap dipakai sebagai konteks agen sebelum simulasi dimulai.

    Returns:
        {
            "berita": [...],
            "reddit": [...],
            "briefing": str,   ← teks siap pakai untuk prompt agen
            "total": int,
            "timestamp": str,
        }
    """
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

    if not baris:
        briefing = ""
    else:
        briefing = (
            f"=== DATA REAL TERKAIT TOPIK: {topik} ===\n"
            + "\n".join(baris)
            + "\n=== GUNAKAN DATA INI SEBAGAI REFERENSI, BUKAN SATU-SATUNYA FAKTA ==="
        )

    return {
        "berita":    berita,
        "reddit":    reddit,
        "briefing":  briefing,
        "total":     len(berita) + len(reddit),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }