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
#   - _resolve_nama()         — resolve nama agen dari string bebas ke kanonik
#   - _label_sentimen()       — konversi skor float ke label positif/negatif/netral

import re
import time
import random

from .llm      import (
    call_llm, call_llm_json,
    MODEL_AGENT, MODEL_ANALYSIS,
    MAX_TOKENS_AGENT, MAX_TOKENS_ANALYSIS,
    AGENT_CALL_DELAY, ROUND_DELAY,
    SENTIMENT_MODE,
    _strip_emoji,
)
from .memory   import (
    update_agent_memory, build_memory_context, build_influence_context,
    _compute_gaya_str,
)
from .sentiment import score_sentiment, filter_forbidden_opens
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

    def _batasi_kalimat(teks: str, max_kalimat: int = 3) -> str:
        """
        Post-processing pure Python — potong output agen di batas kalimat ke-N.
        Tidak merusak teks, tidak menambah LLM call.
        """
        if not teks:
            return teks
        # Split di titik, tanda tanya, atau tanda seru diikuti spasi/akhir string
        pecahan = re.split(r'(?<=[.!?])\s+', teks.strip())
        # Buang fragmen kosong
        pecahan = [k for k in pecahan if k.strip()]
        if len(pecahan) <= max_kalimat:
            return teks
        hasil = " ".join(pecahan[:max_kalimat])
        # Pastikan diakhiri tanda baca
        if hasil and hasil[-1] not in ".!?":
            hasil += "."
        return hasil

    def _proses_satu_agen(
        agen: dict,
        ronde_ke: int,
        topik_ronde: str,
        pendapat_dalam_ronde_ini: list[dict],
        idx_agen: int = 0,
    ) -> dict:
        konteks_memori = build_memory_context(agen)

        # Gabungkan pendapat ronde sebelumnya + yang sudah bicara di ronde ini
        # → agen ke-3 bisa merespons agen ke-1 dan ke-2 yang baru ngomong
        konteks_sumber = pendapat_ronde_sebelumnya + pendapat_dalam_ronde_ini
        konteks_pengaruh = build_influence_context(agen, konteks_sumber, idx_agen=idx_agen)

        gaya_str     = _compute_gaya_str(agen)
        role_singkat = agen.get("_role_singkat") or agen["role"][:250].rstrip()

        ada_yang_sudah_bicara = bool(pendapat_dalam_ronde_ini or pendapat_ronde_sebelumnya)

        # ISSUE #23 — stance rule khusus Pemerintah (diperkuat Sesi 14)
        stance_rule = ""
        if "pemerintah" in agen["nama"].lower() or "pejabat pemerintah" in agen.get("role", "").lower():
            stance_rule = (
                "Khusus posisimu: kamu mewakili pemerintah dalam topik ini — kamu berbicara UNTUK pemerintah, bukan tentang pemerintah dari luar. "
                "JANGAN menyerang, mengkritik, atau menyerukan pemerintah untuk berubah. "
                "Jika dikritik: akui tantangan sebagai sesuatu yang sudah diketahui dan sedang ditangani. "
                "Selalu akhiri dengan langkah konkret yang sudah atau akan dilakukan pemerintah. "
                "Kata-kata seperti 'pemerintah harus' atau 'pemerintah perlu' DILARANG — kamu IS pemerintah. "
            )

        # ISSUE #24 — escape phrase rule khusus Akademisi
        akademisi_rule = ""
        if "akademisi" in agen["nama"].lower() or "dosen" in agen.get("role", "").lower():
            akademisi_rule = (
                "JANGAN tutup argumen dengan frasa terbuka seperti 'perlu dipertimbangkan', "
                "'perlu diteliti lebih lanjut', 'sebelum menarik kesimpulan', atau 'perlu dilihat lebih komprehensif'. "
                "Kamu SUDAH mempertimbangkan — sekarang berikan kesimpulanmu yang tegas. "
            )

        # Sesi 15 — ISSUE #25: conviction_rule — cegah Akademisi jadi fence-sitter
        conviction_rule = ""
        if "akademisi" in agen["nama"].lower() or "dosen" in agen.get("role", "").lower():
            conviction_rule = (
                "ATURAN POSISI AKADEMISI: Kamu HARUS memiliki posisi yang JELAS — bukan netral tanpa alasan. "
                "Netral (skor 0) hanya valid jika: "
                "(1) bukti truly seimbang DAN (2) kamu JELASKAN di respons: 'Bukti seimbang antara X dan Y.' "
                "Jika ronde sebelumnya posisimu bukan netral, JANGAN jadi netral sekarang "
                "kecuali ada DATA BARU yang fundamental mengubah kesimpulan. "
                "CONTOH VALID netral: 'Bukti seimbang: 40% mahasiswa malas, 60% tetap rajin. Perlu data lebih untuk simpulan.' "
                "CONTOH INVALID: Hanya bilang 'Ada dua sisi, so netral.' — itu bukan argumen. "
            )

        system_p = (
            f"Kamu {agen['nama']}. {role_singkat} "
            f"GAYA BICARA WAJIB: {gaya_str}. Ikuti gaya ini secara konsisten — "
            "kalau santai pakai bahasa sehari-hari, kalau formal pakai bahasa resmi, "
            "kalau suka debat tunjukkan dengan nada kritis dan tajam. "
            # BUG #24 — position anchor diperkuat
            "Pertahankan posisimu dari ronde sebelumnya kecuali ada argumen baru yang benar-benar kuat dan data baru yang mengubah pandangan. "
            "Berubah posisi tanpa alasan konkret adalah kelemahan — bukan fleksibilitas. "
            + stance_rule
            + akademisi_rule
            + conviction_rule +  # Sesi 15 — ISSUE #25
            "LARANGAN KERAS: "
            "JANGAN menyebut role atau jabatanmu di dalam kalimat (jangan tulis 'sebagai X', 'saya selaku X', 'saya sebagai X'). "
            "JANGAN bilang kamu tidak punya opini — SEMUA karakter punya sudut pandang kuat. "
            "JANGAN ulangi argumen agen lain — berikan sudut pandang UNIK dari perspektifmu. "
            "JANGAN buka kalimat dengan frasa pendapat seperti 'Saya pikir', 'Saya rasa', "
            "'Gue rasa', 'Gue pikir', 'Menurut saya', 'Menurut gue' — langsung ke poin atau fakta. "
            # Sesi 15 — BUG #26: Larangan diperketat — frasa lebih lengkap + instruksi ulang eksplisit
            "LARANGAN ABSOLUT — Frasa berikut TIDAK BOLEH digunakan sebagai pembuka kalimat pertama: "
            "'Gue tidak bisa menerima', 'Saya tidak bisa menerima', "
            "'Gue tidak setuju dengan klaim', 'Saya tidak setuju dengan klaim', "
            "'Klaim bahwa', 'Tidak sepenuhnya akurat', 'Itu tidak tepat', "
            "'Itu tidak akurat', 'Itu tidak benar', "
            "'Saya tidak cocok dengan', 'Saya kurang setuju'. "
            "JIKA KALIMAT PERTAMAMU MENGGUNAKAN SALAH SATU FRASA INI: ULANGI dan mulai ulang. "
            "SELALU mulai dengan ARGUMEN atau DATA LANGSUNG, bukan NEGASI. "
            "CONTOH BENAR: 'Data menunjukkan 75% mahasiswa masih membaca, jadi AI tidak membuat mereka malas.' "
            "CONTOH SALAH: 'Saya tidak bisa menerima klaim itu. Data menunjukkan 75% mahasiswa masih membaca.' "
            "Lihat bedanya? Jangan mulai dengan negasi. Mulai dengan statement positif atau data. "
            "JANGAN kutip atau ulangi kata-kata peserta lain secara verbatim — parafrase atau langsung respons. "
            "Tulis TEPAT 2-3 kalimat pendek. Setiap kalimat HARUS diakhiri tanda titik. "
            "PELANGGARAN: Menulis lebih dari 3 kalimat adalah kesalahan fatal — potong sebelum mengirim."
        )

        # ISSUE #22 — guard agen pembuka ronde 1
        adalah_pembuka = (
            ronde_ke == 1
            and not pendapat_dalam_ronde_ini
            and not pendapat_ronde_sebelumnya
        )

        # Sesi 15 — BUG #27: Hitung skor ronde lalu untuk change justification
        skor_ronde_lalu = None
        if len(agen.get("memori", [])) > 0:
            last_mem = agen["memori"][-1]
            skor_ronde_lalu = last_mem.get("skor", None)

        parts = []
        if konteks_memori:
            parts.append(konteks_memori)

        # Sesi 15 — BUG #27: change_rule — wajib jelaskan jika posisi berubah signifikan
        if skor_ronde_lalu is not None and len(agen.get("memori", [])) >= 2:
            parts.append(
                "PENTING: Posisimu sudah tercatat dari ronde-ronde sebelumnya. "
                "Jika responsmu kali ini BERBEDA dari yang terakhir kamu bilang, "
                "JELASKAN di kalimat pertama atau kedua: argumen atau data baru APA yang membuatmu berubah. "
                "Contoh: 'Ronde lalu saya khawatir tentang X, tapi sekarang saya lihat bukti baru Y — so saya revisi posisi.' "
                "Jangan geser posisi diam-diam tanpa alasan."
            )

        if ada_yang_sudah_bicara and konteks_pengaruh:
            parts.append(konteks_pengaruh)
            # BUG #21 — instruksi respons lebih fleksibel, tidak paksa sebut nama
            parts.append(
                "Respons ke salah satu peserta — boleh sebut namanya, boleh juga langsung counter argumennya "
                "tanpa sebut nama. Yang penting posisimu jelas dan berbeda dari yang sudah bicara."
            )
        elif adalah_pembuka:
            if briefing_real:
                parts.append(f"Info konteks: {briefing_real[:200]}")
            parts.append("Buka diskusi dengan posisimu yang paling kuat tentang topik ini.")
        elif ronde_ke == 1 and briefing_real:
            parts.append(f"Info: {briefing_real[:200]}")

        parts.append(f"Topik diskusi: {topik_ronde[:130]}\nPendapatmu (2-3 kalimat)?")
        user_p = "\n".join(parts)

        # Pangkas jika > 700 char — tapi pertahankan konteks pengaruh (jangan dipotong kasar)
        if len(user_p) > 700:
            parts_trimmed = []
            if konteks_memori:
                parts_trimmed.append(konteks_memori[:80])
            if ada_yang_sudah_bicara and konteks_pengaruh:
                # Potong konteks pengaruh tapi tetap utuh per baris
                baris_pengaruh = konteks_pengaruh.split("\n")
                parts_trimmed.append("\n".join(baris_pengaruh[:4]))  # max 4 baris
                parts_trimmed.append(
                    "Respons ke salah satu peserta — boleh sebut namanya, "
                    "boleh juga langsung counter argumennya tanpa sebut nama."
                )
            parts_trimmed.append(f"Topik diskusi: {topik_ronde[:130]}\nPendapatmu (2-3 kalimat)?")
            user_p = "\n".join(parts_trimmed)

        jawaban  = call_llm(system_p, user_p, max_tokens=MAX_TOKENS_AGENT, model=MODEL_AGENT)
        # Sesi 15 — BUG #26: filter forbidden opening patterns sebelum dipakai
        jawaban  = filter_forbidden_opens(jawaban)
        # BUG #23 — post-processing: pastikan output maksimal 3 kalimat
        jawaban  = _batasi_kalimat(jawaban, max_kalimat=3)
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
        # Pendapat yang sudah terkumpul di ronde ini (diupdate setiap agen selesai bicara)
        pendapat_dalam_ronde_ini: list[dict] = []

        # Shuffle urutan agen mulai ronde 2 agar percakapan lebih organik
        urutan_agen = list(agents)
        if ronde_ke > 1:
            random.Random(ronde_ke).shuffle(urutan_agen)

        # ── SEQUENTIAL — satu agen per call, bukan paralel ───────────────
        for idx, agen in enumerate(urutan_agen):
            try:
                res = _proses_satu_agen(agen, ronde_ke, topik_ronde, pendapat_dalam_ronde_ini, idx_agen=idx)
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
            entry = {
                "nama": res["nama"], "pendapat": res["pendapat"],
                "sentimen": res["sentimen"], "pengaruh": res["pengaruh"],
            }
            pendapat_ronde_ini.append(entry)
            # Update in-round context → agen berikutnya bisa merespons agen ini
            pendapat_dalam_ronde_ini.append(entry)

            # Jeda antar agen (kecuali terakhir di ronde terakhir)
            bukan_akhir = not (idx == len(urutan_agen) - 1 and ronde_ke == jumlah_ronde)
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
    analisis_raw = _strip_emoji(analisis_raw)
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
            "sentiment_mode": SENTIMENT_MODE,
        },
    }


