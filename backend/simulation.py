# backend/simulation.py
# Orchestration utama simulasi multi-agen multi-ronde.
#
# FIX LOG (vs versi sebelumnya):
#   FIX-A: delta_cap ENFORCEMENT — skor agen tidak boleh loncat > 0.7 dalam 1 ronde
#           Sebelumnya hanya prompt-level (LLM sering abaikan). Sekarang di-clamp di Python.
#   FIX-B: change_justification HARD ENFORCEMENT — jika agen berubah > 0.35 tapi
#           tidak ada change marker, regenerate 1x dengan instruksi lebih keras.
#           Sebelumnya hanya print warning.
#   FIX-C: prediksi SINGLE SOURCE OF TRUTH — heuristic selalu jadi prediksi utama,
#           ML hanya ditampilkan sebagai "eksperimental" di explainability.
#           Sebelumnya dua angka muncul di laporan tanpa penjelasan mana yang benar.
#   FIX-D: Oposisi Kritis stance — flip mendukung→menolak di R1→R2 harus ada justifikasi,
#           sama seperti aturan agen lain. Sebelumnya tidak ada guard untuk Oposisi.
#   FIX-E: confidence reporting — satu angka konsisten, dengan label dan alasan.
#           Sebelumnya "80%" dan "0%" muncul bersamaan membingungkan user.

import os
import re
import json
import time
import statistics

from concurrent.futures import ThreadPoolExecutor

from .llm      import (
    call_llm, call_llm_json,
    MODEL_AGENT, MODEL_ANALYSIS,
    MAX_TOKENS_AGENT, MAX_TOKENS_ANALYSIS,
    AGENT_CALL_DELAY, ROUND_DELAY,
    DISABLE_GRAPH_LLM, DISABLE_FINAL_ANALYSIS_LLM,
    SENTIMENT_MODE,
    _strip_emoji,
)
from .memory   import (
    update_agent_memory, build_memory_context, build_round_summary,
    _compute_gaya_str,
)
from .sentiment import score_sentiment, filter_forbidden_opens
from .graph     import extract_entities
from .core.models import (
    SimulationEvent, simulation_result_to_state,
    AgentProfile, AgentAction,
)
from .core.reporting import generate_report
from .core.event_system import (
    compute_event_impact,
    build_event_narrative,
    get_agent_impact_note,
    generate_event_explanation,
)
from .core.scheduler import (
    get_speaking_order,
    get_strategy_display,
)
from .core.prediction import heuristic_predict, compute_confidence
from .core.scenario import (
    resolve_scenario,
    kepercayaan_sumber,
    teks_polarisasi,
    swing_voter_terfilter,
)
from .services.agent_turn import (
    execute_turn,
    TURN_MAX_TOKENS,
    TURN_RESPONSE_FORMAT,
    PEMICU_MAX_TOKENS,
    PEMICU_RESPONSE_FORMAT,
    angka_klaim,
)
# CrowdPool removed 2026-07-05 — unused, over-engineered

# Jalur baru: satu call LLM per giliran, stance/score dari JSON agen.
# Set USE_LEGACY_PIPELINE=true untuk kembali ke jalur lama (QA + sentimen LLM terpisah).
USE_LEGACY_PIPELINE = os.getenv("USE_LEGACY_PIPELINE", "false").lower() in {"1", "true", "yes", "on"}

# Ambang pemangkasan prompt jalur JSON. Lebih longgar dari legacy karena posisi agen,
# aturan berubah_karena, dan ringkasan pihak lain wajib utuh.
BATAS_TRIM_JSON = 1200

# Paralel antaragen dalam satu ronde (khusus jalur JSON). Ronde 1 independen dan
# Ronde 2+ hanya membaca ringkasan ronde sebelumnya, jadi tidak ada dependensi
# antaragen dalam satu ronde. Pacing dipegang TokenBudget + rate limiter RPM.
PARALLEL_AGENTS = os.getenv("PARALLEL_AGENTS", "false").lower() in {"1", "true", "yes", "on"}
PARALLEL_AGENTS_MAX = int(os.getenv("PARALLEL_AGENTS_MAX", "4"))

_STANCE_KE_LABEL = {"menolak": "negatif", "netral": "netral", "mendukung": "positif"}


# ---------------------------------------------------------------------------
# Helper: Batasi Output Agen (BUG-20)
# ---------------------------------------------------------------------------

def _batasi_kalimat(teks: str, max_kalimat: int = 3) -> str:
    """
    Post-processing pure Python — potong output agen di batas kalimat ke-N.
    Hanya potong kalau melebihi max_kalimat atau hard cap kata.
    """
    if not teks:
        return teks
    pecahan = re.split(r'(?<=[.!?;])\s+', teks.strip())
    pecahan = [k for k in pecahan if k.strip()]

    # ponytail: hard cap 80 kata ≈ 2-3 kalimat diskusi
    kata_total = teks.split()
    if len(kata_total) > 80:
        return " ".join(kata_total[:80]).rstrip(' ,;.-_:') + "."

    if len(pecahan) <= max_kalimat:
        return teks
    hasil = " ".join(pecahan[:max_kalimat])
    if hasil and hasil[-1] not in ".!?":
        hasil += "."
    return hasil


# ---------------------------------------------------------------------------
# FIX-A: Delta Cap — clamp skor agen agar tidak loncat > 0.7 dalam 1 ronde
# Ini HARD ENFORCEMENT di Python layer, bukan hanya instruksi di prompt LLM.
# ---------------------------------------------------------------------------

_DELTA_CAP = 0.70  # maksimum perubahan skor dalam 1 ronde

def _apply_delta_cap(skor_baru: float, skor_lalu: float | None, nama_agen: str, ronde_ke: int) -> float:
    """
    FIX-A: Clamp skor agen agar tidak loncat lebih dari _DELTA_CAP dalam 1 ronde.
    Contoh: skor_lalu=0.83, skor_baru=-0.98 → delta=1.81 → dikurangi ke -0.13

    Catatan: ini aturan realisme (manusia tidak berbalik posisi ekstrem dalam satu
    ronde), BUKAN hasil model. Stance tetap seperti yang ditulis agen; hanya score
    yang di-clamp.
    """
    if skor_lalu is None:
        return skor_baru
    delta = skor_baru - skor_lalu
    if abs(delta) > _DELTA_CAP:
        arah = 1 if delta > 0 else -1
        skor_capped = skor_lalu + (arah * _DELTA_CAP)
        skor_capped = max(-1.0, min(1.0, round(skor_capped, 2)))
        print(
            f"[DELTA_CAP] {nama_agen} R{ronde_ke}: "
            f"skor {skor_lalu:+.2f} → {skor_baru:+.2f} (delta={delta:+.2f}) "
            f"DIKURANGI ke {skor_capped:+.2f} (cap={_DELTA_CAP})"
        )
        return skor_capped
    return skor_baru


# ---------------------------------------------------------------------------
# BUG #3 FIX: Change Justification Validator — sekarang dengan REGENERATE
# ---------------------------------------------------------------------------

_CHANGE_MARKER_PATTERNS = [
    r"ronde\s+(lalu|sebelumnya).{0,50}(tapi|namun|tetapi|sekarang)",
    r"(sebelumnya|awalnya).{0,50}(sekarang|kini|namun|berubah)",
    r"awalnya.{0,50}(tetapi|tapi|kini|namun)",
    r"(bukti|data|argumen|fakta)\s+(baru|terbaru)",
    r"(saya|gue)\s+(revisi|ubah|ganti|perbarui)\s+(posisi|pendapat|pandangan)",
    r"(informasi|laporan|temuan)\s+(baru|terbaru|ini)\s+(mengubah|membuatku|membuat\s+saya)",
    r"(berdasarkan|melihat)\s+(respons|argumen|data).{0,30}(agen|tadi|sebelumnya)",
    # FIX-B: Tambah pola tambahan yang lebih natural
    r"(karena|sebab)\s+(ada|terdapat|muncul)\s+(data|fakta|argumen|bukti)",
    r"(merevisi|mengubah)\s+(posisi|pendapat|pandangan)",
    r"argumen\s+.{0,30}(meyakinkan|kuat|valid|solid)",
]

_CHANGE_MARKERS_COMPILED = [re.compile(p, re.IGNORECASE) for p in _CHANGE_MARKER_PATTERNS]

_CHANGE_THRESHOLD = 0.35  # FIX-B: threshold perubahan yang butuh justifikasi


def _has_change_marker(jawaban: str) -> bool:
    return any(p.search(jawaban) for p in _CHANGE_MARKERS_COMPILED)


def _validate_and_enforce_change_justification(
    nama_agen: str,
    ronde_ke: int,
    jawaban: str,
    skor_baru: float,
    skor_lalu: float | None,
    system_p: str,
    user_p: str,
    sentiment_mode: str,
    topik_ronde: str,
    skip_regenerate: bool = False,
) -> tuple[str, dict]:
    """
    FIX-B: HARD ENFORCEMENT change justification.
    Jika agen berubah posisi > threshold tapi tidak ada change marker,
    regenerate 1x dengan instruksi lebih keras.
    Return: (jawaban_final, sentimen_final)
    """
    sentimen_current = score_sentiment(jawaban, topik=topik_ronde, sentiment_mode=sentiment_mode)

    if ronde_ke < 2 or skor_lalu is None:
        return jawaban, sentimen_current

    delta = abs(skor_baru - skor_lalu)
    if delta <= _CHANGE_THRESHOLD:
        return jawaban, sentimen_current

    if _has_change_marker(jawaban):
        return jawaban, sentimen_current

    # FAST MODE: skip regenerate, cuma log warning — hemat 1 LLM call
    if skip_regenerate:
        arah_lalu = "mendukung" if skor_lalu > 0.2 else ("menolak" if skor_lalu < -0.2 else "netral")
        arah_baru = "mendukung" if skor_baru > 0.2 else ("menolak" if skor_baru < -0.2 else "netral")
        print(
            f"[CHANGE_JUSTIFICATION] {nama_agen} R{ronde_ke}: "
            f"berubah {skor_lalu:+.2f}({arah_lalu}) → {skor_baru:+.2f}({arah_baru}), "
            f"tidak ada change marker. FAST MODE — skip regenerate."
        )
        return jawaban, sentimen_current

    # Tidak ada change marker — regenerate
    arah_lalu = "mendukung" if skor_lalu > 0.2 else ("menolak" if skor_lalu < -0.2 else "netral")
    arah_baru = "mendukung" if skor_baru > 0.2 else ("menolak" if skor_baru < -0.2 else "netral")

    print(
        f"[CHANGE_JUSTIFICATION] {nama_agen} R{ronde_ke}: "
        f"berubah {skor_lalu:+.2f}({arah_lalu}) → {skor_baru:+.2f}({arah_baru}), "
        f"tidak ada change marker. Regenerating..."
    )

    user_p_enforce = user_p + (
        f"\n\nPERINTAH WAJIB: Posisimu ronde lalu adalah {arah_lalu.upper()} ({skor_lalu:+.2f}). "
        f"Sekarang kamu tampaknya bergeser ke {arah_baru.upper()}. "
        f"WAJIB jelaskan di output: argumen atau data baru APA yang membuatmu berubah. "
        f"Gunakan frasa seperti: 'Ronde lalu saya {arah_lalu}, tapi sekarang [alasan baru]...' "
        f"atau 'Berdasarkan argumen [nama/poin] tadi, saya revisi posisi karena...'. "
        f"Tanpa penjelasan perubahan, output tidak valid."
    )

    jawaban_retry = call_llm(system_p, user_p_enforce, max_tokens=MAX_TOKENS_AGENT, model=MODEL_AGENT, use_cache=False)
    jawaban_retry = filter_forbidden_opens(jawaban_retry)
    jawaban_retry = _batasi_kalimat(jawaban_retry, max_kalimat=3)
    jawaban_retry = filter_forbidden_opens(jawaban_retry)

    if jawaban_retry and _has_change_marker(jawaban_retry):
        sentimen_retry = score_sentiment(jawaban_retry, topik=topik_ronde, sentiment_mode=sentiment_mode)
        print(f"[CHANGE_JUSTIFICATION] Retry berhasil, ada change marker.")
        return jawaban_retry, sentimen_retry

    # Retry tidak berhasil — tetap pakai output asli
    print(f"[CHANGE_JUSTIFICATION] Retry tidak ada change marker, pakai output asli.")
    return jawaban, sentimen_current


