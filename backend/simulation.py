# backend/simulation.py
# Orchestration utama simulasi multi-agen multi-ronde.
#
# Tanggung jawab modul ini:
#   - run_simulation()        — loop ronde + per-agen, kumpulkan output
#   - _analisis_dan_aktor()   — 1 call LLM-JSON untuk narasi + aktor kunci
#   - analyze_key_actors()    — endpoint /extract-graph (pure Python + LLM)
#   - _build_ringkasan_agen() — helper pure Python (volatilitas + pengaruh)
#   - _aktor_fallback()       — fallback tanpa LLM
#   - _parse_prediksi()       — parse persentase skenario dari teks

import re
import time

from .llm      import (
    call_llm, call_llm_json,
    MODEL_AGENT, MODEL_ANALYSIS,
    MAX_TOKENS_AGENT, MAX_TOKENS_ANALYSIS,
    AGENT_CALL_DELAY, ROUND_DELAY,
)
from .memory   import (
    update_agent_memory, build_memory_context, build_influence_context,
    _compute_gaya_str,
)
from .sentiment import score_sentiment
from .graph     import extract_entities


# ---------------------------------------------------------------------------
# Simulation Core — Sequential + Jeda (solusi utama rate limit)
# ---------------------------------------------------------------------------

def run_simulation(
    topik: str,
    agents: list[dict],
    jumlah_ronde: int = 3,
    intervensi: str | None = None,
    briefing_real: str = "",
) -> dict:
    """
    Jalankan simulasi multi-agen multi-ronde.

    RATE LIMIT STRATEGY:
    ─────────────────────────────────────────────────
    • Agen diproses SEQUENTIAL, satu per satu
    • Jeda AGENT_CALL_DELAY detik antar setiap agen
    • Jeda ROUND_DELAY detik antar setiap ronde
    • Token prompt dipangkas: role max 250 char, briefing max 200 char
    • Retry otomatis via call_llm() jika 429
    • Sentiment mode inline = 0 token tambahan per agen
    ─────────────────────────────────────────────────
    """
    ronde_detail              = []
    log_diskusi               = f"TOPIK: {topik}\n"
    pendapat_ronde_sebelumnya: list[dict] = []

    # Precompute field statis per agen — tidak berubah sepanjang simulasi
    for agen in agents:
        agen.setdefault("_role_singkat", agen["role"][:250].rstrip())
        _compute_gaya_str(agen)

    def _proses_satu_agen(agen: dict, ronde_ke: int, topik_ronde: str) -> dict:
        konteks_memori   = build_memory_context(agen)
        konteks_pengaruh = build_influence_context(agen, pendapat_ronde_sebelumnya)

        gaya_str     = _compute_gaya_str(agen)
        role_singkat = agen.get("_role_singkat") or agen["role"][:250].rstrip()

        system_p = (
            f"Kamu {agen['nama']}. {role_singkat} "
            f"Gaya: {gaya_str}. "
            "Jawab 1-2 kalimat pendek, bahasa sehari-hari."
        )

        parts = []
        if konteks_memori:   parts.append(konteks_memori)
        if konteks_pengaruh: parts.append(konteks_pengaruh)
        if ronde_ke == 1 and briefing_real:
            parts.append(f"Info: {briefing_real[:200]}")
        parts.append(f"Topik: {topik_ronde[:130]}\nPendapatmu?")
        user_p = "\n".join(parts)

        jawaban  = call_llm(system_p, user_p, max_tokens=MAX_TOKENS_AGENT, model=MODEL_AGENT)
        sentimen = score_sentiment(jawaban, topik=topik_ronde)

        return {
            "nama":     agen["nama"],
            "pendapat": jawaban,
            "sentimen": sentimen,
            "pengaruh": agen.get("pengaruh", 0.5),
        }

    for ronde_ke in range(1, jumlah_ronde + 1):
        topik_ronde = topik
        if intervensi and ronde_ke == (jumlah_ronde // 2) + 1:
            topik_ronde = f"{topik} [INTERVENSI: {intervensi}]"
            log_diskusi += f"\n--- INTERVENSI RONDE {ronde_ke}: {intervensi} ---\n"

        output_ronde       = {"ronde": ronde_ke, "agen": []}
        pendapat_ronde_ini = []

        # ── SEQUENTIAL — satu agen per call, bukan paralel ───────────────
        for idx, agen in enumerate(agents):
            try:
                res = _proses_satu_agen(agen, ronde_ke, topik_ronde)
            except Exception as e:
                print(f"[Skip] {agen['nama']} ronde {ronde_ke}: {e}")
                res = {
                    "nama":     agen["nama"],
                    "pendapat": "(tidak dapat merespons saat ini)",
                    "sentimen": {"label": "netral", "skor": 0.0},
                    "pengaruh": agen.get("pengaruh", 0.5),
                }

            update_agent_memory(agen, ronde_ke, res["pendapat"])
            log_diskusi += f"\n[R{ronde_ke}] {agen['nama']}: {res['pendapat']}\n"

            output_ronde["agen"].append({
                "nama": res["nama"], "pendapat": res["pendapat"], "sentimen": res["sentimen"],
            })
            pendapat_ronde_ini.append({
                "nama": res["nama"], "pendapat": res["pendapat"],
                "sentimen": res["sentimen"], "pengaruh": res["pengaruh"],
            })

            # Jeda antar agen (kecuali terakhir di ronde terakhir)
            bukan_akhir = not (idx == len(agents) - 1 and ronde_ke == jumlah_ronde)
            if bukan_akhir:
                time.sleep(AGENT_CALL_DELAY)

        ronde_detail.append(output_ronde)
        pendapat_ronde_sebelumnya = pendapat_ronde_ini

        # Jeda antar ronde
        if ronde_ke < jumlah_ronde:
            time.sleep(ROUND_DELAY)

    # ── GraphRAG extraction ──────────────────────────────────────────────
    graf_data = extract_entities(topik, log_diskusi)

    # ── Sentimen agregat ─────────────────────────────────────────────────
    sentimen_agregat = {}
    for agen in agents:
        tren = [
            a["sentimen"]["skor"]
            for ronde in ronde_detail
            for a in ronde["agen"]
            if a["nama"] == agen["nama"]
        ]
        sentimen_agregat[agen["nama"]] = tren

    # ── Analisis akhir + aktor kunci — digabung 1 call (FIX #3) ─────────
    analisis_raw, aktor_analisis = _analisis_dan_aktor(
        topik, log_diskusi, agents, sentimen_agregat
    )
    prediksi = _parse_prediksi(analisis_raw)

    return {
        "ronde_detail":     ronde_detail,
        "graf_data":        graf_data,
        "analisis":         analisis_raw,
        "prediksi":         prediksi,
        "sentimen_agregat": sentimen_agregat,
        "jumlah_ronde":     jumlah_ronde,
        "topik":            topik,
        "intervensi":       intervensi,
        "aktor_analisis":   aktor_analisis,
        "model_info": {
            "agen":           MODEL_AGENT,
            "analisis":       MODEL_ANALYSIS,
            "sentiment_mode": __import__("os").getenv("SENTIMENT_MODE", "inline"),
        },
    }


# ---------------------------------------------------------------------------
# Analisis Gabungan — 1 call LLM-JSON (FIX #3)
# ---------------------------------------------------------------------------

def _build_ringkasan_agen(agents: list[dict], sentimen_agregat: dict) -> tuple[dict, dict, list[str]]:
    """Helper: hitung volatilitas + pengaruh_map + ringkasan per agen (pure Python)."""
    pengaruh_map = {a["nama"]: a.get("pengaruh", 0.5) for a in agents}
    volatilitas: dict[str, float] = {}
    for nama, tren in sentimen_agregat.items():
        if len(tren) < 2:
            volatilitas[nama] = 0.0
        else:
            volatilitas[nama] = round(
                sum(abs(tren[i] - tren[i-1]) for i in range(1, len(tren))) / (len(tren)-1), 2
            )
    ringkasan_agen = []
    for nama, tren in sentimen_agregat.items():
        if not tren: continue
        arah = "stabil"
        if len(tren) >= 2:
            if tren[-1] - tren[0] > 0.2:   arah = "→mendukung"
            elif tren[0] - tren[-1] > 0.2: arah = "→menolak"
        ringkasan_agen.append(
            f"{nama}: pengaruh={pengaruh_map.get(nama,0.5)}, "
            f"skor={tren[0]:.2f}→{tren[-1]:.2f}, vol={volatilitas.get(nama,0)}, {arah}"
        )
    return pengaruh_map, volatilitas, ringkasan_agen


def _analisis_dan_aktor(
    topik: str,
    log_diskusi: str,
    agents: list[dict],
    sentimen_agregat: dict,
) -> tuple[str, dict]:
    """
    Gabungkan analisis akhir + aktor kunci dalam 1 call LLM-JSON.

    Sebelumnya: 2 call terpisah (call_llm teks + call_llm_json aktor).
    Sekarang:   1 call JSON yang sekaligus menghasilkan narasi + aktor.

    Return: (analisis_raw: str, aktor_analisis: dict)
    """
    nama_valid = list(sentimen_agregat.keys())
    pengaruh_map, volatilitas, ringkasan_agen = _build_ringkasan_agen(agents, sentimen_agregat)

    prompt = (
        f"Log diskusi:\n{log_diskusi[:1200]}\n\n"
        f"Data agen:\n" + "\n".join(ringkasan_agen) + "\n\n"
        "Balas HANYA JSON valid dengan struktur:\n"
        '{"analisis": "<RINGKASAN 2 paragraf>\\n\\n<TABEL: | Partisipan | Sikap Akhir | Prediksi ke Depan | Kemungkinan Berubah |>\\n\\nPREDIKSI SKENARIO: Konsensus X%, Polarisasi Y%, Status Quo Z%.", '
        '"aktor_kunci":[{"nama":"...","alasan":"...","dampak_jika_berubah":"..."}], '
        '"swing_voter":[{"nama":"...","alasan_volatil":"...","potensi_arah":"mendukung|menolak"}], '
        '"aktor_penggerak":"...", "rekomendasi":"..."}'
    )

    raw = call_llm_json(
        "Kamu analis sosial. Jawab HANYA JSON valid, bahasa Indonesia mudah dipahami.",
        prompt,
        max_tokens=MAX_TOKENS_ANALYSIS,
        model=MODEL_ANALYSIS,
    )

    def _resolve(s: str) -> str:
        s = s.strip()
        if s in pengaruh_map: return s
        for v in nama_valid:
            if v.lower() == s.lower() or s.lower() in v.lower(): return v
        return s

    def _lb(skor): return "Mendukung" if skor > 0.2 else "Menolak" if skor < -0.2 else "Netral"

    analisis_raw  = ""
    aktor_analisis: dict = {}

    if isinstance(raw, dict) and raw:
        analisis_raw = str(raw.get("analisis", ""))

        for item in raw.get("aktor_kunci", []):
            nama = _resolve(item.get("nama", ""))
            item["nama"] = nama
            tren = sentimen_agregat.get(nama, [])
            item.update({
                "pengaruh_skor": pengaruh_map.get(nama, 0.5),
                "sikap_akhir":   tren[-1] if tren else 0.0,
                "sikap_label":   _lb(tren[-1] if tren else 0.0),
            })
        for item in raw.get("swing_voter", []):
            nama = _resolve(item.get("nama", ""))
            item["nama"] = nama
            tren = sentimen_agregat.get(nama, [])
            item.update({
                "volatilitas": volatilitas.get(nama, 0.0),
                "sikap_awal":  tren[0]  if tren else 0.0,
                "sikap_akhir": tren[-1] if tren else 0.0,
            })
        pg = raw.get("aktor_penggerak", "")
        if pg and pg != "-":
            raw["aktor_penggerak"] = _resolve(pg)

        aktor_analisis = {
            k: raw[k] for k in ("aktor_kunci", "swing_voter", "aktor_penggerak", "rekomendasi")
            if k in raw
        }

    if not analisis_raw:
        analisis_raw = "(analisis tidak tersedia)"
    if not aktor_analisis:
        aktor_analisis = _aktor_fallback(pengaruh_map, volatilitas, sentimen_agregat)

    return analisis_raw, aktor_analisis


def _aktor_fallback(pengaruh_map: dict, volatilitas: dict, sentimen_agregat: dict) -> dict:
    """Fallback pure-Python tanpa LLM jika call JSON gagal."""
    def _lb(skor): return "Mendukung" if skor > 0.2 else "Menolak" if skor < -0.2 else "Netral"
    sp = sorted(pengaruh_map.items(), key=lambda x: -x[1])
    sv = sorted(volatilitas.items(),  key=lambda x: -x[1])
    return {
        "aktor_kunci": [
            {"nama": n, "alasan": "Pengaruh tertinggi",
             "dampak_jika_berubah": "Dapat menggeser konsensus",
             "pengaruh_skor": s,
             "sikap_akhir":   sentimen_agregat.get(n, [0])[-1],
             "sikap_label":   _lb(sentimen_agregat.get(n, [0])[-1])}
            for n, s in sp[:3]
        ],
        "swing_voter": [
            {"nama": n, "alasan_volatil": "Sering berubah pendapat",
             "potensi_arah": "mendukung" if sentimen_agregat.get(n,[0])[-1] > 0 else "menolak",
             "volatilitas": v,
             "sikap_awal":  sentimen_agregat.get(n,[0])[0],
             "sikap_akhir": sentimen_agregat.get(n,[0])[-1]}
            for n, v in sv[:3] if v > 0
        ],
        "aktor_penggerak": sp[0][0] if sp else "-",
        "rekomendasi": "Fokus pada aktor paling berpengaruh.",
    }


# ---------------------------------------------------------------------------
# Analisis Aktor Kunci & Swing Voter
# (dipertahankan untuk endpoint /extract-graph yang memanggilnya langsung)
# ---------------------------------------------------------------------------

def analyze_key_actors(
    topik: str,
    agents: list[dict],
    ronde_detail: list[dict],
    sentimen_agregat: dict,
) -> dict:
    volatilitas  = {}
    pengaruh_map = {a["nama"]: a.get("pengaruh", 0.5) for a in agents}
    nama_valid   = list(sentimen_agregat.keys())

    for nama, tren in sentimen_agregat.items():
        if len(tren) < 2: volatilitas[nama] = 0.0
        else:
            volatilitas[nama] = round(
                sum(abs(tren[i] - tren[i-1]) for i in range(1, len(tren))) / (len(tren)-1), 2
            )

    ringkasan_agen = []
    for nama, tren in sentimen_agregat.items():
        if not tren: continue
        arah = "stabil"
        if len(tren) >= 2:
            if tren[-1] - tren[0] > 0.2:   arah = "→mendukung"
            elif tren[0] - tren[-1] > 0.2: arah = "→menolak"
        ringkasan_agen.append(
            f"{nama}: pengaruh={pengaruh_map.get(nama,0.5)}, "
            f"skor={tren[0]:.2f}→{tren[-1]:.2f}, vol={volatilitas.get(nama,0)}, {arah}"
        )

    def _resolve(s: str) -> str:
        s = s.strip()
        if s in pengaruh_map: return s
        for v in nama_valid:
            if v.lower() == s.lower() or s.lower() in v.lower(): return v
        return s

    def _lb(skor): return "Mendukung" if skor > 0.2 else "Menolak" if skor < -0.2 else "Netral"

    prompt = (
        f"Topik: {topik}\nAgen: {', '.join(nama_valid)}\n"
        + "\n".join(ringkasan_agen) + "\n\n"
        "JSON:\n"
        '{"aktor_kunci":[{"nama":"...","alasan":"...","dampak_jika_berubah":"..."}],'
        '"swing_voter":[{"nama":"...","alasan_volatil":"...","potensi_arah":"mendukung|menolak"}],'
        '"aktor_penggerak":"...","rekomendasi":"..."}'
    )
    hasil = call_llm_json(
        "Analis diskusi sosial. Balas HANYA JSON valid.",
        prompt, max_tokens=500, model=MODEL_ANALYSIS
    )

    if isinstance(hasil, dict) and hasil:
        for item in hasil.get("aktor_kunci", []):
            nama = _resolve(item.get("nama", ""))
            item["nama"] = nama
            tren = sentimen_agregat.get(nama, [])
            item.update({
                "pengaruh_skor": pengaruh_map.get(nama, 0.5),
                "sikap_akhir":   tren[-1] if tren else 0.0,
                "sikap_label":   _lb(tren[-1] if tren else 0.0),
            })
        for item in hasil.get("swing_voter", []):
            nama = _resolve(item.get("nama", ""))
            item["nama"] = nama
            tren = sentimen_agregat.get(nama, [])
            item.update({
                "volatilitas": volatilitas.get(nama, 0.0),
                "sikap_awal":  tren[0]  if tren else 0.0,
                "sikap_akhir": tren[-1] if tren else 0.0,
            })
        pg = hasil.get("aktor_penggerak", "")
        if pg and pg != "-":
            hasil["aktor_penggerak"] = _resolve(pg)
        return hasil

    # Fallback tanpa LLM
    sp = sorted(pengaruh_map.items(), key=lambda x: -x[1])
    sv = sorted(volatilitas.items(),  key=lambda x: -x[1])
    return {
        "aktor_kunci": [
            {"nama": n, "alasan": "Pengaruh tertinggi",
             "dampak_jika_berubah": "Dapat menggeser konsensus",
             "pengaruh_skor": s,
             "sikap_akhir":   sentimen_agregat.get(n, [0])[-1],
             "sikap_label":   _lb(sentimen_agregat.get(n, [0])[-1])}
            for n, s in sp[:3]
        ],
        "swing_voter": [
            {"nama": n, "alasan_volatil": "Sering berubah pendapat",
             "potensi_arah": "mendukung" if sentimen_agregat.get(n,[0])[-1] > 0 else "menolak",
             "volatilitas": v,
             "sikap_awal":  sentimen_agregat.get(n,[0])[0],
             "sikap_akhir": sentimen_agregat.get(n,[0])[-1]}
            for n, v in sv[:3] if v > 0
        ],
        "aktor_penggerak": sp[0][0] if sp else "-",
        "rekomendasi": "Fokus pada aktor paling berpengaruh.",
    }


# ---------------------------------------------------------------------------
# Parse Prediksi Skenario
# ---------------------------------------------------------------------------

def _parse_prediksi(teks: str) -> dict:
    default = {"Konsensus": 33, "Polarisasi": 34, "Status Quo": 33}
    patterns = {
        "Konsensus":  r"[Kk]onsensus[^\d]*(\d{1,3})\s*%",
        "Polarisasi": r"[Pp]olarisasi[^\d]*(\d{1,3})\s*%",
        "Status Quo": r"[Ss]tatus\s*[Qq]uo[^\d]*(\d{1,3})\s*%",
    }
    hasil = {}
    for key, pat in patterns.items():
        m = re.search(pat, teks)
        if m: hasil[key] = int(m.group(1))
    if len(hasil) < 3: return default
    total = sum(hasil.values())
    return {k: round(v/total*100) for k, v in hasil.items()} if total else default