# ---------------------------------------------------------------------------
# Analisis Gabungan — 1 call LLM-JSON (FIX #3)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Helper module-level private — dipakai oleh _analisis_dan_aktor()
# dan analyze_key_actors() agar tidak ada duplikasi definisi.
# ---------------------------------------------------------------------------

def _resolve_nama(s: str, pengaruh_map: dict, nama_valid: list) -> str:
    """Resolve nama agen dari string bebas ke nama kanonik di nama_valid."""
    s = s.strip()
    if s in pengaruh_map:
        return s
    for v in nama_valid:
        if v.lower() == s.lower() or s.lower() in v.lower():
            return v
    return s


def _label_sentimen(skor: float) -> str:
    """Konversi skor sentimen float ke label teks."""
    if skor > 0.2:  return "positif"
    if skor < -0.2: return "negatif"
    return "netral"


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
) -> tuple[str, dict]:
    """
    Hasilkan analisis akhir + aktor kunci.

    DIPISAH menjadi 2 call sederhana agar LLM tidak gagal parse JSON
    akibat prompt terlalu panjang (penyebab utama "analisis tidak tersedia").

    Call 1 — plain text analisis (lebih stabil, tidak ada risiko JSON corrupt)
    Call 2 — JSON aktor kunci (prompt ringkas)

    Return: (analisis_raw: str, aktor_analisis: dict)
    """
    nama_valid = list(sentimen_agregat.keys())
    pengaruh_map, volatilitas, ringkasan_agen = _build_ringkasan_agen(agents, sentimen_agregat)

    # ── CALL 1: Analisis naratif (plain text — jauh lebih stabil) ───────
    prompt_analisis = (
        f"Topik: {topik}\n"
        f"Log diskusi:\n{log_diskusi[:1000]}\n\n"
        "Tulis analisis dalam bahasa Indonesia:\n"
        "1. Ringkasan 2 paragraf: dinamika diskusi dan posisi tiap agen.\n"
        "2. Untuk setiap partisipan, tulis satu kalimat yang menyebutkan nama, "
        "sikap akhir (positif/negatif/netral), prediksi ke depan, dan kemungkinan berubah.\n"
        "3. Baris terakhir harus persis:\n"
        "   PREDIKSI SKENARIO: Konsensus X%, Polarisasi Y%, Status Quo Z%\n"
        "   (X+Y+Z = 100)"
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
    )
    analisis_raw = _strip_emoji(analisis_raw or "")
    if not analisis_raw or analisis_raw.startswith("[Error") or analisis_raw.startswith("[RateLimit"):
        analisis_raw = "(analisis tidak tersedia)"

    # ── CALL 2: JSON aktor kunci (prompt ringkas) ────────────────────────
    prompt_aktor = (
        f"Topik: {topik}\nAgen: {', '.join(nama_valid)}\n"
        + "\n".join(ringkasan_agen) + "\n\n"
        "Balas HANYA JSON valid:\n"
        '{"aktor_kunci":[{"nama":"...","alasan":"...","dampak_jika_berubah":"..."}],'
        '"swing_voter":[{"nama":"...","alasan_volatil":"...","potensi_arah":"positif|negatif"}],'
        '"aktor_penggerak":"...","rekomendasi":"..."}'
    )
    raw = call_llm_json(
        "Analis diskusi sosial. Balas HANYA JSON valid.",
        prompt_aktor,
        max_tokens=500,
        model=MODEL_ANALYSIS,
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
            raw["aktor_penggerak"] = _resolve_nama(pg, pengaruh_map, nama_valid)

        aktor_analisis = {
            k: raw[k] for k in ("aktor_kunci", "swing_voter", "aktor_penggerak", "rekomendasi")
            if k in raw
        }

    if not aktor_analisis:
        aktor_analisis = _aktor_fallback(pengaruh_map, volatilitas, sentimen_agregat)

    return analisis_raw, aktor_analisis


def _aktor_fallback(pengaruh_map: dict, volatilitas: dict, sentimen_agregat: dict) -> dict:
    """Fallback pure-Python tanpa LLM jika call JSON gagal."""
    sp = sorted(pengaruh_map.items(), key=lambda x: -x[1])
    sv = sorted(volatilitas.items(),  key=lambda x: -x[1])
    return {
        "aktor_kunci": [
            {"nama": n, "alasan": "Pengaruh tertinggi",
             "dampak_jika_berubah": "Dapat menggeser konsensus",
             "pengaruh_skor": s,
             "sikap_akhir":   sentimen_agregat.get(n, [0])[-1],
             "sikap_label":   _label_sentimen(sentimen_agregat.get(n, [0])[-1])}
            for n, s in sp[:3]
        ],
        "swing_voter": [
            {"nama": n, "alasan_volatil": "Sering berubah pendapat",
             "potensi_arah": "positif" if sentimen_agregat.get(n,[0])[-1] > 0 else "negatif",
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
    """
    Analisis aktor kunci untuk endpoint /extract-graph.

    Refactored: menggunakan _build_ringkasan_agen() dan _aktor_fallback()
    yang sudah ada — menghilangkan duplikasi logika dengan _analisis_dan_aktor().
    Tetap melakukan 1 LLM call untuk JSON aktor (sama seperti sebelumnya).
    Output schema tidak berubah.
    """
    pengaruh_map, volatilitas, ringkasan_agen = _build_ringkasan_agen(agents, sentimen_agregat)
    nama_valid = list(sentimen_agregat.keys())

    prompt = (
        f"Topik: {topik}\nAgen: {', '.join(nama_valid)}\n"
        + "\n".join(ringkasan_agen) + "\n\n"
        "Balas HANYA JSON valid:\n"
        '{"aktor_kunci":[{"nama":"...","alasan":"...","dampak_jika_berubah":"..."}],'
        '"swing_voter":[{"nama":"...","alasan_volatil":"...","potensi_arah":"positif|negatif"}],'
        '"aktor_penggerak":"...","rekomendasi":"..."}'
    )
    hasil = call_llm_json(
        "Analis diskusi sosial. Balas HANYA JSON valid.",
        prompt, max_tokens=500, model=MODEL_ANALYSIS
    )

    if isinstance(hasil, dict) and hasil:
        for item in hasil.get("aktor_kunci", []):
            nama = _resolve_nama(item.get("nama", ""), pengaruh_map, nama_valid)
            item["nama"] = nama
            tren = sentimen_agregat.get(nama, [])
            item.update({
                "pengaruh_skor": pengaruh_map.get(nama, 0.5),
                "sikap_akhir":   tren[-1] if tren else 0.0,
                "sikap_label":   _label_sentimen(tren[-1] if tren else 0.0),
            })
        for item in hasil.get("swing_voter", []):
            nama = _resolve_nama(item.get("nama", ""), pengaruh_map, nama_valid)
            item["nama"] = nama
            tren = sentimen_agregat.get(nama, [])
            item.update({
                "volatilitas": volatilitas.get(nama, 0.0),
                "sikap_awal":  tren[0]  if tren else 0.0,
                "sikap_akhir": tren[-1] if tren else 0.0,
            })
        pg = hasil.get("aktor_penggerak", "")
        if pg and pg != "-":
            hasil["aktor_penggerak"] = _resolve_nama(pg, pengaruh_map, nama_valid)
        return hasil

    # Fallback tanpa LLM — gunakan helper yang sudah ada
    return _aktor_fallback(pengaruh_map, volatilitas, sentimen_agregat)


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