# ---------------------------------------------------------------------------
# ponytail: QA Agent — cek output sesuai topik ga. 1 LLM call, prompt 2 baris.
# Kalau invalid: regenerate 1x dengan feedback. Masih invalid? pakai output asli.
# ---------------------------------------------------------------------------

_QA_SYSTEM = "Kamu reviewer. Cek apakah output diskusi SESUAI dengan topik. Balas HANYA: VALID atau INVALID lalu alasan 1 kalimat."

def _qa_check_topic(topik: str, jawaban: str, system_p: str, user_p: str) -> str:
    """Validasi output agen sesuai topik. 1 retry kalau invalid."""
    if not jawaban or jawaban.startswith("[Error") or jawaban.startswith("[RateLimit"):
        return jawaban

    topik_bersih = topik.split("\n")[0][:150]  # ambil judul utama doang
    prompt = f"Topik: {topik_bersih}\nOutput: {jawaban[:300]}\n\nApakah output ini bahas topik di atas? BALAS: VALID atau INVALID + alasan 1 kalimat."

    hasil = call_llm(_QA_SYSTEM, prompt, max_tokens=80, model=MODEL_AGENT, use_cache=False)

    if "INVALID" in hasil.upper():
        print(f"[QA] {jawaban[:50]}... -> INVALID: {hasil[:80]}")
        # retry 1x dengan feedback
        retry_p = user_p + (
            f"\n\nPERINGATAN QA: Outputmu TIDAK sesuai topik. "
            f"Topik diskusi: {topik_bersih}. "
            f"Fokus ke topik ini. Jangan bahas isu lain."
        )
        jawaban_retry = call_llm(system_p, retry_p, max_tokens=MAX_TOKENS_AGENT, model=MODEL_AGENT, use_cache=False)
        jawaban_retry = filter_forbidden_opens(jawaban_retry)
        jawaban_retry = _batasi_kalimat(jawaban_retry, max_kalimat=3)
        if jawaban_retry and not jawaban_retry.startswith("[Error"):
            return jawaban_retry

    return jawaban


def _hitung_kualitas(ronde_detail: list[dict]) -> dict:
    """
    Penjaga kualitas run: fallback tinggi tidak boleh lolos diam-diam.

    Ambang: <= 0.10 "ok", < 0.30 "warning", >= 0.30 "degraded".
    """
    total = sum(len(r.get("agen", [])) for r in ronde_detail)
    fallback_n = sum(
        1 for r in ronde_detail for a in r.get("agen", []) if a.get("fallback")
    )
    rate = round(fallback_n / total, 3) if total else 0.0
    if rate <= 0.10:
        status = "ok"
    elif rate < 0.30:
        status = "warning"
    else:
        status = "degraded"
    return {
        "fallback_count": fallback_n,
        "total_giliran": total,
        "fallback_rate": rate,
        "status": status,
    }


def _hitung_klaim(ronde_detail: list[dict]) -> dict:
    """Rekap klaim angka asing per run (FASE 2)."""
    giliran_klaim = 0
    semua_angka: list[str] = []
    for r in ronde_detail:
        for a in r.get("agen", []):
            if a.get("klaim_agen"):
                giliran_klaim += 1
                semua_angka.extend(a.get("angka_klaim") or [])
    return {
        "giliran_klaim": giliran_klaim,
        "angka": sorted(set(semua_angka)),
    }


