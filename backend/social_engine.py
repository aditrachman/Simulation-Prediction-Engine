# backend/social_engine.py
# Mode Sosmed VoxSwarm — diperbaiki:
#   FIX INTERAKSI: Eksekusi aksi SEQUENTIAL per tick dalam 2 fase:
#     Fase 1 — semua agen "berpikir" (LLM call paralel) dan memilih aksi
#     Fase 2 — aksi dieksekusi SEQUENTIAL agar interaksi antar-agen nyata:
#              REPLY/LIKE/QUOTE bisa merujuk post yang dibuat agen lain
#              di fase 1 yang sama (bukan hanya post dari tick sebelumnya)
#   FIX EMOTIKON: Fungsi strip_emoji() menghapus emotikon dari teks analisis
#   FIX #3a: Statistik agregat di level atas payload
#   FIX #3b: parent_name di setiap post reply/quote

import re
import uuid
import time
from datetime import datetime, timezone
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Tipe data dasar
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _uid() -> str:
    return str(uuid.uuid4())[:8]


def strip_emoji(teks: str) -> str:
    """Hapus emoji/simbol unicode non-ASCII dari teks, untuk laporan profesional."""
    if not teks:
        return ""
    # Hapus karakter emoji (blok unicode umum)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"
        "\u3030"
        "]+",
        flags=re.UNICODE,
    )
    hasil = emoji_pattern.sub("", teks)
    # Bersihkan spasi berlebih
    hasil = re.sub(r"  +", " ", hasil).strip()
    return hasil


def buat_akun(agen: dict) -> dict:
    """Buat akun sosmed untuk satu agen."""
    return {
        "id":          _uid(),
        "nama":        agen["nama"],
        "handle":      "@" + agen["nama"].lower().replace(" ", "_").replace("/", "_"),
        "role":        agen["role"],
        "kepribadian": agen.get("kepribadian", {}),
        "pengaruh":    agen.get("pengaruh", 0.5),
        "is_counter":  agen.get("is_counter", False),
        "followers":   [],
        "following":   [],
        "likes_given": [],
        "posts":       [],
        "is_authority": "pemerintah" in agen["nama"].lower() or "pejabat" in agen["nama"].lower(),
    }


def buat_post(
    akun: dict,
    konten: str,
    tipe: str = "post",
    reply_to: str = None,
    quote_of: str = None,
    topik: str = "",
    sentimen: dict = None,
    parent_nama: str = None,
    parent_handle: str = None,
) -> dict:
    """Buat satu post/tweet dari sebuah akun."""
    post_id = _uid()
    akun["posts"].append(post_id)
    return {
        "id":            post_id,
        "akun_id":       akun["id"],
        "nama":          akun["nama"],
        "handle":        akun["handle"],
        "konten":        konten,
        "tipe":          tipe,
        "reply_to":      reply_to,
        "quote_of":      quote_of,
        "parent_nama":   parent_nama,
        "parent_handle": parent_handle,
        "topik":         topik,
        "sentimen":      sentimen or {"label": "netral", "skor": 0.0},
        "likes":         [],
        "replies":       [],
        "quotes":        [],
        "timestamp":     _now_iso(),
        "is_viral":      False,
        "reach":         0,
    }


# ---------------------------------------------------------------------------
# Social Engine Core
# ---------------------------------------------------------------------------