def run_simulation(
    topik: str,
    agents: list[dict],
    jumlah_ronde: int = 3,
    intervensi: str | None = None,
    briefing_real: str = "",
    tier: str = "free",
    scheduler_strategy: str = "influence_aware",
    n_crowd: int = 0,
    data_transparency: dict | None = None,
    konteks_real: dict | None = None,
) -> dict:
    """
    Jalankan simulasi multi-agen multi-ronde.

    RATE LIMIT STRATEGY:
    ─────────────────────────────────────────────────
    • Jalur JSON: agen dalam satu ronde paralel (PARALLEL_AGENTS, maks
      PARALLEL_AGENTS_MAX), tanpa jeda tetap; pacing via TokenBudget + RPM
    • Jalur legacy: SEQUENTIAL dengan AGENT_CALL_DELAY / ROUND_DELAY
    • Token prompt dipangkas: role max 250 char, briefing max 200 char
    • Retry otomatis via call_llm() jika 429
    • Sentiment mode inline = 0 token tambahan per agen
    ─────────────────────────────────────────────────
    """
    FAST_MODE = os.getenv("SIMULATION_FAST", "false").lower() in {"1", "true", "yes", "on"}
    if FAST_MODE:
        print("[SIMULATION] FAST MODE aktif — delay=0, QA/justify skip, max_tokens dipangkas.")

    from .llm_guard import metrics as _llm_metrics, reset_metrics as _reset_metrics

    # konteks_real opsional: main.py sudah mengambilnya sekali. Jangan fetch di sini.
    if konteks_real is None:
        konteks_real = {}

    # Ensure briefing_real is populated from konteks_real if not explicitly provided
    if not briefing_real and konteks_real:
        briefing_real = konteks_real.get("briefing", "")

    # Ensure data_transparency is populated from konteks_real if not explicitly provided
    if data_transparency is None and konteks_real:
        data_transparency = konteks_real.get("data_transparency", {})

    _reset_metrics()
    waktu_mulai = time.time()

    ronde_detail              = []
    log_diskusi               = f"TOPIK: {topik}\n"
    pendapat_ronde_sebelumnya: list[dict] = []
    events: list[SimulationEvent] = []
    n_agents = len(agents)
    sentiment_mode = SENTIMENT_MODE if tier != "free" else "inline"
    llm_for_sentiment = int(sentiment_mode not in ("inline", "ml"))
    # Di FAST_MODE kita skip QA (1 call per agen) dan regenerate justification (~20% agen)
    if USE_LEGACY_PIPELINE:
        if FAST_MODE:
            estimated_llm_calls = n_agents * jumlah_ronde + (0 if tier == "free" else 2)
        else:
            estimated_llm_calls = (
                n_agents * jumlah_ronde
                + (llm_for_sentiment * n_agents * jumlah_ronde)
                + (0 if tier == "free" else 1)
                + (0 if tier == "free" else 2)
            )
    else:
        # Jalur JSON: 1 call per giliran + analisis/aktor di tier normal.
        estimated_llm_calls = n_agents * jumlah_ronde + (0 if tier == "free" else 2)

    # ── Phase 2: Normalisasi agents ke AgentProfile ──
    agent_profiles: list[AgentProfile] = [AgentProfile(**a) for a in agents]
    agent_dicts: list[dict] = []
    for profile, d in zip(agent_profiles, agents):
        d = dict(d)  # copy agar tidak mutasi original
        d.setdefault("_role_singkat", d["role"][:250].rstrip())
        _compute_gaya_str(d)
        agent_dicts.append(d)
    agents = agent_dicts  # kode lama tetap pakai dict

    # Phase 2: track actions via AgentAction
    agent_actions: list[AgentAction] = []

    # Track stance terakhir per agen untuk validasi perubahan & fallback
    stance_terakhir: dict[str, str] = {}

    # Sumber angka sah untuk post-check klaim (briefing + topik, tanpa LLM)
    sumber_angka = f"{briefing_real or ''} {topik}"

    def _proses_satu_agen(
        agen: dict,
        ronde_ke: int,
        topik_ronde: str,
    ) -> dict:
        konteks_memori = build_memory_context(agen)

        # Ronde 1 independen: tidak ada output agen lain di prompt.
        # Ronde 2+: ringkasan ekstraktif ronde sebelumnya, tanpa nama agen.
        if ronde_ke == 1:
            konteks_pengaruh = ""
        else:
            konteks_pengaruh = build_round_summary(
                pendapat_ronde_sebelumnya, kecuali=agen["nama"]
            )

        role_singkat = agen.get("_role_singkat") or agen["role"][:250].rstrip()

        # VOICE ANCHOR — suara unik per persona + satu register bahasa yang dikunci
        voice_anchor = ""
        nama_lower = agen["nama"].lower()
        if "mahasiswa" in nama_lower:
            voice_anchor = (
                "Kamu mahasiswa semester 7, vokal dan blak-blakan. "
                "Register: gue/lo, konsisten sampai akhir. "
                "Sering pakai 'bro', 'sih', 'banget'; mulai langsung ke poin, kadang provokatif. "
                "Quirk: bandingin sama pengalaman kampus."
            )
        elif "founder" in nama_lower or "startup" in nama_lower:
            voice_anchor = (
                "Kamu founder startup tech yang sudah raise seed. "
                "Register: 'saya' dengan sisipan istilah Inggris (pivot, burn rate). "
                "Mulai dengan framing narasi, selalu kaitkan ke market opportunity."
            )
        elif "pengusaha" in nama_lower or "umkm" in nama_lower:
            voice_anchor = (
                "Kamu pengusaha UMKM warung kopi 8 tahun. "
                "Register: gue/lo kasual, sering pakai 'kan', 'lho', 'gitu loh'. "
                "Mulai dari pengalaman lapangan; selalu hitung untung rugi."
            )
        elif "pekerja" in nama_lower or "kantoran" in nama_lower:
            voice_anchor = (
                "Kamu pekerja kantoran HRD 5 tahun. "
                "Register: gue/lo santai-formal, sesekali 'Honestly', 'Realistically'. "
                "Mulai dari pengalaman kerja, realistis soal gaji dan beban kerja."
            )
        elif "pemerintah" in nama_lower or "pejabat" in nama_lower:
            voice_anchor = (
                "Kamu pejabat Eselon III yang technocrat. "
                "Register: 'kami' formal dan manusiawi, jangan pakai 'gue'/'lo'. "
                "Acknowledge dulu, lalu posisi; tutup dengan langkah konkret."
            )
        elif "akademisi" in nama_lower or "dosen" in nama_lower or "peneliti" in nama_lower:
            voice_anchor = (
                "Kamu dosen Psikologi yang bisa jelasin simple. "
                "Register: 'saya' baku tapi mengalir, jangan pakai 'gue'/'lo'. "
                "Framing research, sebut keterbatasan data bila relevan."
            )
        elif "media" in nama_lower or "jurnalis" in nama_lower:
            voice_anchor = (
                "Kamu jurnalis investigatif Metro TV 10 tahun. "
                "Register: 'saya' tegas, jangan pakai 'gue'/'lo'. "
                "Mulai dengan fakta atau pertanyaan retoris; tunjuk inkonsistensi."
            )
        elif "masyarakat" in nama_lower or "umum" in nama_lower or "warga" in nama_lower:
            voice_anchor = (
                "Kamu ibu rumah tangga 45 tahun, anaknya baru lulus SMA. "
                "Register: 'saya' sehari-hari, sering pakai 'aduh', 'iya kan', 'emang sih'. "
                "Mulai dari perasaan dan pengalaman tetangga, bukan statistik."
            )
        elif "oposisi" in nama_lower or "kritis" in nama_lower:
            voice_anchor = (
                "Kamu aktivis mahasiswa yang suka turun ke jalan. "
                "Register: 'kami' rakyat, vokal, jangan pakai 'gue'/'lo'. "
                "Mulai dengan serangan langsung ke dampak kebijakan."
            )

        # ERROR-1 FIX: hitung skor_ronde_lalu DI SINI
        skor_ronde_lalu = None
        if len(agen.get("memori", [])) > 0:
            last_mem = agen["memori"][-1]
            skor_ronde_lalu = last_mem.get("skor", None)
        stance_ronde_lalu = stance_terakhir.get(agen["nama"])

        # ISSUE #23 — stance rule khusus Pemerintah
        stance_rule = ""
        if "pemerintah" in agen["nama"].lower() or "pejabat pemerintah" in agen.get("role", "").lower():
            stance_rule = (
                "Kamu PERWAKILAN PEMERINTAH — bicara atas nama pemerintah, bukan dari luar. "
                "Jangan bilang 'pemerintah harus'. Akui tantangan sebagai hal yang sedang ditangani. "
                "Tutup dengan langkah konkret."
            )

        # BUG-08 FIX: stance lock khusus Pemerintah harus masuk sebelum system_p dibuat.
        is_pemerintah = "pemerintah" in agen["nama"].lower()
        if is_pemerintah and skor_ronde_lalu is not None and skor_ronde_lalu > 0.0:
            stance_rule += (
                "Kamu SUDAH mendukung sebelumnya; jangan menolak, paling jauh netral."
            )

        akademisi_rule = ""
        if "akademisi" in agen["nama"].lower() or "dosen" in agen.get("role", "").lower():
            akademisi_rule = (
                "JANGAN tutup dengan frasa kayak 'perlu dipertimbangkan' atau 'perlu diteliti lebih lanjut'. "
                "Kamu SUDAH mempertimbangkan — sekarang kasih kesimpulanmu yang tegas. "
            )

        conviction_rule = ""
        if "akademisi" in agen["nama"].lower() or "dosen" in agen.get("role", "").lower():
            memori_skor = [m.get("skor", 0) for m in agen.get("memori", []) if "skor" in m]
            dua_ronde_netral = len(memori_skor) >= 2 and all(abs(s) < 0.2 for s in memori_skor[-2:])

            conviction_rule = (
                "Kamu HARUS punya posisi JELAS — netral bukan berarti objektif. "
                "Netral cuma valid kalau bukti benar-benar seimbang DAN kamu JELASKAN kenapa. "
                "Kalau ronde lalu kamu sudah punya posisi, JANGAN tiba-tiba netral "
                "kecuali ada DATA BARU yang fundamental. "
            )
            if dua_ronde_netral:
                conviction_rule += (
                    "PERINGATAN: Kamu SUDAH 2 RONDE NETRAL. "
                    "INI TIDAK BOLEH TERUS. Ambil posisi SEKARANG — Mendukung atau Menolak. "
                    "Jelaskan data mana yang bikin kamu condong. "
                )
            if skor_ronde_lalu is not None and abs(skor_ronde_lalu) > 0.4:
                conviction_rule += (
                    "\nPosisi kamu ronde lalu KUAT. Berubah drastis dalam SATU ronde "
                    "tidak valid secara ilmiah. Bergerak SATU LANGKAH aja:\n"
                    "  • Mendukung kuat → Mendukung lemah atau Netral\n"
                    "  • Menolak kuat → Menolak lemah atau Netral\n"
                )

        # SYSTEM PROMPT — natural, bukan rule-book
        system_p = (
            f"Kamu {agen['nama']}. {role_singkat}\n"
            f"{voice_anchor}\n"
            + stance_rule
            + akademisi_rule
            + conviction_rule
            + "\nATURAN (melanggar = output dihapus):\n"
            "1. Jangan sebut role/jabatanmu, jangan buka dengan 'Saya pikir'.\n"
            "2. Jangan bilang tak punya opini; jangan ulang argumen orang lain.\n"
            "3. Dilarang menyebut angka atau statistik yang tidak ada di BRIEFING atau "
            "TOPIK. Jika butuh data, tulis 'perlu data'.\n"
            "4. 2-3 kalimat, maksimal 35 kata, seperti orang ngobrol.\n"
        )

        parts = []

        # BUG-10 FIX: Jika ronde 1 dan agen punya initial_stance
        if ronde_ke == 1 and "initial_stance" in agen and not konteks_memori:
            initial = agen.get("initial_stance", 0.0)
            if isinstance(initial, (int, float)):
                if initial > 0.2:
                    parts.append(
                        "POSISI AWAL: cenderung MENDUKUNG. Ubah hanya kalau ada argumen baru yang kuat."
                    )
                elif initial < -0.2:
                    parts.append(
                        "POSISI AWAL: cenderung MENOLAK. Ubah hanya kalau ada argumen baru yang kuat."
                    )
                else:
                    parts.append("POSISI AWAL: NETRAL. Ambil posisi kalau bukti condong.")

        if konteks_memori:
            parts.append(konteks_memori)

        # Aturan eksplisit perubahan posisi (wajib ada di Ronde 2+, tidak boleh dipangkas)
        aturan_berubah = ""
        if ronde_ke >= 2:
            aturan_berubah = (
                "Kalau stance-mu beda dari ronde sebelumnya, isi berubah_karena dengan "
                "pemicunya dalam satu kalimat; kalau sama, kosongkan."
            )
            parts.append(aturan_berubah)

        # Stabilization PR — BUG #27: change_rule berbasis skor sentimen nyata
        if skor_ronde_lalu is not None and len(agen.get("memori", [])) >= 2:
            if skor_ronde_lalu > 0.2:
                parts.append(
                    "Terakhir kamu cenderung MENDUKUNG. "
                    "Kalau sekarang kamu berubah, JELASKAN data atau argumen baru yang bikin kamu pikir ulang."
                )
            elif skor_ronde_lalu < -0.2:
                parts.append(
                    "Terakhir kamu cenderung MENOLAK. "
                    "Kalau sekarang kamu berubah, JELASKAN data atau argumen baru yang bikin kamu pikir ulang."
                )
            else:
                parts.append(
                    "Terakhir kamu netral. Kalau sekarang kamu ambil posisi kuat, JELASKAN kenapa."
                )

        if ronde_ke == 1:
            # Semua agen Ronde 1 dapat briefing yang sama, tanpa saling melihat output.
            if briefing_real:
                parts.append(f"Info konteks: {briefing_real[:500]}")
            parts.append("Sampaikan posisimu yang paling kuat.")
        elif konteks_pengaruh:
            parts.append(konteks_pengaruh)
            parts.append(
                "Tanggapi ringkasan itu — setuju atau sanggah, pakai katamu sendiri, tanpa menyebut nama."
            )
        # Phase 3: inject event impact note for this agent
        _event_impacts = event_impacts.get(intervensi, {}) if intervensi else {}
        impact_note = get_agent_impact_note(agen["nama"], _event_impacts)
        if impact_note:
            parts.append(impact_note)

        # Phase 5: cegah repetisi argumen dari structured memory
        from .core.memory_store import AgentMemoryStore
        if "_memory_store" in agen:
            _store: AgentMemoryStore = agen["_memory_store"]
            _fresh_prompt = _store.arguments.get_fresh_argument_prompt()
            if _fresh_prompt:
                parts.append(_fresh_prompt)

        parts.append(f"Topik: {topik_ronde[:130]}\n\nTanggapannya?")
        user_p = "\n".join(parts)

        if USE_LEGACY_PIPELINE:
            # Jalur lama tidak diubah.
            if len(user_p) > 900:
                parts_trimmed = []
                if konteks_memori:
                    parts_trimmed.append(konteks_memori[:80])
                if ronde_ke == 1 and briefing_real:
                    parts_trimmed.append(f"Info konteks: {briefing_real[:320]}")
                elif konteks_pengaruh:
                    parts_trimmed.append("\n".join(konteks_pengaruh.split("\n")[:4]))
                parts_trimmed.append(f"Topik: {topik_ronde[:130]}\n\nTanggapannya?")
                user_p = "\n".join(parts_trimmed)
        elif len(user_p) > BATAS_TRIM_JSON:
            # Jalur JSON: posisi agen, aturan berubah_karena, dan ringkasan pihak lain
            # tidak boleh dipangkas. Yang dipangkas hanya briefing/topik panjang.
            parts_trimmed = []
            if konteks_memori:
                parts_trimmed.append(konteks_memori)
            if aturan_berubah:
                parts_trimmed.append(aturan_berubah)
            if ronde_ke == 1 and briefing_real:
                parts_trimmed.append(f"Info konteks: {briefing_real[:200]}")
            if konteks_pengaruh:
                parts_trimmed.append(konteks_pengaruh)
            parts_trimmed.append(f"Topik: {topik_ronde[:130]}\n\nTanggapannya?")
            user_p = "\n".join(parts_trimmed)

        # ── Jalur baru: satu call LLM per giliran, output JSON ──────────────
        if not USE_LEGACY_PIPELINE:
            turn = execute_turn(
                llm=lambda s, u: call_llm(
                    s, u,
                    max_tokens=TURN_MAX_TOKENS,
                    model=MODEL_AGENT,
                    use_cache=False,
                    auto_complete=False,          # JSON tidak boleh dipotong
                    response_format=TURN_RESPONSE_FORMAT,
                ),
                system_p=system_p,
                user_p=user_p,
                prev_stance=stance_ronde_lalu,
                prev_score=skor_ronde_lalu,
                llm_pemicu=lambda s, u: call_llm(
                    s, u,
                    max_tokens=PEMICU_MAX_TOKENS,
                    model=MODEL_AGENT,
                    use_cache=False,
                    auto_complete=False,
                    response_format=PEMICU_RESPONSE_FORMAT,
                ),
            )
            if turn["fallback"]:
                print(
                    f"[GiliranFallback] {agen['nama']} R{ronde_ke}: "
                    f"output JSON tidak valid, pakai stance {turn['stance']}"
                )

            # Aturan realisme: score dibatasi agar tidak loncat > _DELTA_CAP per ronde.
            # Ini clamp Python, bukan hasil model. Stance tetap seperti yang ditulis agen.
            turn["score"] = _apply_delta_cap(turn["score"], skor_ronde_lalu, agen["nama"], ronde_ke)

            # Post-check angka: klaim di luar briefing/topik ditandai, bukan diubah.
            asing = angka_klaim(turn["alasan"], sumber_angka)
            return {
                "nama":     agen["nama"],
                "pendapat": turn["alasan"],
                "sentimen": {
                    "label": _STANCE_KE_LABEL[turn["stance"]],
                    "skor":  turn["score"],
                },
                "pengaruh":        agen.get("pengaruh", 0.5),
                "stance":          turn["stance"],
                "score":           turn["score"],
                "score_asli":      turn["score_asli"],
                "score_disesuaikan": turn["score_disesuaikan"],
                "alasan":          turn["alasan"],
                "berubah_karena":  turn["berubah_karena"],
                "perubahan_tanpa_alasan": turn.get("perubahan_tanpa_alasan", False),
                "sesuai_topik":    turn["sesuai_topik"],
                "fallback":        turn["fallback"],
                "klaim_agen":      bool(asing),
                "angka_klaim":     asing,
            }
        # ── Jalur lama (USE_LEGACY_PIPELINE=true) ──────────────────────────
        jawaban = call_llm(system_p, user_p, max_tokens=MAX_TOKENS_AGENT, model=MODEL_AGENT, use_cache=False)
        if jawaban.startswith(("[Error", "[RateLimit", "[Offline")):
            # Jangan simpan teks error sebagai opini agen — outer handler
            # akan mencatat placeholder netral untuk agen ini.
            raise RuntimeError(jawaban[:200])
        jawaban = filter_forbidden_opens(jawaban)
        jawaban = _batasi_kalimat(jawaban, max_kalimat=3)
        jawaban = filter_forbidden_opens(jawaban)

        # ponytail: QA check — validasi topik sebelum lanjut. 1 LLM call tambahan, prompt 2 baris.
        # FAST MODE: skip QA check (hemat 1 call per agen)
        if not FAST_MODE:
            jawaban = _qa_check_topic(topik_ronde, jawaban, system_p, user_p)

        sentimen = score_sentiment(jawaban, topik=topik_ronde, sentiment_mode=sentiment_mode)

        # FIX-A: Clamp delta skor agar tidak loncat terlalu jauh
        skor_capped = _apply_delta_cap(sentimen["skor"], skor_ronde_lalu, agen["nama"], ronde_ke)
        if skor_capped != sentimen["skor"]:
            # Update label setelah capping
            if skor_capped > 0.2:
                label_capped = "positif"
            elif skor_capped < -0.2:
                label_capped = "negatif"
            else:
                label_capped = "netral"
                skor_capped = 0.0
            sentimen = {"label": label_capped, "skor": skor_capped}

        # FIX-B: HARD ENFORCEMENT change justification (regenerate jika perlu)
        # FAST MODE: skip regenerate, cuma clamp skor — hemat 1 call LLM per agen yg berubah drastis
        jawaban, sentimen = _validate_and_enforce_change_justification(
            nama_agen=agen["nama"],
            ronde_ke=ronde_ke,
            jawaban=jawaban,
            skor_baru=sentimen["skor"],
            skor_lalu=skor_ronde_lalu,
            system_p=system_p,
            user_p=user_p,
            sentiment_mode=sentiment_mode,
            topik_ronde=topik_ronde,
            skip_regenerate=FAST_MODE,
        )

        # Re-apply delta cap setelah regenerate (kalau skor berubah lagi)
        skor_final = _apply_delta_cap(sentimen["skor"], skor_ronde_lalu, agen["nama"], ronde_ke)
        if skor_final != sentimen["skor"]:
            if skor_final > 0.2:
                label_final = "positif"
            elif skor_final < -0.2:
                label_final = "negatif"
            else:
                label_final = "netral"
                skor_final = 0.0
            sentimen = {"label": label_final, "skor": skor_final}

        # Prompt-level conviction_rule sering diabaikan LLM → retry dengan instruksi lebih keras
        # FAST MODE: skip retry LLM, langsung fallback ke forced_skor
        if not FAST_MODE and ("akademisi" in agen.get("nama", "").lower() or "dosen" in agen.get("role", "").lower()):
            if sentimen["label"] == "netral":
                memori_skor = [m.get("skor", 0.0) for m in agen.get("memori", []) if "skor" in m]
                if len(memori_skor) >= 1 and abs(memori_skor[-1]) < 0.2:
                    user_p += (
                        "\nKAMU SUDAH 2+ RONDE NETRAL. "
                        "INI TIDAK BOLEH TERUS. Ambil posisi SEKARANG — MENDUKUNG atau MENOLAK. "
                        "Tulis argumen yang bikin kamu condong ke satu arah. "
                        "JANGAN KEMBALIKAN NETRAL."
                    )
                    _retry_jawaban = call_llm(system_p, user_p, max_tokens=MAX_TOKENS_AGENT, model=MODEL_AGENT, use_cache=False)
                    _retry_jawaban = filter_forbidden_opens(_retry_jawaban)
                    _retry_jawaban = _batasi_kalimat(_retry_jawaban, max_kalimat=3)
                    _retry_jawaban = filter_forbidden_opens(_retry_jawaban)
                    _retry_sentimen = score_sentiment(_retry_jawaban, topik=topik_ronde, sentiment_mode=sentiment_mode)
                    if _retry_sentimen["label"] != "netral":
                        jawaban = _retry_jawaban
                        sentimen = _retry_sentimen

        # BUG-19 ENFORCEMENT: post-processing — paksa skor jika masih netral
        if ("akademisi" in agen.get("nama", "").lower() or "dosen" in agen.get("role", "").lower()):
            if sentimen["label"] == "netral":
                memori_skor_fix = [m.get("skor", 0.0) for m in agen.get("memori", []) if "skor" in m]
                if len(memori_skor_fix) >= 1 and abs(memori_skor_fix[-1]) < 0.2:
                    initial = agen.get("initial_stance", 0.0)
                    forced_skor = 0.3 if initial >= 0 else -0.3
                    sentimen = {"label": "positif" if forced_skor > 0 else "negatif", "skor": forced_skor}

        return {
            "nama":     agen["nama"],
            "pendapat": jawaban,
            "sentimen": sentimen,
            "pengaruh": agen.get("pengaruh", 0.5),
        }

    # Phase 3: track event impacts per-agent
    event_impacts: dict[str, dict[str, float]] = {}

    def _jalan_giliran(agen: dict, ronde_ke: int, topik_ronde: str) -> tuple[dict, bool]:
        """Satu giliran agen, termasuk penanganan gagal. Aman dipanggil paralel:
        hanya membaca state ronde sebelumnya dan menulis ke dict agennya sendiri."""
        try:
            return _proses_satu_agen(agen, ronde_ke, topik_ronde), False
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            print(f"[Error] {agen['nama']} ronde {ronde_ke}: {error_type}: {error_msg}")
            return {
                "nama":     agen["nama"],
                "pendapat": f"(gagal: {error_msg[:200]})",
                "sentimen": None,  # tidak ada sentimen untuk giliran gagal
                "pengaruh": agen.get("pengaruh", 0.5),
                "status":   "gagal",
                "alasan_gagal": error_msg[:500],
            }, True

    for ronde_ke in range(1, jumlah_ronde + 1):
        topik_ronde = topik
        active_event_impacts: dict[str, float] = {}
        if intervensi and ronde_ke == (jumlah_ronde // 2) + 1:
            agent_names = [a["nama"] for a in agents]
            event = SimulationEvent(
                tipe="intervensi",
                ronde=ronde_ke,
                deskripsi=intervensi,
                dampak_hint={},
            )
            active_event_impacts = compute_event_impact(event, agent_names)
            event.actual_impacts = active_event_impacts
            events.append(event)
            event_narasi = build_event_narrative(event, active_event_impacts)
            topik_ronde = f"{topik}\n{event_narasi}"
            log_diskusi += f"\n--- INTERVENSI RONDE {ronde_ke}: {intervensi} ---\n"
            event_impacts[intervensi] = active_event_impacts

        output_ronde       = {"ronde": ronde_ke, "agen": []}
        pendapat_ronde_ini = []

        order = get_speaking_order(agents, ronde_ke, strategy=scheduler_strategy)
        urutan_agen = [agents[i] for i in order]

        # Baris A: jalankan semua agen ronde ini. pool.map menjaga urutan roster,
        # jadi hasilnya deterministik walau selesai tidak berurutan.
        if not USE_LEGACY_PIPELINE and PARALLEL_AGENTS and len(urutan_agen) > 1:
            with ThreadPoolExecutor(
                max_workers=min(PARALLEL_AGENTS_MAX, len(urutan_agen))
            ) as pool:
                hasil_agen = list(pool.map(
                    lambda a: _jalan_giliran(a, ronde_ke, topik_ronde), urutan_agen
                ))
        else:
            hasil_agen = []
            for i, a in enumerate(urutan_agen):
                hasil_agen.append(_jalan_giliran(a, ronde_ke, topik_ronde))
                bukan_akhir = not (i == len(urutan_agen) - 1 and ronde_ke == jumlah_ronde)
                if USE_LEGACY_PIPELINE and not FAST_MODE and bukan_akhir:
                    time.sleep(AGENT_CALL_DELAY)

        # Barrier: memory, stance_terakhir, dan daftar pendapat baru diperbarui
        # setelah semua agen ronde ini selesai.
        for agen, (res, res_failed) in zip(urutan_agen, hasil_agen):
            # Hanya catat ke output ronde (untuk transparansi), TAMBAHKAN status
            output_ronde["agen"].append({
                "nama": res["nama"],
                "pendapat": res["pendapat"],
                "sentimen": res["sentimen"],
                "status":   res.get("status", "sukses"),
                "alasan_gagal": res.get("alasan_gagal"),
                "stance":          res.get("stance"),
                "score":           res.get("score"),
                "score_asli":      res.get("score_asli"),
                "score_disesuaikan": res.get("score_disesuaikan", False),
                "alasan":          res.get("alasan"),
                "berubah_karena":  res.get("berubah_karena"),
                "perubahan_tanpa_alasan": res.get("perubahan_tanpa_alasan", False),
                "sesuai_topik":    res.get("sesuai_topik"),
                "fallback":        res.get("fallback", False),
                "klaim_agen":      res.get("klaim_agen", False),
                "angka_klaim":     res.get("angka_klaim", []),
            })
            if res.get("stance"):
                stance_terakhir[res["nama"]] = res["stance"]

            if not res_failed:
                # Giliran sukses: update memory, log, aggregator structures
                agent_actions.append(AgentAction(
                    agent_nama=agen["nama"],
                    ronde=ronde_ke,
                    tipe_aksi="berpendapat",
                    pendapat=res["pendapat"],
                    sentimen=res["sentimen"],
                ))

                update_agent_memory(agen, ronde_ke, res["pendapat"], res["sentimen"],
                                    all_opinions=pendapat_ronde_ini)
                log_diskusi += f"\n[R{ronde_ke}] {agen['nama']}: {res['pendapat']}\n"

                entry = {
                    "nama": res["nama"], "pendapat": res["pendapat"],
                    "sentimen": res["sentimen"], "pengaruh": res["pengaruh"],
                }
                pendapat_ronde_ini.append(entry)
            else:
                print(f"[GiliranGagal] {agen['nama']} R{ronde_ke}: {res['alasan_gagal'][:120]}")

        ronde_detail.append(output_ronde)
        pendapat_ronde_sebelumnya = pendapat_ronde_ini

        # Jeda hanya di jalur legacy; jalur JSON dipacing TokenBudget + rate limiter.
        if USE_LEGACY_PIPELINE and not FAST_MODE and ronde_ke < jumlah_ronde:
            time.sleep(ROUND_DELAY)

    # ── GraphRAG extraction ──
    graf_data = (
        {"entitas": [], "relasi": [], "disabled": True, "reason": "free_tier_mode"}
        if tier == "free" else extract_entities(topik, log_diskusi)
    )

    # ── Sentimen agregat (hanya giliran sukses) ──
    sentimen_agregat = {}
    for agen in agents:
        tren = [
            a["sentimen"]["skor"]
            for ronde in ronde_detail
            for a in ronde["agen"]
            if a["nama"] == agen["nama"] and a.get("status") == "sukses" and a.get("sentimen") is not None
        ]
        sentimen_agregat[agen["nama"]] = tren

    # ── Analisis akhir + aktor kunci ──
    # Initialize ringkasan_terstruktur for all tiers
    ringkasan_terstruktur = {}
    if tier == "free":
        analisis_raw = _analisis_fallback_text(topik, sentimen_agregat)
        pengaruh_map, volatilitas, _ = _build_ringkasan_agen(agents, sentimen_agregat)
        aktor_analisis = _aktor_fallback(pengaruh_map, volatilitas, sentimen_agregat, data_transparency)
    else:
        analisis_raw, aktor_analisis, ringkasan_terstruktur = _analisis_dan_aktor(
            topik, log_diskusi, agents, sentimen_agregat, data_transparency
        )
    analisis_raw = _strip_emoji(analisis_raw)
    # Store ringkasan_terstruktur for later use in hasil_dict
    _ringkasan_terstruktur_temp = ringkasan_terstruktur
    _ringkasan_kalimat_temp = _susun_ringkasan_kalimat(sentimen_agregat, ringkasan_terstruktur)

    # ponytail: Parse RISIKO UTAMA dari teks analisis — regex, 2 baris
    risiko_match = re.search(r"RISIKO UTAMA:\s*(.+?)(?:\n\n|\Z)", analisis_raw, re.DOTALL | re.IGNORECASE)
    risiko_utama = risiko_match.group(1).strip() if risiko_match else ""
    if risiko_match:
        analisis_raw = re.sub(r"\n?\s*RISIKO UTAMA:.*?(?:\n\n|\Z)", "", analisis_raw, flags=re.DOTALL | re.IGNORECASE).strip()

    prediksi = _parse_prediksi(analisis_raw)

    # Phase 2: Rebuild simulation_state
    simulation_state = simulation_result_to_state(
        topik=topik,
        ronde_ke=jumlah_ronde,
        agents=agents,
        sentimen_agregat=sentimen_agregat,
        events=events,
    )
    simulation_state_payload = (
        simulation_state.model_dump()
        if hasattr(simulation_state, "model_dump")
        else simulation_state.dict()
    )
    simulation_state_payload["agent_actions"] = [
        a.model_dump() for a in agent_actions
    ]

    # Phase 3: Generate event_explanations
    agent_names = [a["nama"] for a in agents]
    event_explanations = generate_event_explanation(events, agent_names)

    simulation_quality = _build_simulation_quality(
        n_agents=n_agents,
        jumlah_ronde=jumlah_ronde,
        estimated_llm_calls=estimated_llm_calls,
        tier=tier,
    )

    # ponytail: CrowdPool removed — crowd_data & crowd_distribution are always empty
    crowd_data = None

    # FIX-C: Heuristic selalu jadi SINGLE SOURCE OF TRUTH untuk prediksi utama.
    # ML hanya eksperimental dan ditampilkan terpisah di explainability report.
    quality_score = float(simulation_quality.get("score", 1.0) or 1.0)
    heuristic_result = heuristic_predict(
        sentimen_agregat=sentimen_agregat,
        n_agents=n_agents,
        n_rounds=jumlah_ronde,
        quality_score=quality_score,
        events=events,
    )

    # FIX-C: prediksi final SELALU dari heuristic (tidak ada dua sumber)
    prediksi_final = heuristic_result["prediksi"]
    prediction_confidence = heuristic_result["confidence"]
    prediction_reasoning = heuristic_result["reasoning"]

    # FIX-E: Build confidence yang konsisten — satu angka, satu label, satu alasan
    confidence_summary = _build_confidence_summary(
        confidence_dict=prediction_confidence,
        n_agents=n_agents,
        jumlah_ronde=jumlah_ronde,
        sentimen_agregat=sentimen_agregat,
    )
    hasil_dict = {
        "ronde_detail":      ronde_detail,
        "graf_data":         graf_data,
        "analisis":          analisis_raw,
        "prediksi":          prediksi_final,  # FIX-C: selalu heuristic
        "sentimen_agregat":  sentimen_agregat,
        "crowd_data":        crowd_data,
        "simulation_state":   simulation_state_payload,
        "event_explanations": event_explanations,
        "simulation_metrics": {
            "polarization_score": simulation_state.polarization_score,
            "consensus_score":    simulation_state.consensus_score,
            "event_count":        len(events),
            "agent_count":        len(simulation_state.agent_states),
            "crowd_size":         n_crowd,
        },
        "simulation_quality": simulation_quality,
        "runtime_mode": {
            "tier": tier,
            "free_tier_like": tier == "free",
            "sentiment_mode": sentiment_mode,
            "graph_llm_enabled": tier != "free",
            "final_analysis_llm_enabled": tier != "free",
            "estimated_llm_calls": estimated_llm_calls,
            "scheduler_strategy": scheduler_strategy,
            "scheduler_label": get_strategy_display(scheduler_strategy),
            "n_crowd": n_crowd,
            "fast_mode": FAST_MODE,
            "pipeline": "legacy" if USE_LEGACY_PIPELINE else "json",
        },
        "events":           simulation_state_payload.get("events", []),
        "jumlah_ronde":     jumlah_ronde,
        "topik":            topik,
        "intervensi":       intervensi,
        "aktor_analisis":       aktor_analisis,
        "risiko_utama":         risiko_utama,
        "prediction_confidence": prediction_confidence,
        "prediction_reasoning":  prediction_reasoning,
        "confidence_summary":    confidence_summary,  # FIX-E: field baru, konsisten
        # BUG #10 FIX: prediction_source sebagai flat field, bukan dict â hindari bentrok dengan main.py
        "prediction_source": "heuristic",
        "giliran_gagal": _build_giliran_gagal_summary(ronde_detail),
        "model_info": {
            "agen":           MODEL_AGENT,
            "analisis":       MODEL_ANALYSIS,
            "sentiment_mode": SENTIMENT_MODE,
        },
    }

    # NEW: Sumber kebenaran tunggal untuk skenario (resolve_scenario)
    skenario_resolved = resolve_scenario(
        sentimen_agregat=sentimen_agregat,
        n_agents=n_agents,
        n_rounds=jumlah_ronde,
        quality_score=quality_score,
        events=events,
    )
    hasil_dict["skenario_resolved"] = skenario_resolved

    # NEW: Kepercayaan sumber
    sumber_status_val = konteks_real.get("sumber_status", "kosong")
    sumber_relevan_val = len(konteks_real.get("berita", []))
    hasil_dict["kepercayaan_sumber"] = kepercayaan_sumber(
        sumber_status=sumber_status_val,
        sumber_relevan=sumber_relevan_val,
        isi_dibaca=False,  # hanya judul/ringkasan, tidak isi penuh
        n_agen=n_agents,
        n_ronde=jumlah_ronde,
    )

    # NEW: Teks polarisasi (digunakan di laporan)
    hasil_dict["teks_polarisasi"] = teks_polarisasi(
        skor_akhir={nama: tren[-1] for nama, tren in sentimen_agregat.items() if tren},
        total_peserta=n_agents,
    )

    # NEW: Swing voter terfilter
    hasil_dict["swing_voter_terfilter"] = swing_voter_terfilter(
        sentimen_agregat=sentimen_agregat,
        ambang=0.15,
    )

    # NEW: Ringkasan terstruktur dari LLM (isi dari _analisis_dan_aktor return)
    hasil_dict["ringkasan_terstruktur"] = _ringkasan_terstruktur_temp
    hasil_dict["ringkasan_kalimat"] = _ringkasan_kalimat_temp

    hasil_dict["explainability_report"] = generate_report(hasil_dict)

    kualitas = _hitung_kualitas(ronde_detail)
    hasil_dict["kualitas"] = kualitas
    hasil_dict["klaim_angka"] = _hitung_klaim(ronde_detail)

    # Statistik run (dari metrik llm_guard): untuk mengukur efek paralel & pacing.
    _stat = _llm_metrics()
    hasil_dict["statistik_run"] = {
        "pipeline": "legacy" if USE_LEGACY_PIPELINE else "json",
        "parallel": bool(PARALLEL_AGENTS and not USE_LEGACY_PIPELINE),
        "parallel_max": PARALLEL_AGENTS_MAX,
        "durasi_detik": round(time.time() - waktu_mulai, 2),
        "panggilan_llm": _stat["calls"],
        "token_prompt": _stat["prompt_tokens"],
        "token_completion": _stat["completion_tokens"],
        "token_total": _stat["prompt_tokens"] + _stat["completion_tokens"],
        "rate_limited_429": _stat["rate_limited_429"],
        "tunggu_token_budget_detik": round(_stat["budget_wait"], 2),
        "tunggu_rpm_detik": round(_stat["rpm_wait"], 2),
    }
    if kualitas["status"] != "ok":
        print(
            f"[KUALITAS] status={kualitas['status']} — "
            f"{kualitas['fallback_count']}/{kualitas['total_giliran']} giliran fallback "
            f"({kualitas['fallback_rate']:.0%}). Hasil studi kasus dari run ini "
            f"{'tidak layak dirakit' if kualitas['status'] == 'degraded' else 'perlu dibaca hati-hati'}."
        )

    # Simpan run ke file (atomik, thread-safe)
    try:
        from .services.run_store import save_run
        run_id = save_run(hasil_dict)
        hasil_dict["_run_id"] = run_id
        print(f"[RUN_STORE] saved run_id={run_id}")
    except Exception as e:
        print(f"[RUN_STORE] save failed: {e}")

    # Assemble + simpan CaseStudy (narator + computed) — tidak boleh gagalkan simulasi
    try:
        from .services.casestudy_assemble import assemble_case_study, save_case_study
        case_dict = assemble_case_study(run_id)
        save_case_study(run_id, case_dict)
        print(f"[CASE_STUDY] assembled and saved for run_id={run_id}")
    except Exception as exc:
        print(
            f"[CASE_STUDY] failed for run_id={run_id}: "
            f"{type(exc).__name__}: {exc}"
        )

    return hasil_dict


# ---------------------------------------------------------------------------
# Ringkasan Giliran Gagal
# ---------------------------------------------------------------------------

def _build_giliran_gagal_summary(ronde_detail: list[dict]) -> dict:
    """
    Bangun ringkasan giliran sukses vs gagal per agen per ronde.
    Digunakan untuk transparansi: user bisa lihat data mana yang bolong.
    """
    summary = {}
    for ronde in ronde_detail:
        r = ronde["ronde"]
        summary[f"ronde_{r}"] = {}
        for a in ronde["agen"]:
            nama = a["nama"]
            status = a.get("status", "sukses")
            if nama not in summary[f"ronde_{r}"]:
                summary[f"ronde_{r}"][nama] = {"sukses": 0, "gagal": 0}
            if status == "gagal":
                summary[f"ronde_{r}"][nama]["gagal"] += 1
                summary[f"ronde_{r}"][nama]["alasan"] = a.get("alasan_gagal")
            else:
                summary[f"ronde_{r}"][nama]["sukses"] += 1
    # Total keseluruhan
    total_sukses = sum(
        v["sukses"] for r in summary.values() for v in r.values()
    )
    total_gagal = sum(
        v["gagal"] for r in summary.values() for v in r.values()
    )
    summary["total"] = {"sukses": total_sukses, "gagal": total_gagal}
    return summary


# ---------------------------------------------------------------------------
# FIX-E: Confidence Summary — satu sumber, konsisten
# ---------------------------------------------------------------------------

def _build_confidence_summary(
    confidence_dict: dict,
    n_agents: int,
    jumlah_ronde: int,
    sentimen_agregat: dict,
) -> dict:
    """
    FIX-E: Build confidence summary yang konsisten — satu angka, satu label.
    Ini yang ditampilkan di laporan. Tidak ada dua angka yang kontradiktif.
    """
    if isinstance(confidence_dict, dict):
        score = float(confidence_dict.get("score", 0.0))
        label = confidence_dict.get("label", "rendah")
        alasan = confidence_dict.get("alasan", [])
    else:
        score = float(confidence_dict) if confidence_dict else 0.0
        label = "rendah" if score < 0.4 else ("sedang" if score < 0.7 else "tinggi")
        alasan = []

    # Hitung variance sebagai konteks
    all_scores = [s for tren in sentimen_agregat.values() for s in tren if tren]
    import statistics as _stats
    variance = _stats.variance(all_scores) if len(all_scores) > 1 else 0.0

    n_pos = sum(1 for tren in sentimen_agregat.values() if tren and tren[-1] > 0.2)
    n_neg = sum(1 for tren in sentimen_agregat.values() if tren and tren[-1] < -0.2)
    n_net = len(sentimen_agregat) - n_pos - n_neg

    return {
        "score": score,
        "score_persen": round(score * 100),
        "label": label,
        "alasan": alasan,
        "konteks": {
            "n_agen": n_agents,
            "n_ronde": jumlah_ronde,
            "variance_sentimen": round(variance, 3),
            "distribusi_akhir": {
                "mendukung": n_pos,
                "menolak": n_neg,
                "netral": n_net,
            },
        },
        "interpretasi": (
            f"Prediksi ini EKSPLORASI, bukan keputusan final. "
            f"Variansi sentimen {variance:.2f} — {'opini sangat terbelah' if variance > 0.3 else 'opini relatif searah'}. "
            f"Distribusi akhir: {n_pos} mendukung, {n_neg} menolak, {n_net} netral dari {len(sentimen_agregat)} agen."
        ),
    }


# ---------------------------------------------------------------------------
# Analisis Gabungan — 1 call LLM-JSON (FIX #3)
# ---------------------------------------------------------------------------

def _resolve_nama(s: str, pengaruh_map: dict, nama_valid: list) -> str:
    s = s.strip()
    if s in pengaruh_map:
        return s
    for v in nama_valid:
        if v.lower() == s.lower() or s.lower() in v.lower():
            return v
    return s


def _label_sentimen(skor: float) -> str:
    if skor > 0.2:  return "positif"
    if skor < -0.2: return "negatif"
    return "netral"


def _parse_ringkasan_json(teks: str) -> tuple[dict, str]:
    """Ambil JSON object dari keluaran LLM dan buang dari teks.

    Tahan code fence dan teks di sekitarnya. Jika JSON rusak, objek tetap
    dibuang dari teks supaya JSON mentah tidak tampil di ringkasan.
    """
    tanpa_fence = re.sub(r"```(?:json)?", "", teks or "", flags=re.IGNORECASE)
    tanpa_fence = tanpa_fence.replace("```", "")

    parsed: dict = {}
    objek_terpakai = ""
    kandidat = set(re.findall(r"\{[^{}]*\}", tanpa_fence, re.DOTALL))
    kandidat.update(re.findall(r"\{.*\}", tanpa_fence, re.DOTALL))
    for kandidat_json in sorted(kandidat, key=len, reverse=True):
        try:
            data = json.loads(kandidat_json)
        except Exception:
            continue
        if isinstance(data, dict) and data and all(isinstance(k, str) for k in data):
            parsed = {k: v for k, v in data.items() if isinstance(v, str)}
            objek_terpakai = kandidat_json
            break

    bersih = tanpa_fence
    if objek_terpakai:
        bersih = bersih.replace(objek_terpakai, " ")
    # Buang sisa blok JSON yang gagal di-parse.
    bersih = re.sub(r"\{[^{}]*\}", " ", bersih, flags=re.DOTALL)
    if "{" in bersih:
        bersih = re.sub(r"\{.*", " ", bersih, flags=re.DOTALL)
    bersih = bersih.replace("}", " ")
    bersih = re.sub(r"[ \t]+", " ", bersih)
    bersih = re.sub(r"\n\s*\n+", "\n\n", bersih).strip()
    return parsed, bersih


def _susun_ringkasan_kalimat(
    sentimen_agregat: dict[str, list[float]],
    ringkasan_terstruktur: dict,
) -> list[str]:
    """Susun kalimat per peserta dari skor akhir dan klausa syarat berubah."""
    kalimat: list[str] = []
    for nama, tren in sentimen_agregat.items():
        if not tren:
            continue
        skor = tren[-1]
        if skor > 0.2:
            sikap = "mendukung"
        elif skor < -0.2:
            sikap = "menolak"
        else:
            sikap = "netral"

        klausa = str(ringkasan_terstruktur.get(nama) or "").strip()
        klausa = re.sub(
            r"^(bisa|akan)\s+berubah\s+jika\s+",
            "",
            klausa,
            flags=re.IGNORECASE,
        ).strip()
        klausa = re.sub(r"^jika\s+", "", klausa, flags=re.IGNORECASE).strip()
        klausa = klausa.rstrip(".")

        if not klausa:
            kalimat.append(
                f"{nama} bersikap {sikap} (skor akhir {skor:.2f}); "
                "syarat berubah tidak tersedia."
            )
        else:
            kalimat.append(
                f"{nama} bersikap {sikap} (skor akhir {skor:.2f}); "
                f"bisa berubah jika {klausa}."
            )
    return kalimat


def _build_ringkasan_agen(agents: list[dict], sentimen_agregat: dict) -> tuple[dict, dict, list[str]]:
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
            if tren[-1] - tren[0] > 0.2:   arah = "→positif"
            elif tren[0] - tren[-1] > 0.2: arah = "→negatif"
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
    data_transparency: dict | None = None,
) -> tuple[str, dict, dict]:
    """
    Returns:
        (analisis_raw, aktor_analisis, ringkasan_terstruktur)
    """
    nama_valid = list(sentimen_agregat.keys())
    pengaruh_map, volatilitas, ringkasan_agen = _build_ringkasan_agen(agents, sentimen_agregat)

    prompt_analisis = (
        f"Topik: {topik}\n"
        f"Log diskusi:\n{log_diskusi[:1000]}\n\n"
        "Tulis analisis dalam bahasa Indonesia:\n"
        "1. Ringkasan 2 paragraf: dinamika diskusi dan posisi tiap agen.\n"
        "2. Untuk setiap partisipan, balas HANYA JSON object dengan format:\n"
        "   {\"nama_agen\": \"satu klausa syarat berubah (mis. 'bisa berubah jika data menunjukkan peningkatan dampak')\"}\n"
        "   JANGAN menyebut sikap perorangan (positif/negatif/netral) — itu sudah diketahui dari data.\n"
        "   JANGAN menulis PREDIKSI SKENARIO.\n"
        "3. Setelah ringkasan, tambahkan satu paragraf pendek dengan format:\n"
        "   RISIKO UTAMA: [Identifikasi 1-2 risiko terbesar jika topik/kebijakan ini dilanjutkan, berdasarkan argumen agen yang menolak]"
    )
    analisis_raw = call_llm(
        (
            "Kamu analis sosial yang menjelaskan diskusi kepada orang awam. "
            "Tulis analisis dalam bahasa Indonesia yang MUDAH DIPAHAMI, "
            "seperti menjelaskan kepada teman — bukan laporan akademis. "
            "Hindari jargon teknis. Gunakan kalimat singkat. Jangan pakai bullet/tabel."
        ),
        prompt_analisis,
        max_tokens=MAX_TOKENS_ANALYSIS,
        model=MODEL_ANALYSIS,
        use_analysis_chain=True,
    )
    analisis_raw = _strip_emoji(analisis_raw or "")
    if not analisis_raw or analisis_raw.startswith("[Error") or analisis_raw.startswith("[RateLimit"):
        analisis_raw = "(analisis tidak tersedia)"

    # Extract ringkasan_terstruktur dari JSON di keluaran LLM, lalu buang JSON dari teks.
    ringkasan_terstruktur, analisis_raw = _parse_ringkasan_json(analisis_raw)

    # Remove PREDIKSI SKENARIO lines from analisis_raw (LLM might still include it)
    analisis_raw = re.sub(
        r'PREDIKSI SKENARIO:.*?(\n|$)',
        '',
        analisis_raw,
        flags=re.IGNORECASE
    ).strip()
    analisis_raw = re.sub(
        r'\(X\+Y\+Z\s*=\s*100\).*?(\n|$)',
        '',
        analisis_raw,
        flags=re.IGNORECASE
    ).strip()

    if not analisis_raw or analisis_raw.startswith("[Error") or analisis_raw.startswith("[RateLimit"):
        analisis_raw = "(analisis tidak tersedia)"

    prompt_aktor = (
        f"Topik: {topik}\nAgen: {', '.join(nama_valid)}\n"
        + "\n".join(ringkasan_agen) + "\n\n"
        "PERHATIAN untuk kelompok_kritis: field cara_pendekatan HARUS:\n"
        "- Spesifik ke argumen yang mereka kemukakan dalam diskusi\n"
        "- Berisi tindakan konkret yang bisa dilakukan (bukan saran generik)\n"
        "- Maksimal 1-2 kalimat\n"
        "Contoh BURUK: 'Identifikasi kekhawatiran spesifik dan cari titik kompromi'\n"
        "Contoh BAGUS: 'Berikan kompensasi berupa subsidi silang untuk pelaku UMKM yang terdampak, dan jadwalkan dialog triwulan dengan perwakilan mereka'\n\n"
        "Untuk aktor_kunci, isi cara_pendekatan dengan saran konkret dan spesifik ke topik untuk mempengaruhi aktor tersebut.\n\n"
        "Balas HANYA JSON valid:\n"
        '{"aktor_kunci":[{"nama":"...","alasan":"...","dampak_jika_berubah":"...","cara_pendekatan":"..."}],'
        '"swing_voter":[{"nama":"...","alasan_volatil":"...","potensi_arah":"positif|negatif"}],'
        '"aktor_penggerak":"...","rekomendasi":"...",'
        '"rekomendasi_strategis":["Rekomendasi 1 konkret...","Rekomendasi 2 konkret...","Rekomendasi 3 konkret..."],'
        '"kelompok_kritis":[{"nama":"...","alasan":"...","cara_pendekatan":"..."}]}'
    )
    # ponytail: inject briefing note for empty/limited data
    dp = data_transparency or {}
    bs = dp.get("briefing_status", "")
    if bs == "empty":
        prompt_aktor += (
            "\n\nCATATAN: Tidak ada data berita atau survei eksternal untuk topik ini. "
            "Berikan rekomendasi berdasarkan analisis logis terhadap topik dan hasil diskusi agent, "
            "TAPI tetap spesifik ke konteks topik — JANGAN generate saran generik yang bisa berlaku untuk topik apapun. "
            "Jangan mengklaim ada data pendukung yang sebenarnya tidak tersedia."
        )
    elif bs == "limited":
        source = "data survei" if dp.get("polling_reference_matched") else "briefing minim"
        prompt_aktor += (
            f"\n\nCATATAN: Data pendukung untuk topik ini terbatas ({source}). "
            "Pertimbangkan keterbatasan ini dalam rekomendasi."
        )
    raw = call_llm_json(
        "Analis diskusi sosial. Balas HANYA JSON valid.",
        prompt_aktor,
        max_tokens=500,
        model=MODEL_ANALYSIS,
        use_analysis_chain=True,
    )

    aktor_analisis: dict = {}

    if isinstance(raw, dict) and raw:
        for item in raw.get("aktor_kunci", []):
            nama = _resolve_nama(item.get("nama", ""), pengaruh_map, nama_valid)
            item["nama"] = nama
            tren = sentimen_agregat.get(nama, [])
            item.update({
                "pengaruh_skor": pengaruh_map.get(nama, 0.5),
                "sikap_akhir":   tren[-1] if tren else 0.0,
                "sikap_label":   _label_sentimen(tren[-1] if tren else 0.0),
            })
        for item in raw.get("swing_voter", []):
            nama = _resolve_nama(item.get("nama", ""), pengaruh_map, nama_valid)
            item["nama"] = nama
            tren = sentimen_agregat.get(nama, [])
            item.update({
                "volatilitas": volatilitas.get(nama, 0.0),
                "sikap_awal":  tren[0]  if tren else 0.0,
                "sikap_akhir": tren[-1] if tren else 0.0,
            })
        pg = raw.get("aktor_penggerak", "")
        if pg and pg != "-":
            resolved = _resolve_nama(pg, pengaruh_map, nama_valid)
            # ponytail: fallback ke top aktor_kunci kalo LLM hallucinate nama yg gak ada di roster
            if resolved not in pengaruh_map:
                kunci_llm = raw.get("aktor_kunci") or [{}]
                resolved = kunci_llm[0].get("nama", "-") if kunci_llm else "-"
            raw["aktor_penggerak"] = resolved

        aktor_analisis = {
            k: raw[k] for k in ("aktor_kunci", "swing_voter", "aktor_penggerak", "rekomendasi", "rekomendasi_strategis", "kelompok_kritis")
            if k in raw
        }

        # Fix 1: Retry rekomendasi_strategis dengan separate LLM call jika hasil dari JSON utama gagal
        rekom_strat = aktor_analisis.get("rekomendasi_strategis", [])
        if not isinstance(rekom_strat, list) or len(rekom_strat) < 3:
            prompt_rekom = (
                f"Topik: {topik}\n\n"
                "Data agen:\n"
                + "\n".join(ringkasan_agen) + "\n\n"
                "Berdasarkan hasil diskusi di atas, berikan 3 rekomendasi strategis yang KONKRET dan ACTIONABLE.\n\n"
                "Balas HANYA dengan format JSON array berikut, tanpa teks tambahan apapun:\n"
                '["rekomendasi pertama...", "rekomendasi kedua...", "rekomendasi ketiga..."]\n\n'
                "Aturan:\n"
                "- Tiap rekomendasi 1-2 kalimat, langsung ke poin\n"
                "- Rekomendasi 1: kelompok mana yang perlu didekati duluan dan cara konkretnya\n"
                "- Rekomendasi 2: narasi atau framing yang paling efektif berdasarkan argumen pendukung\n"
                "- Rekomendasi 3: cara konkret menetralisir kelompok penolak terkuat\n"
                "- JANGAN tambahkan penjelasan di luar JSON array\n"
                "- JANGAN gunakan markdown atau backtick"
            )
            # ponytail: same briefing note for retry prompt
            if bs == "empty":
                prompt_rekom += (
                    "\n\nCATATAN: Tidak ada data eksternal untuk topik ini. "
                    "Tetap spesifik ke konteks — jangan berpura-pura ada data pendukung."
                )
            elif bs == "limited":
                prompt_rekom += (
                    "\n\nCATATAN: Data eksternal terbatas untuk topik ini. "
                    "Pertimbangkan keterbatasan data dalam rekomendasi."
                )
            raw_rekom_raw = call_llm(
                "Kamu adalah konsultan strategi. Balas HANYA JSON array.",
                prompt_rekom,
                max_tokens=400,
                model=MODEL_ANALYSIS,
                use_analysis_chain=True,
            )
            rekom_strat = _parse_rekomendasi(raw_rekom_raw or "")
            if not rekom_strat:
                rekom_strat = _fallback_rekomendasi(agents, topik, data_transparency)
            aktor_analisis["rekomendasi_strategis"] = rekom_strat

    if not aktor_analisis:
        aktor_analisis = _aktor_fallback(pengaruh_map, volatilitas, sentimen_agregat, data_transparency)

    return analisis_raw, aktor_analisis, ringkasan_terstruktur


def _aktor_fallback(pengaruh_map: dict, volatilitas: dict, sentimen_agregat: dict, data_transparency: dict | None = None) -> dict:
    """
    BUG #5 & BUG #6 FIX: Fallback pure-Python tanpa LLM.
    FIX-6: Aktor kunci = INFLUENCE TINGGI + KONSISTENSI TINGGI (bukan volatilitas tinggi).
    Swing voter = VOLATILITAS TINGGI (agen paling sering berubah).
    Dua hal ini harus BERBEDA — tidak boleh agen yang sama jadi keduanya.
    """
    def _konsistensi(nama: str) -> float:
        scores = sentimen_agregat.get(nama, [])
        if len(scores) < 2:
            return 1.0
        try:
            var = statistics.variance(scores)
            return round(1.0 - min(var, 1.0), 3)
        except Exception:
            return 1.0

    def _cara_pendekatan_fallback(nama: str, pengaruh: float, konsistensi: float, skor: float) -> str:
        """Generate cara_pendekatan berbasis data simulasi, dengan variasi per kategori aktor."""
        sentimen_akhir = sentimen_agregat.get(nama, [0])[-1]
        var = hash(nama) % 3  # deterministic 0..2

        # Kategorisasi aktor via keyword di nama
        nl = nama.lower()
        if any(k in nl for k in ("jurnalis","media","wartawan","pers")):
            kat = "media"
        elif any(k in nl for k in ("pengusaha","pekerja","umkm","ekonomi","startup",
                                   "bisnis","buruh","petani","nelayan","diaspora")):
            kat = "ekonomi"
        elif any(k in nl for k in ("pemerintah","tni","kepala daerah","dokter","nakes")):
            kat = "institusi"
        elif any(k in nl for k in ("aktivis","advokat","pengacara","akademisi","mahasiswa",
                                   "ulama","guru","tokoh","hukum","ham","etikawan","minoritas")):
            kat = "tokoh"
        else:
            kat = "umum"

        if sentimen_akhir < -0.2:
            t = {
                "media": [
                    f"{nama} resisten (sentimen {sentimen_akhir:+.2f}). Ajak diskusi redaksi untuk pahami keberatan mereka.",
                    f"{nama} negatif (sentimen {sentimen_akhir:+.2f}). Beri akses eksklusif ke data verifikasi.",
                    f"{nama} resisten (sentimen {sentimen_akhir:+.2f}). Briefing wartawan khusus dapat menjembatani kesenjangan.",
                ],
                "ekonomi": [
                    f"{nama} resisten (sentimen {sentimen_akhir:+.2f}). Tekankan dampak bisnis dan insentif yang tersedia.",
                    f"{nama} negatif (sentimen {sentimen_akhir:+.2f}). Sajikan studi kasus dan simulasi finansial.",
                    f"{nama} menolak (sentimen {sentimen_akhir:+.2f}). Libatkan asosiasi usaha untuk dialog sektoral.",
                ],
                "institusi": [
                    f"{nama} resisten (sentimen {sentimen_akhir:+.2f}). Koordinasi lintas sektor untuk identifikasi hambatan.",
                    f"{nama} negatif (sentimen {sentimen_akhir:+.2f}). Siapkan policy brief dan data dampak institusional.",
                    f"{nama} menolak (sentimen {sentimen_akhir:+.2f}). Jadwalkan pertemuan bilateral untuk bahas implementasi.",
                ],
                "tokoh": [
                    f"{nama} resisten (sentimen {sentimen_akhir:+.2f}). Libatkan dalam forum diskusi untuk gali keberatan.",
                    f"{nama} negatif (sentimen {sentimen_akhir:+.2f}). Ajak sebagai narasumber netral dengan data pendukung.",
                    f"{nama} menolak (sentimen {sentimen_akhir:+.2f}). Pendekatan personal lewat jaringan kepercayaan diperlukan.",
                ],
                "umum": [
                    f"{nama} resisten (sentimen {sentimen_akhir:+.2f}). Prioritaskan dialog personal untuk gali akar penolakan.",
                    f"{nama} negatif (sentimen {sentimen_akhir:+.2f}). Sosialisasi bertahap dengan data konkret dapat mengubah persepsi.",
                    f"{nama} menolak (sentimen {sentimen_akhir:+.2f}). Informasi terstruktur dan diskusi terbatas bisa membantu.",
                ],
            }
            return t[kat][var]

        if skor > 0.7:
            t = {
                "media": [
                    f"{nama} aktor kunci — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Jadwalkan wawancara eksklusif untuk bangun hubungan strategis.",
                    f"{nama} aktor kunci — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Libatkan sebagai mitra komunikasi utama di media.",
                    f"{nama} prioritas utama — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Undang ke forum diskusi redaksi secara proaktif.",
                ],
                "ekonomi": [
                    f"{nama} aktor kunci — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Libatkan dalam penyusunan kebijakan insentif.",
                    f"{nama} prioritas — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Ajak sebagai mitra uji coba program baru.",
                    f"{nama} pemain kunci — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Jadwalkan forum bisnis untuk selaraskan perspektif.",
                ],
                "institusi": [
                    f"{nama} aktor kunci — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Jadwalkan koordinasi lintas sektor untuk pembahasan kebijakan.",
                    f"{nama} prioritas — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Libatkan dalam perumusan regulasi sejak tahap awal.",
                    f"{nama} mitra strategis — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Siapkan nota dinas dan data pendukung untuk advokasi.",
                ],
                "tokoh": [
                    f"{nama} aktor kunci — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Ajak sebagai mitra diskusi untuk bangun dukungan publik.",
                    f"{nama} prioritas — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Libatkan sebagai narasumber di forum-forum strategis.",
                    f"{nama} tokoh kunci — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Dekati melalui jaringan komunitas untuk endors publik.",
                ],
                "umum": [
                    f"{nama} aktor kunci — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Libatkan sejak awal sebagai mitra komunikasi utama.",
                    f"{nama} prioritas — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Ajak diskusi strategis untuk selaraskan perspektif.",
                    f"{nama} pemain penting — pengaruh {pengaruh:.0%}, konsisten (skor {skor:.2f}). Jadwalkan pertemuan rutin untuk jaga hubungan.",
                ],
            }
            return t[kat][var]

        if konsistensi < 0.5:
            t = {
                "media": [
                    f"{nama} konsistensi rendah ({konsistensi:.0%}) — sikap masih bisa dibentuk. Undang ke forum diskusi redaksi.",
                    f"{nama} belum konsisten ({konsistensi:.0%}) — berpotensi berubah. Beri akses data eksklusif untuk edukasi bertahap.",
                    f"{nama} fluktuatif ({konsistensi:.0%}) — bisa diarahkan. Fasilitasi akses langsung ke pembuat kebijakan.",
                ],
                "ekonomi": [
                    f"{nama} konsistensi rendah ({konsistensi:.0%}) — masih cair. Sajikan proyeksi bisnis jangka panjang yang meyakinkan.",
                    f"{nama} belum konsisten ({konsistensi:.0%}) — pengaruh bisa dimenangkan. Tawarkan insentif dan kemudahan regulasi.",
                    f"{nama} fluktuatif ({konsistensi:.0%}) — perlu pendekatan. Libatkan dalam uji kebijakan sebelum implementasi luas.",
                ],
                "institusi": [
                    f"{nama} konsistensi rendah ({konsistensi:.0%}) — sikap bisa berubah. Siapkan data kinerja dan capaian program.",
                    f"{nama} belum konsisten ({konsistensi:.0%}) — perlu advokasi. Kirim policy brief dan undang ke forum koordinasi.",
                    f"{nama} fluktuatif ({konsistensi:.0%}) — potensi didapatkan. Jadwalkan rapat teknis untuk bahas implementasi.",
                ],
                "tokoh": [
                    f"{nama} konsistensi rendah ({konsistensi:.0%}) — masih bisa diyakinkan. Ajak sebagai panelis diskusi publik.",
                    f"{nama} belum konsisten ({konsistensi:.0%}) — terbuka untuk diajak. Beri platform untuk sampaikan pendapat.",
                    f"{nama} fluktuatif ({konsistensi:.0%}) — potensial didukung. Libatkan dalam kegiatan komunitas dan sosialisasi.",
                ],
                "umum": [
                    f"{nama} konsistensi rendah ({konsistensi:.0%}) — sikap masih bisa dibentuk. Beri informasi terstruktur dan libatkan diskusi.",
                    f"{nama} belum konsisten ({konsistensi:.0%}) — terbuka untuk pendekatan. Sajikan argumen berbasis data relevan.",
                    f"{nama} fluktuatif ({konsistensi:.0%}) — perlu perhatian. Beri info bertahap dengan contoh konkret.",
                ],
            }
            return t[kat][var]

        t = {
            "media": [
                f"Pantau {nama} secara berkala — pengaruh {pengaruh:.0%}, relevansi perlu diuji. Siapkan briefing jika diperlukan.",
                f"{nama} perlu diobservasi (pengaruh {pengaruh:.0%}). Uji sentimen mereka secara periodik untuk deteksi pergeseran opini.",
                f"Monitoring {nama} lanjutan — pengaruh {pengaruh:.0%} belum optimal. Info bertahap bisa uji keterlibatan mereka.",
            ],
            "ekonomi": [
                f"Pantau {nama} secara berkala — pengaruh {pengaruh:.0%}. Siapkan data insentif jika mereka mulai tertarik.",
                f"{nama} perlu diobservasi (pengaruh {pengaruh:.0%}). Kirim berkala laporan dampak ekonomi kebijakan.",
                f"Monitoring {nama} — pengaruh {pengaruh:.0%}. Uji ketertarikan lewat undangan forum bisnis terbatas.",
            ],
            "institusi": [
                f"Pantau {nama} secara berkala — pengaruh {pengaruh:.0%}. Kirimkan laporan capaian program secara periodik.",
                f"{nama} perlu diobservasi (pengaruh {pengaruh:.0%}). Siapkan notula rapat koordinasi untuk informasi terkini.",
                f"Monitoring {nama} — pengaruh {pengaruh:.0%}. Undang ke forum koordinasi rutin untuk jaga engagement.",
            ],
            "tokoh": [
                f"Pantau {nama} secara berkala — pengaruh {pengaruh:.0%}. Ajak diskusi santai untuk jaga hubungan.",
                f"{nama} perlu diobservasi (pengaruh {pengaruh:.0%}). Kirim undangan forum diskusi untuk ukur minat.",
                f"Monitoring {nama} — pengaruh {pengaruh:.0%}. Beri ruang partisipasi di kegiatan publik.",
            ],
            "umum": [
                f"Pantau {nama} secara berkala — pengaruh {pengaruh:.0%}. Relevansinya perlu diuji lebih lanjut.",
                f"{nama} perlu diobservasi (pengaruh {pengaruh:.0%}). Beri informasi bertahap dan ukur respons.",
                f"Monitoring {nama} — pengaruh {pengaruh:.0%}. Siapkan materi engagement jika sentimen berubah.",
            ],
        }
        return t[kat][var]

    # Composite score: pengaruh × (0.7 + 0.3 × konsistensi)
    # FIX-6: Agen dengan pengaruh tinggi DAN konsisten = aktor kunci
    composite_scores = {
        nama: pengaruh * (0.7 + 0.3 * _konsistensi(nama))
        for nama, pengaruh in pengaruh_map.items()
    }

    sp_composite = sorted(composite_scores.items(), key=lambda x: -x[1])
    aktor_kunci_nama = sp_composite[0][0] if sp_composite else None

    # FIX-6: Swing voter = agen dengan volatilitas TERTINGGI, BUKAN aktor kunci
    sv = sorted(
        [(n, v) for n, v in volatilitas.items() if n != aktor_kunci_nama],
        key=lambda x: -x[1]
    )

    # Build rekomendasi_strategis with optional data note
    rekom_strat = [
        f"Prioritas utama: dekati {sp_composite[0][0]} — pengaruh tinggi, bisa jadi penggerak opini. Ajukan diskusi personal untuk menyelaraskan perspektif.",
        f"Framing narasi: Gunakan argumen berbasis data dan manfaat langsung untuk publik — ini yang paling mungkin diterima oleh kelompok pro.",
        f"Antisipasi penolakan: Pantau pergerakan {sv[0][0] if sv else 'aktor paling volatil'} — kelompok ini paling mungkin berubah arah dan memengaruhi yang lain."
    ] if sp_composite else [
        "Belum ada data cukup untuk rekomendasi strategis.",
    ]
    if (data_transparency or {}).get("briefing_status") in ("empty", "limited"):
        rekom_strat.append(
            "Catatan: Rekomendasi ini disusun tanpa data eksternal (berita/survei) yang memadai untuk topik ini — "
            "pertimbangkan riset tambahan sebelum mengambil keputusan."
        )

    return {
        "aktor_kunci": [
            {
                "nama": n,
                "alasan": (
                    f"Pengaruh {pengaruh_map.get(n, 0.5):.0%} × "
                    f"Konsistensi {_konsistensi(n):.0%} = "
                    f"Skor komposit {composite_scores.get(n, 0):.2f}"
                ),
                "dampak_jika_berubah": "Dapat menggeser konsensus",
                "pengaruh_skor": pengaruh_map.get(n, 0.5),
                "konsistensi_skor": _konsistensi(n),
                "composite_score": composite_scores.get(n, 0),
                "sikap_akhir":   sentimen_agregat.get(n, [0])[-1],
                "sikap_label":   _label_sentimen(sentimen_agregat.get(n, [0])[-1]),
                "cara_pendekatan": _cara_pendekatan_fallback(
                    n,
                    pengaruh_map.get(n, 0.5),
                    _konsistensi(n),
                    composite_scores.get(n, 0),
                ),
            }
            for n, _ in sp_composite[:3]
        ],
        "swing_voter": [
            {
                "nama": n,
                "alasan_volatil": f"Volatilitas {v:.2f} — paling sering berubah pendapat",
                "potensi_arah": "positif" if sentimen_agregat.get(n, [0])[-1] > 0 else "negatif",
                "volatilitas": v,
                "sikap_awal":  sentimen_agregat.get(n, [0])[0],
                "sikap_akhir": sentimen_agregat.get(n, [0])[-1],
            }
            for n, v in sv[:3] if v > 0
        ],
        "aktor_penggerak": sp_composite[0][0] if sp_composite else "-",
        "rekomendasi": (
            f"Fokus pada {sp_composite[0][0]} (pengaruh tinggi + konsisten). "
            f"Waspadai {sv[0][0] if sv else '-'} sebagai swing voter."
            if sp_composite else "Fokus pada aktor paling berpengaruh."
        ),
        "rekomendasi_strategis": rekom_strat,
        "kelompok_kritis": [
            {
                "nama": n,
                "alasan": f"Sentimen akhir {_label_sentimen(sentimen_agregat.get(n, [0])[-1])} ({sentimen_agregat.get(n, [0])[-1]:+.2f}) — termasuk penolak paling konsisten.",
                "cara_pendekatan": f"Libatkan {n} dalam forum diskusi terbatas untuk menggali akar kekhawatiran mereka, lalu tawarkan solusi spesifik yang menjawab poin keberatan utama mereka."
            }
            for n, _ in sorted(
                [(n, sentimen_agregat.get(n, [0])[-1]) for n in sentimen_agregat],
                key=lambda x: x[1]
            )[:2]
            if sentimen_agregat.get(n, [0])[-1] < -0.2
        ],
    }