def run_social_simulation(
    topik: str,
    agents: list[dict],
    konteks_real: dict,
    jumlah_tick: int = 5,
    intervensi: str = None,
    call_llm_fn=None,
    call_llm_json_fn=None,
    score_sentiment_fn=None,
    model_agent: str = "llama-3.1-8b-instant",
    model_analysis: str = "llama-3.3-70b-versatile",
) -> dict:
    """
    Jalankan simulasi sosial media multi-agen.

    PERBAIKAN UTAMA — Interaksi 2-Fase per Tick:
    ─────────────────────────────────────────────────────────────────────
    Setiap tick dijalankan dalam dua fase terpisah:

    FASE 1 (paralel): Semua agen "berpikir" bersamaan dan menghasilkan
        rencana aksi (JSON). POST dieksekusi langsung di fase ini agar
        hasilnya tersedia di fase 2.

    FASE 2 (sequential): Aksi non-post (LIKE, REPLY, QUOTE, FOLLOW)
        dieksekusi satu per satu. Karena semua post fase 1 sudah masuk
        ke post_map, REPLY/QUOTE ke post teman satu tick bisa berhasil.
    ─────────────────────────────────────────────────────────────────────
    """

    akun_map: dict[str, dict] = {}
    for agen in agents:
        akun = buat_akun(agen)
        akun_map[agen["nama"]] = akun

    _setup_awal_following(akun_map)

    semua_post: list[dict] = []
    post_map:   dict[str, dict] = {}

    log_aktivitas: list[dict] = []
    tick_detail:   list[dict] = []

    briefing = konteks_real.get("briefing", "")

    tick_intervensi = (jumlah_tick // 2) + 1 if intervensi else -1

    # Precompute string gaya per agen (kepribadian tidak berubah)
    _gaya_agen: dict[str, str] = {}
    for agen in agents:
        kep      = agen.get("kepribadian", {})
        agresif  = kep.get("agreeableness", 0.5) < 0.4
        emosional = kep.get("neuroticism",   0.5) > 0.6
        terbuka  = kep.get("openness",       0.5) > 0.7
        _gaya_agen[agen["nama"]] = (
            f"{'suka debat dan langsung nyerang argumen' if agresif else 'sopan tapi tegas'}"
            f"{', mudah emosi kalau ada yang salah' if emosional else ''}"
            f"{', aktif engage berbagai sudut pandang' if terbuka else ''}"
        )

    for tick in range(1, jumlah_tick + 1):

        # ── Injeksi intervensi sebagai "breaking news post" ──────────────
        if tick == tick_intervensi and intervensi:
            post_intervensi = {
                "id":            _uid(),
                "akun_id":       "SYSTEM",
                "nama":          "Breaking News",
                "handle":        "@breaking_news",
                "konten":        f"BREAKING: {intervensi}",
                "tipe":          "post",
                "reply_to":      None,
                "quote_of":      None,
                "parent_nama":   None,
                "parent_handle": None,
                "topik":         topik,
                "sentimen":      {"label": "netral", "skor": 0.0},
                "likes":         [],
                "replies":       [],
                "quotes":        [],
                "timestamp":     _now_iso(),
                "is_viral":      True,
                "reach":         len(agents),
            }
            semua_post.insert(0, post_intervensi)
            post_map[post_intervensi["id"]] = post_intervensi

        # Precompute snapshot tick (sama untuk semua agen dalam satu tick)
        _trending_tick   = _get_trending(semua_post, top_n=3)
        _trending_teks   = _format_trending(_trending_tick) if _trending_tick else "Belum ada trending."
        _intervensi_teks = f"\n BREAKING NEWS: {intervensi}" if (tick == tick_intervensi and intervensi) else ""
        _briefing_teks   = briefing[:400] if briefing else "(tidak ada data real)"

        tick_posts: list[dict] = []
        tick_aksi:  list[dict] = []

        # ═══════════════════════════════════════════════════════════════
        # FASE 1 — LLM calls paralel: semua agen "berpikir" bersamaan
        #          dan menghasilkan rencana aksi.
        #          POST langsung dieksekusi agar tersedia di Fase 2.
        # ═══════════════════════════════════════════════════════════════

        rencana_fase1: list[dict] = []   # [(agen_nama, aksi, konten, target, alasan)]

        def _pikirkan_aksi(agen_nama: str) -> dict:
            """Fase 1: minta LLM memilih aksi. Return dict rencana."""
            akun = akun_map[agen_nama]
            agen = next(a for a in agents if a["nama"] == agen_nama)

            feed      = _build_feed(akun, semua_post, post_map, maks=8)
            feed_teks = _format_feed(feed) if feed else "Belum ada post di feed."
            gaya_str  = _gaya_agen[agen_nama]

            # Daftar post yang bisa di-like/reply/quote (ID aktual)
            post_ref_list = "\n".join([
                f"  [{p['id']}] @{p['handle']}: {p['konten'][:100]}"
                for p in feed[:6]
            ])

            system_p = (
                f"Kamu {agen['nama']} di platform sosial media dengan handle {akun['handle']}. {agen['role']} "
                f"Gaya: {gaya_str}. "
                "Pilih SATU aksi: POST, LIKE, REPLY, QUOTE, FOLLOW, atau DIAM. "
                "PENTING: untuk LIKE/REPLY/QUOTE, gunakan HANYA ID post dari daftar di bawah (format 8 karakter). "
                "Balas HANYA JSON valid."
            )

            user_p = (
                f"Topik hari ini: {topik}{_intervensi_teks}\n\n"
                f"Data terkini:\n{_briefing_teks}\n\n"
                f"Feed kamu:\n{feed_teks}\n\n"
                f"Trending:\n{_trending_teks}\n\n"
                f"Post yang bisa kamu LIKE/REPLY/QUOTE (gunakan ID-nya):\n"
                f"{post_ref_list if post_ref_list else '(belum ada post)'}\n\n"
                f"Follower kamu: {len(akun['followers'])} | Following: {len(akun['following'])}\n\n"
                '{"aksi": "POST|LIKE|REPLY|QUOTE|FOLLOW|DIAM", '
                '"konten": "isi post/reply/quote (kosong jika LIKE/FOLLOW/DIAM)", '
                '"target_id": "ID post (8 karakter) jika LIKE/REPLY/QUOTE, atau nama agen jika FOLLOW", '
                '"alasan": "kenapa kamu pilih aksi ini (1 kalimat)"}'
            )

            raw = call_llm_json_fn(system_p, user_p, max_tokens=200, model=model_agent)
            if not isinstance(raw, dict):
                raw = {}

            return {
                "agen_nama": agen_nama,
                "aksi":      str(raw.get("aksi",      "DIAM")).upper().strip(),
                "konten":    str(raw.get("konten",    "")).strip(),
                "target":    str(raw.get("target_id", "")).strip(),
                "alasan":    str(raw.get("alasan",    "")).strip(),
            }

        with ThreadPoolExecutor(max_workers=min(len(agents), 6)) as executor:
            futures = {executor.submit(_pikirkan_aksi, a["nama"]): a["nama"] for a in agents}
            for future in as_completed(futures):
                try:
                    rencana = future.result()
                    rencana_fase1.append(rencana)
                except Exception as e:
                    print(f"[Fase1 Error] {futures[future]}: {e}")

        # POST dieksekusi di akhir Fase 1 agar semua post tersedia di Fase 2
        for rencana in rencana_fase1:
            if rencana["aksi"] == "POST" and rencana["konten"]:
                akun     = akun_map[rencana["agen_nama"]]
                konten   = rencana["konten"]
                sentimen = score_sentiment_fn(konten, topik) if score_sentiment_fn else {"label": "netral", "skor": 0.0}
                post     = buat_post(akun, konten, tipe="post", topik=topik, sentimen=sentimen)
                semua_post.append(post)
                post_map[post["id"]] = post
                tick_posts.append(post)
                tick_aksi.append({
                    "tipe": "post", "post": post,
                    "alasan": rencana["alasan"], "agen": rencana["agen_nama"],
                })

        # ═══════════════════════════════════════════════════════════════
        # FASE 2 — Eksekusi sequential: LIKE, REPLY, QUOTE, FOLLOW
        #          Semua post fase 1 sudah ada di post_map, jadi
        #          interaksi antar-agen dalam satu tick bisa terjadi.
        # ═══════════════════════════════════════════════════════════════

        for rencana in rencana_fase1:
            agen_nama = rencana["agen_nama"]
            aksi      = rencana["aksi"]
            konten    = rencana["konten"]
            target    = rencana["target"]
            alasan    = rencana["alasan"]
            akun      = akun_map[agen_nama]

            if aksi == "POST":
                continue  # sudah dieksekusi di Fase 1

            elif aksi == "LIKE" and target:
                post_target = post_map.get(target)
                if post_target and akun["handle"] not in post_target["likes"]:
                    post_target["likes"].append(akun["handle"])
                    akun["likes_given"].append(target)
                    tick_aksi.append({
                        "tipe": "like", "target_id": target,
                        "alasan": alasan, "agen": agen_nama,
                    })
                else:
                    # target tidak ditemukan — coba like post terbaru dari orang lain
                    kandidat = [p for p in semua_post if p["nama"] != agen_nama and akun["handle"] not in p["likes"]]
                    if kandidat:
                        fallback = kandidat[-1]
                        fallback["likes"].append(akun["handle"])
                        akun["likes_given"].append(fallback["id"])
                        tick_aksi.append({
                            "tipe": "like", "target_id": fallback["id"],
                            "alasan": alasan + " (fallback)", "agen": agen_nama,
                        })

            elif aksi == "REPLY" and konten and target:
                post_target = post_map.get(target)
                if post_target:
                    sentimen = score_sentiment_fn(konten, topik) if score_sentiment_fn else {"label": "netral", "skor": 0.0}
                    reply    = buat_post(
                        akun, konten, tipe="reply", reply_to=target, topik=topik, sentimen=sentimen,
                        parent_nama=post_target.get("nama"), parent_handle=post_target.get("handle"),
                    )
                    post_target["replies"].append(reply["id"])
                    semua_post.append(reply)
                    post_map[reply["id"]] = reply
                    tick_posts.append(reply)
                    tick_aksi.append({
                        "tipe": "reply", "post": reply, "target_id": target,
                        "alasan": alasan, "agen": agen_nama,
                    })
                elif konten:
                    # target tidak ditemukan — jadikan POST biasa
                    sentimen = score_sentiment_fn(konten, topik) if score_sentiment_fn else {"label": "netral", "skor": 0.0}
                    post     = buat_post(akun, konten, tipe="post", topik=topik, sentimen=sentimen)
                    semua_post.append(post)
                    post_map[post["id"]] = post
                    tick_posts.append(post)
                    tick_aksi.append({
                        "tipe": "post", "post": post,
                        "alasan": alasan + " (reply→post fallback)", "agen": agen_nama,
                    })

            elif aksi == "QUOTE" and konten and target:
                post_target = post_map.get(target)
                if post_target:
                    sentimen = score_sentiment_fn(konten, topik) if score_sentiment_fn else {"label": "netral", "skor": 0.0}
                    quote    = buat_post(
                        akun, konten, tipe="quote", quote_of=target, topik=topik, sentimen=sentimen,
                        parent_nama=post_target.get("nama"), parent_handle=post_target.get("handle"),
                    )
                    post_target["quotes"].append(quote["id"])
                    semua_post.append(quote)
                    post_map[quote["id"]] = quote
                    tick_posts.append(quote)
                    tick_aksi.append({
                        "tipe": "quote", "post": quote, "target_id": target,
                        "alasan": alasan, "agen": agen_nama,
                    })
                elif konten:
                    # fallback ke POST
                    sentimen = score_sentiment_fn(konten, topik) if score_sentiment_fn else {"label": "netral", "skor": 0.0}
                    post     = buat_post(akun, konten, tipe="post", topik=topik, sentimen=sentimen)
                    semua_post.append(post)
                    post_map[post["id"]] = post
                    tick_posts.append(post)
                    tick_aksi.append({
                        "tipe": "post", "post": post,
                        "alasan": alasan + " (quote→post fallback)", "agen": agen_nama,
                    })

            elif aksi == "FOLLOW" and target:
                target_akun = _cari_akun(target, akun_map)
                if target_akun and target_akun["handle"] not in akun["following"]:
                    akun["following"].append(target_akun["handle"])
                    target_akun["followers"].append(akun["handle"])
                    tick_aksi.append({
                        "tipe": "follow", "target": target_akun["nama"],
                        "alasan": alasan, "agen": agen_nama,
                    })

            else:
                tick_aksi.append({
                    "tipe": "diam", "alasan": alasan or "tidak ada yang menarik",
                    "agen": agen_nama,
                })

        # ── Update virality & respons otoritas ──────────────────────────
        _update_virality(semua_post, akun_map)

        viral_posts = [p for p in semua_post if p.get("is_viral") and p["tipe"] == "post"]
        if viral_posts:
            for agen_nama, akun in akun_map.items():
                if akun["is_authority"]:
                    _authority_response(
                        akun, viral_posts, semua_post, post_map,
                        topik, briefing, tick, akun_map,
                        call_llm_json_fn, score_sentiment_fn,
                        model_agent, tick_aksi,
                    )

        tick_detail.append({
            "tick":       tick,
            "posts_baru": tick_posts,
            "aksi":       tick_aksi,
            "trending":   _get_trending(semua_post, top_n=5),
            "viral":      [p for p in semua_post if p.get("is_viral")],
        })

        log_aktivitas.extend(tick_aksi)

    # ── Analisis akhir sosmed ────────────────────────────────────────────
    analisis_sosmed = _analisis_sosmed(
        topik, semua_post, akun_map, log_aktivitas,
        call_llm_fn, model_analysis,
    )

    # ── Profil akun ─────────────────────────────────────────────────────
    profil_agen = []
    for nama, akun in akun_map.items():
        post_agen = [p for p in semua_post if p["nama"] == nama]
        total_likes_dapat  = sum(len(p["likes"])   for p in post_agen)
        total_reply_dapat  = sum(len(p["replies"]) for p in post_agen)
        total_quote_dapat  = sum(len(p["quotes"])  for p in post_agen)
        profil_agen.append({
            "nama":              akun["nama"],
            "handle":            akun["handle"],
            "followers":         len(akun["followers"]),
            "following":         len(akun["following"]),
            "total_post":        len([p for p in semua_post if p["nama"] == nama and p["tipe"] == "post"]),
            "total_likes_dapat": total_likes_dapat,
            "total_reply_dapat": total_reply_dapat,
            "total_quote_dapat": total_quote_dapat,
            "total_likes_beri":  len(akun["likes_given"]),
            "is_authority":      akun["is_authority"],
            "is_counter":        akun["is_counter"],
        })

    profil_agen.sort(key=lambda x: -(x["followers"] + x["total_likes_dapat"]))

    total_likes_global   = sum(len(p["likes"])   for p in semua_post)
    total_replies_global = sum(len(p["replies"]) for p in semua_post)
    total_quotes_global  = sum(len(p["quotes"])  for p in semua_post)
    viral_count_global   = len([p for p in semua_post if p.get("is_viral")])

    return {
        "mode":           "sosmed",
        "topik":          topik,
        "intervensi":     intervensi,
        "tick_detail":    tick_detail,
        "semua_post":     semua_post,
        "profil_agen":    profil_agen,
        "trending_akhir": _get_trending(semua_post, top_n=10),
        "viral_posts":    [p for p in semua_post if p.get("is_viral")],
        "log_aktivitas":  log_aktivitas,
        "analisis":       analisis_sosmed,
        "statistik": {
            "total_likes":   total_likes_global,
            "total_replies": total_replies_global,
            "total_quotes":  total_quotes_global,
            "viral_count":   viral_count_global,
            "total_post":    len([p for p in semua_post if p["tipe"] == "post" and p["akun_id"] != "SYSTEM"]),
        },
        "konteks_real": {
            "total_sumber": konteks_real.get("total", 0),
            "timestamp":    konteks_real.get("timestamp", ""),
        },
    }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _setup_awal_following(akun_map: dict):
    """Agen saling follow berdasarkan openness & pengaruh awal."""
    akun_list = list(akun_map.values())
    for akun in akun_list:
        openness    = akun["kepribadian"].get("openness", 0.5)
        maks_follow = int(openness * len(akun_list))
        kandidat    = [a for a in akun_list if a["handle"] != akun["handle"]]
        kandidat.sort(key=lambda x: -x["pengaruh"])
        for target in kandidat[:maks_follow]:
            if target["handle"] not in akun["following"]:
                akun["following"].append(target["handle"])
                target["followers"].append(akun["handle"])


def _build_feed(akun: dict, semua_post: list, post_map: dict, maks: int = 8) -> list[dict]:
    """Bangun feed untuk satu agen: post dari yang di-follow + trending."""
    following_handles = set(akun["following"])
    feed = [
        p for p in semua_post
        if p["handle"] in following_handles or p.get("is_viral")
    ]
    feed.sort(key=lambda x: x["timestamp"], reverse=True)
    return feed[:maks]


def _format_feed(feed: list[dict]) -> str:
    if not feed:
        return "(feed kosong)"
    baris = []
    for p in feed[:6]:
        like_str  = f" | {len(p['likes'])} likes" if p["likes"] else ""
        viral_str = " [VIRAL]" if p.get("is_viral") else ""
        tipe_str  = f"[{p['tipe'].upper()}] " if p["tipe"] != "post" else ""
        baris.append(f"  [{p['id']}] {tipe_str}{p['handle']}: {p['konten'][:100]}{like_str}{viral_str}")
    return "\n".join(baris)


def _format_trending(trending: list[dict]) -> str:
    if not trending:
        return "(belum ada trending)"
    baris = []
    for p in trending:
        engagement = len(p["likes"]) + len(p["replies"]) + len(p["quotes"])
        baris.append(f"  [{p['id']}] {p['handle']}: {p['konten'][:100]} (engagement: {engagement})")
    return "\n".join(baris)


def _get_trending(semua_post: list, top_n: int = 5) -> list[dict]:
    """Post dengan engagement tertinggi."""
    for p in semua_post:
        p["_engagement"] = len(p["likes"]) + len(p["replies"]) * 2 + len(p["quotes"]) * 3
    trending = sorted(semua_post, key=lambda x: -x.get("_engagement", 0))
    return trending[:top_n]


def _update_virality(semua_post: list, akun_map: dict, viral_threshold: int = 3):
    """Post dianggap viral jika engagement >= threshold."""
    n_agen    = len(akun_map)
    threshold = max(viral_threshold, n_agen // 3)
    for post in semua_post:
        engagement    = len(post["likes"]) + len(post["replies"]) * 2 + len(post["quotes"]) * 3
        post["is_viral"] = engagement >= threshold
        post["reach"]    = min(n_agen, engagement + 1)


def _cari_akun(target: str, akun_map: dict) -> Optional[dict]:
    """Cari akun berdasarkan nama atau handle."""
    target_lower = target.lower().strip().lstrip("@")
    for akun in akun_map.values():
        if (akun["nama"].lower() == target_lower or
                akun["handle"].lstrip("@").lower() == target_lower or
                target_lower in akun["nama"].lower()):
            return akun
    return None


def _authority_response(
    akun: dict, viral_posts: list, semua_post: list, post_map: dict,
    topik: str, briefing: str, tick: int, akun_map: dict,
    call_llm_json_fn, score_sentiment_fn,
    model_agent: str, tick_aksi: list,
):
    """Agen otoritas (pemerintah) merespons jika ada konten viral."""
    if not call_llm_json_fn or not viral_posts:
        return

    top_viral = sorted(viral_posts, key=lambda x: -x.get("_engagement", 0))[0]

    if any(
        a.get("tipe") == "reply" and a.get("target_id") == top_viral["id"] and a.get("agen") == akun["nama"]
        for a in tick_aksi
    ):
        return

    system_p = (
        f"Kamu {akun['nama']}, pejabat resmi. {akun['role']} "
        "Respons konten viral secara resmi dan diplomatis. Balas HANYA JSON valid."
    )
    user_p = (
        f"Topik: {topik}\n"
        f"Post viral dari {top_viral['handle']}: \"{top_viral['konten']}\"\n"
        f"Engagement: {len(top_viral['likes'])} likes | {len(top_viral['replies'])} balasan | {len(top_viral['quotes'])} kutipan\n\n"
        '{"aksi": "REPLY|QUOTE|POST_KEBIJAKAN", '
        '"konten": "respons resmi 1-2 kalimat, formal dan diplomatis", '
        '"kebijakan_baru": "kebijakan yang dipertimbangkan akibat post ini (bisa kosong)"}'
    )

    raw = call_llm_json_fn(system_p, user_p, max_tokens=150, model=model_agent)
    if not isinstance(raw, dict):
        return

    konten    = str(raw.get("konten", "")).strip()
    kebijakan = str(raw.get("kebijakan_baru", "")).strip()
    aksi      = str(raw.get("aksi", "REPLY")).upper()

    if konten:
        sentimen = score_sentiment_fn(konten, topik) if score_sentiment_fn else {"label": "netral", "skor": 0.0}
        if aksi in ("REPLY", "POST_KEBIJAKAN"):
            reply = buat_post(
                akun, konten, tipe="reply", reply_to=top_viral["id"], topik=topik, sentimen=sentimen,
                parent_nama=top_viral.get("nama"), parent_handle=top_viral.get("handle"),
            )
            top_viral["replies"].append(reply["id"])
            semua_post.append(reply)
            post_map[reply["id"]] = reply
            tick_aksi.append({
                "tipe": "reply_otoritas", "post": reply, "target_id": top_viral["id"],
                "kebijakan_baru": kebijakan,
                "alasan": f"Merespons post viral dari {top_viral['handle']}",
                "agen": akun["nama"],
            })
        elif aksi == "QUOTE":
            quote = buat_post(
                akun, konten, tipe="quote", quote_of=top_viral["id"], topik=topik, sentimen=sentimen,
                parent_nama=top_viral.get("nama"), parent_handle=top_viral.get("handle"),
            )
            top_viral["quotes"].append(quote["id"])
            semua_post.append(quote)
            post_map[quote["id"]] = quote
            tick_aksi.append({
                "tipe": "quote_otoritas", "post": quote, "target_id": top_viral["id"],
                "kebijakan_baru": kebijakan,
                "alasan": f"Quote tweet post viral dari {top_viral['handle']}",
                "agen": akun["nama"],
            })


def _analisis_sosmed(
    topik: str,
    semua_post: list,
    akun_map: dict,
    log_aktivitas: list,
    call_llm_fn,
    model_analysis: str,
) -> dict:
    """Analisis akhir dinamika sosmed. Teks analisis bebas dari emoji."""
    if not call_llm_fn:
        return {}

    total_post   = len([p for p in semua_post if p["tipe"] == "post"])
    total_reply  = len([p for p in semua_post if p["tipe"] == "reply"])
    total_quote  = len([p for p in semua_post if p["tipe"] == "quote"])
    total_like   = sum(len(p["likes"]) for p in semua_post)
    viral_count  = len([p for p in semua_post if p.get("is_viral")])

    top_posts     = _get_trending(semua_post, top_n=5)
    top_posts_teks = "\n".join(
        f"  - [{p['handle']}] \"{p['konten'][:100]}\" "
        f"({len(p['likes'])} likes, {len(p['replies'])} balasan, {len(p['quotes'])} kutipan)"
        for p in top_posts
    )

    ranking_akun = sorted(
        akun_map.values(),
        key=lambda x: -(len(x["followers"]) + len([p for p in semua_post if p["nama"] == x["nama"]]))
    )
    ranking_teks = "\n".join(
        f"  - {a['handle']}: {len(a['followers'])} followers"
        for a in ranking_akun[:5]
    )

    influencer_scores = {}
    for nama, akun in akun_map.items():
        post_agen = [p for p in semua_post if p["nama"] == nama]
        eng = sum(len(p["likes"]) + len(p["replies"]) * 2 + len(p["quotes"]) * 3 for p in post_agen)
        influencer_scores[nama] = eng
    top_influencers = sorted(influencer_scores.items(), key=lambda x: -x[1])[:3]

    prompt = (
        f"Topik: {topik}\n"
        f"Statistik: {total_post} post | {total_reply} reply | {total_quote} quote | {total_like} likes | {viral_count} viral\n\n"
        f"Top post:\n{top_posts_teks}\n\n"
        f"Ranking follower:\n{ranking_teks}\n\n"
        "Analisis singkat 3-4 kalimat: siapa paling berpengaruh, narasi dominan, dan dampak diskusi ini. "
        "JANGAN gunakan emoji atau simbol khusus dalam jawaban."
    )

    narasi_raw = call_llm_fn(
        "Kamu analis media sosial. Jelaskan dengan bahasa mudah dipahami orang awam. Jangan gunakan emoji.",
        prompt,
        max_tokens=400,
        model=model_analysis,
    )
    # Strip emoji dari hasil analisis
    narasi = strip_emoji(narasi_raw)

    return {
        "narasi": narasi,
        "statistik": {
            "total_post":   total_post,
            "total_reply":  total_reply,
            "total_quote":  total_quote,
            "total_like":   total_like,
            "viral_count":  viral_count,
        },
        "top_posts":     top_posts[:5],
        "ranking_akun":  [
            {"handle": a["handle"], "nama": a["nama"], "followers": len(a["followers"])}
            for a in ranking_akun[:5]
        ],
        "top_influencers": [
            {"nama": nama, "engagement_score": skor}
            for nama, skor in top_influencers
        ],
    }