# ---------------------------------------------------------------------------
# Fix 1: Parse & fallback rekomendasi_strategis — robust, multi-format
# ---------------------------------------------------------------------------

def _parse_rekomendasi(raw_text: str) -> list:
    """Parse rekomendasi strategis dari response LLM, dengan multiple fallback."""
    if not raw_text:
        return []

    # Coba 1: langsung parse JSON
    try:
        result = json.loads(raw_text.strip())
        if isinstance(result, list) and len(result) > 0:
            return [str(r) for r in result[:3]]
    except Exception:
        pass

    # Coba 2: extract JSON array dari dalam teks
    try:
        match = re.search(r'\[.*?\]', raw_text, re.DOTALL)
        if match:
            result = json.loads(match.group())
            if isinstance(result, list) and len(result) > 0:
                return [str(r) for r in result[:3]]
    except Exception:
        pass

    # Coba 3: split by newline kalau model balas dengan numbered list
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    cleaned = []
    for line in lines:
        line = re.sub(r'^[\d]+[.)]\s*', '', line)
        if len(line) > 20:
            cleaned.append(line)
    if len(cleaned) >= 1:
        return cleaned[:3]

    return []


def _fallback_rekomendasi(agents: list[dict], topik: str, data_transparency: dict | None = None) -> list:
    """Generate rekomendasi berbasis data agen kalau LLM gagal total."""
    penolak = [a for a in agents if a.get('sentimen', {}).get('label') == 'negatif']
    pendukung = [a for a in agents if a.get('sentimen', {}).get('label') == 'positif']

    nama_penolak = penolak[0]['nama'] if penolak else 'kelompok penolak'
    nama_pendukung = pendukung[0]['nama'] if pendukung else 'kelompok pendukung'

    result = [
        f"Prioritaskan pendekatan ke {nama_penolak} — kelompok ini memiliki penolakan terkuat dan perlu dilibatkan dalam dialog sebelum kebijakan diimplementasikan.",
        f"Gunakan argumen dari {nama_pendukung} sebagai basis narasi publik — framing yang menekankan manfaat konkret lebih efektif dari data statistik.",
        f"Lakukan sosialisasi bertahap dengan melibatkan tokoh lokal yang dipercaya komunitas penolak untuk mengurangi resistensi."
    ]
    dp = data_transparency or {}
    if dp.get("briefing_status") in ("empty", "limited"):
        result.append(
            "Catatan: Rekomendasi ini disusun tanpa data eksternal (berita/survei) yang memadai untuk topik ini — "
            "pertimbangkan riset tambahan sebelum mengambil keputusan."
        )
    return result


def _build_simulation_quality(
    n_agents: int,
    jumlah_ronde: int,
    estimated_llm_calls: int,
    tier: str = "free",
) -> dict:
    score       = 1.0
    limitations = []
    kelebihan   = []

    sentiment_mode_efektif = "inline" if tier == "free" else SENTIMENT_MODE
    graph_llm_enabled      = tier != "free" and not DISABLE_GRAPH_LLM
    analysis_llm_enabled   = tier != "free" and not DISABLE_FINAL_ANALYSIS_LLM

    if sentiment_mode_efektif == "ml":
        kelebihan.append(
            "Sentimen pakai ML classifier — 0 LLM call, gratis, deterministik, "
            "tidak kena rate limit."
        )
        score += 0.05
    elif sentiment_mode_efektif == "llm":
        kelebihan.append("Sentimen pakai LLM — paling akurat untuk kalimat kompleks.")

    if n_agents >= 7:
        kelebihan.append(f"{n_agents} agen — keragaman perspektif cukup luas.")
    elif n_agents >= 5:
        kelebihan.append(f"{n_agents} agen — variasi sudut pandang cukup.")

    if jumlah_ronde >= 5:
        kelebihan.append(f"{jumlah_ronde} ronde — dinamika opini bisa diamati dalam durasi panjang.")
    elif jumlah_ronde >= 3:
        kelebihan.append(f"{jumlah_ronde} ronde — cukup untuk melihat perubahan opini.")

    if sentiment_mode_efektif == "inline":
        score -= 0.18
        limitations.append(
            "Sentimen pakai mode inline (kata kunci) — kurang akurat untuk "
            "kalimat kompleks, negasi ganda, atau ironi."
        )

    if not graph_llm_enabled:
        score -= 0.12
        limitations.append(
            "GraphRAG dinonaktifkan — peta entitas dan hubungan antar aktor "
            "tidak diekstrak. Fitur ini opsional, tidak memengaruhi jalannya simulasi."
        )

    if not analysis_llm_enabled:
        score -= 0.16
        limitations.append(
            "Analisis akhir pakai aturan otomatis (rule-based), bukan narasi "
            "LLM. Ringkasan lebih pendek tapi tetap informatif."
        )

    if n_agents < 5:
        score -= 0.12
        limitations.append(
            f"Hanya {n_agents} agen — variasi sudut pandang terbatas, "
            f"hasil mungkin kurang mewakili dinamika opini publik."
        )

    if jumlah_ronde < 3:
        score -= 0.12
        limitations.append(
            f"Hanya {jumlah_ronde} ronde — perubahan opini sulit diamati "
            f"dalam durasi pendek."
        )

    score = max(0.0, min(1.0, round(score, 2)))

    if score >= 0.80:
        tier_label  = "high"
        label       = "Simulasi Kaya"
        ringkasan   = "Simulasi berjalan dengan konfigurasi yang baik."
    elif score >= 0.60:
        tier_label  = "medium"
        label       = "Simulasi Standar"
        ringkasan   = "Simulasi berjalan cukup, ada beberapa fitur yang tidak aktif."
    elif score >= 0.40:
        tier_label  = "low"
        label       = "Simulasi Ringan"
        ringkasan   = "Simulasi berjalan dalam mode hemat. Hasil layak dibaca sebagai eksplorasi awal."
    else:
        tier_label  = "minimal"
        label       = "Simulasi Cepat"
        ringkasan   = "Simulasi minimalis — cocok untuk uji coba cepat."

    return {
        "score":             score,
        "score_persen":      round(score * 100),
        "tier":              tier_label,
        "label":             label,
        "ringkasan":         ringkasan,
        "estimated_llm_calls": estimated_llm_calls,
        "kelebihan":         kelebihan,
        "keterbatasan":      limitations,
        "interpretation":    (
            "Hasil ini layak dibaca sebagai simulasi eksploratif — "
            "untuk melihat kemungkinan dinamika opini, bukan prediksi faktual."
        ),
    }


def _analisis_fallback_text(topik: str, sentimen_agregat: dict) -> str:
    final_scores = {
        nama: (tren[-1] if tren else 0.0)
        for nama, tren in sentimen_agregat.items()
    }
    if not final_scores:
        return (
            f"Simulasi untuk topik '{topik}' belum menghasilkan cukup data. "
            "PREDIKSI SKENARIO: Konsensus 33%, Polarisasi 34%, Status Quo 33%"
        )

    pos = sum(1 for s in final_scores.values() if s > 0.2)
    neg = sum(1 for s in final_scores.values() if s < -0.2)
    net = len(final_scores) - pos - neg
    total = max(len(final_scores), 1)

    if pos / total >= 0.6:
        prediksi = (60, 20, 20)
        dinamika = "mayoritas agen cenderung mendukung"
    elif neg / total >= 0.5 or (pos > 0 and neg > 0):
        prediksi = (20, 60, 20)
        dinamika = "diskusi menunjukkan perbedaan posisi yang cukup kuat"
    else:
        prediksi = (25, 25, 50)
        dinamika = "mayoritas posisi masih tertahan di area netral atau belum berubah tajam"

    ringkas_agen = []
    for nama, skor in final_scores.items():
        if skor > 0.2:
            label = "mendukung"
        elif skor < -0.2:
            label = "menolak"
        else:
            label = "netral"
        ringkas_agen.append(f"{nama} cenderung {label} ({skor:+.2f})")

    return (
        f"Mode hemat aktif, jadi analisis ini dibuat dari skor simulasi tanpa LLM tambahan. "
        f"Untuk topik '{topik}', {dinamika}. "
        f"Ringkasan posisi akhir: {', '.join(ringkas_agen)}.\n"
        f"PREDIKSI SKENARIO: Konsensus {prediksi[0]}%, Polarisasi {prediksi[1]}%, Status Quo {prediksi[2]}%"
    )


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
