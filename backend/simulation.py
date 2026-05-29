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
    update_agent_memory, build_memory_context, build_influence_context,
    _compute_gaya_str,
)
from .sentiment import score_sentiment, filter_forbidden_opens
from .graph     import extract_entities
from .core.models import (
    SimulationEvent, simulation_result_to_state,
    AgentProfile, AgentAction, agent_dict_to_profile, agent_profile_to_dict,
)
from .core.event_system import (
    compute_event_impact,
    build_event_narrative,
    get_agent_impact_note,
    generate_event_explanation,
)
from .core.scheduler import (
    get_speaking_order,
    select_response_target,
    get_strategy_display,
)
from .core.prediction import heuristic_predict, compute_confidence
from .core.swarm import CrowdPool



# ---------------------------------------------------------------------------
# Helper: Batasi Output Agen (BUG-20)
# ---------------------------------------------------------------------------

def _batasi_kalimat(teks: str, max_kalimat: int = 3) -> str:
    """
    Post-processing pure Python — potong output agen di batas kalimat ke-N.
    BUG-20 FIX: hard cap 45 kata, threshold 30 kata + split di titik koma.
    """
    if not teks:
        return teks
    pecahan = re.split(r'(?<=[.!?;])\s+', teks.strip())
    pecahan = [k for k in pecahan if k.strip()]
    
    # Hard cap total kata
    kata_total = teks.split()
    if len(kata_total) > 45:
        return " ".join(kata_total[:45]).rstrip(' ,;.-_:') + "."

    if len(pecahan) <= max_kalimat:
        kata_kata = teks.split()
        if len(kata_kata) > 30:
            potongan = " ".join(kata_kata[:25])
            for pemisah in [". ", "; ", ", namun ", ", padahal ", ", sehingga ",
                            ", tetapi ", ", tapi ", "Kami juga ", "Selain itu ", "Dengan demikian "]:
                idx = potongan.rfind(pemisah)
                if idx > 10:
                    return potongan[:idx + 1].rstrip(' ,;.-_:') + "."
            return " ".join(kata_kata[:20]).rstrip(' ,;.-_:') + "."
        return teks
    hasil = " ".join(pecahan[:max_kalimat])
    if hasil and hasil[-1] not in ".!?":
        hasil += "."
    return hasil


# ---------------------------------------------------------------------------
# Simulation Core — Sequential + Jeda (solusi utama rate limit)
# ---------------------------------------------------------------------------

def run_simulation(
    topik: str,
    agents: list[dict],
    jumlah_ronde: int = 3,
    intervensi: str | None = None,
    briefing_real: str = "",
    tier: str = "free",
    scheduler_strategy: str = "influence_aware",
    n_crowd: int = 0,
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
    events: list[SimulationEvent] = []
    n_agents = len(agents)
    sentiment_mode = SENTIMENT_MODE if tier != "free" else "inline"
    llm_for_sentiment = int(sentiment_mode not in ("inline", "ml"))
    estimated_llm_calls = (
        n_agents * jumlah_ronde
        + (llm_for_sentiment * n_agents * jumlah_ronde)
        + (0 if tier == "free" else 1)
        + (0 if tier == "free" else 2)
    )

    # ── Phase 8: Inisialisasi CrowdPool ──
    crowd_pool: CrowdPool | None = None
    if n_crowd > 0:
        crowd_pool = CrowdPool(seed=hash(topik) % (2**31))
        crowd_pool.generate(n=n_crowd)

    # ── Phase 2: Normalisasi agents ke AgentProfile ──
    agent_profiles: list[AgentProfile] = []
    agent_dicts: list[dict] = []
    for a in agents:
        if isinstance(a, AgentProfile):
            profile = a
            d = agent_profile_to_dict(profile)
        else:
            profile = agent_dict_to_profile(a)
            d = dict(a)
        d.setdefault("_role_singkat", d["role"][:250].rstrip())
        _compute_gaya_str(d)
        agent_profiles.append(profile)
        agent_dicts.append(d)
    agents = agent_dicts  # kode lama tetap pakai dict

    # Phase 2: track actions via AgentAction
    agent_actions: list[AgentAction] = []

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

        # BUG-12 FIX: voice_anchor per persona — cegah template "Data menunjukkan bahwa" mendominasi semua agen
        voice_anchor = ""
        nama_lower = agen["nama"].lower()
        if "mahasiswa" in nama_lower:
            voice_anchor = (
                "GAYA BICARA WAJIB MAHASISWA: Langsung, emosional, pakai bahasa gaul 'gue/lu/bro'. "
                "CONTOH PEMBUKA YANG BENAR: '75% temen gue bilang...', 'Fakta di lapangan: TNI masih...', 'Ini nggak masuk akal bro...'. "
                "DILARANG KERAS membuka dengan: 'Data menunjukkan bahwa', 'Berdasarkan data', 'Studi menunjukkan', 'Penelitian menunjukkan'. "
            )
        elif "pengusaha" in nama_lower or "umkm" in nama_lower:
            voice_anchor = (
                "GAYA BICARA WAJIB PENGUSAHA: Pragmatis, langsung ke angka dan dampak bisnis. "
                "CONTOH PEMBUKA YANG BENAR: 'Dari sisi bisnis, ini artinya...', 'Anggaran militer Rp X triliun itu...', 'Dampak terhadap UMKM: penjualan turun 20%'. "
                "DILARANG KERAS membuka dengan: 'Data menunjukkan bahwa', 'Berdasarkan data'. "
            )
        elif "pekerja" in nama_lower or "kantoran" in nama_lower:
            voice_anchor = (
                "GAYA BICARA WAJIB PEKERJA: Singkat, pragmatis, langsung dampak nyata. "
                "CONTOH PEMBUKA: 'Dari pengalaman kerja, ini berarti...', 'Efek langsungnya ke gaji dan jam kerja...'. "
                "DILARANG KERAS: 'Data menunjukkan bahwa', 'Berdasarkan data'. "
            )
        elif "pemerintah" in nama_lower or "pejabat" in nama_lower:
            voice_anchor = (
                "GAYA BICARA WAJIB PEMERINTAH: Formal, diplomatis, padat. "
                "CONTOH PEMBUKA: 'Kami telah mengambil langkah...', 'Dari perspektif kebijakan, solusinya adalah...'. "
                "JANGAN: 'Data menunjukkan bahwa', 'Berdasarkan data' — terlalu akademis untuk pemerintah. "
                "VARIASI: Jangan ulangi pola kalimat yang sama setiap ronde. Variasikan argumen: kadang bicara kebijakan, "
                "kadang bicara data dampak, kadang respons terhadap kritik dengan data konkret. "
            )
        elif "akademisi" in nama_lower or "dosen" in nama_lower or "peneliti" in nama_lower:
            voice_anchor = (
                "GAYA BICARA WAJIB AKADEMISI: Berbasis riset dan statistik, tapi SINGKAT. "
                "CONTOH PEMBUKA: 'Studi 2024 menunjukkan...', 'Dari data survei: 65% responden...', 'Meta-analisis dari 12 penelitian menunjukkan...'. "
                "HINDARI: 'Data menunjukkan bahwa' (terlalu umum), gunakan spesifik: 'Studi X dari universitas Y menunjukkan...'. "
                "VARIASI: JANGAN pakai studi/statistik yang SAMA di setiap ronde. Jika sudah pakai 'Studi 2024' di ronde sebelumnya, "
                "ronde ini pakai sumber atau tahun yang BERBEDA. Boleh juga pakai data dari sumber berita, observasi lapangan, atau laporan pemerintah. "
            )
        elif "media" in nama_lower or "jurnalis" in nama_lower:
            voice_anchor = (
                "GAYA BICARA WAJIB JURNALIS: Investigatif, kritis, kesimpulannya tegas bukan 'ada dua sisi'. "
                "CONTOH PEMBUKA: 'Temuan investigasi kami menemukan...', 'Testimoni dari lapangan: ...', 'Dokumen menunjukkan...'. "
                "DILARANG: 'Data menunjukkan bahwa' (terlalu netral untuk jurnalis investigatif). "
            )
        elif "masyarakat" in nama_lower or "umum" in nama_lower or "warga" in nama_lower:
            voice_anchor = (
                "GAYA BICARA WAJIB MASYARAKAT UMUM: Sederhana, berdasarkan pengalaman hidup. "
                "CONTOH PEMBUKA: 'Dari cerita teman saya...', 'Yang saya lihat di lingkungan: ...', 'Untuk rakyat kecil, artinya...'. "
                "JANGAN: 'Data menunjukkan bahwa', 'Berdasarkan data' — itu bukan cara orang biasa ngomong. "
            )

        # ERROR-1 FIX: hitung skor_ronde_lalu DI SINI — sebelum conviction_rule & stance_rule
        # yang keduanya bergantung pada nilai ini. Sebelumnya dihitung di baris 241 (terlambat).
        skor_ronde_lalu = None
        if len(agen.get("memori", [])) > 0:
            last_mem = agen["memori"][-1]
            skor_ronde_lalu = last_mem.get("skor", None)

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
        # BUG-08 FIX: stance lock khusus Pemerintah harus masuk sebelum system_p dibuat.
        is_pemerintah = "pemerintah" in agen["nama"].lower()
        if is_pemerintah and skor_ronde_lalu is not None and skor_ronde_lalu > 0.0:
            stance_rule += (
                "STANCE LOCK PEMERINTAH: Posisimu sebelumnya MENDUKUNG atau NETRAL. "
                "Kamu TIDAK BOLEH bergerak ke posisi MENOLAK â€” pemerintah tidak mengkritik kebijakannya sendiri. "
                "Jika ada tekanan, akui tantangan tapi tetap pertahankan bahwa langkah yang diambil sudah benar. "
                "Maksimal posisimu adalah NETRAL jika situasi memang kompleks. "
            )

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
            # BUG-19 FIX: cek apakah 2 ronde terakhir netral → force ambil posisi
            memori_skor = [m.get("skor", 0) for m in agen.get("memori", []) if "skor" in m]
            dua_ronde_netral = len(memori_skor) >= 2 and all(abs(s) < 0.2 for s in memori_skor[-2:])
            
            conviction_rule = (
                "ATURAN POSISI AKADEMISI: Kamu HARUS memiliki posisi yang JELAS — bukan netral tanpa alasan. "
                "Netral (skor 0) hanya valid jika: "
                "(1) bukti truly seimbang DAN (2) kamu JELASKAN di respons: 'Bukti seimbang antara X dan Y.' "
                "Jika ronde sebelumnya posisimu bukan netral, JANGAN jadi netral sekarang "
                "kecuali ada DATA BARU yang fundamental mengubah kesimpulan. "
                "CONTOH VALID netral: 'Bukti seimbang: 40% mahasiswa malas, 60% tetap rajin. Perlu data lebih untuk simpulan.' "
                "CONTOH INVALID: Hanya bilang 'Ada dua sisi, so netral.' — itu bukan argumen. "
            )
            if dua_ronde_netral:
                conviction_rule += (
                    "PERINGATAN: Kamu SUDAH 2 RONDE BERTURUT-TURUT NETRAL. "
                    "Ini TIDAK DIPERBOLEHKAN lagi. WAJIB ambil posisi di ronde ini — "
                    "PILIH: Mendukung atau Menolak. Jelaskan data mana yang membuatmu condong. "
                    "Tidak ada alasan 'butuh data lebih' setelah 2 ronde diskusi. "
                )
            
            # BUG-11 FIX: Tambahkan delta_cap_rule — cegah flip dramatis dalam 1 ronde
            if skor_ronde_lalu is not None and abs(skor_ronde_lalu) > 0.4:
                conviction_rule += (
                    "\nATURAN PERUBAHAN AKADEMISI (delta_cap): "
                    "Posisimu ronde lalu KUAT (mendukung atau menolak dengan yakin: |skor| > 0.4). "
                    "Perubahan posisi yang drastis dalam SATU ronde TIDAK VALID secara ilmiah. "
                    "Kamu hanya bisa bergerak SATU LANGKAH dalam 1 ronde:\n"
                    "  • Mendukung kuat (>0.5) → Mendukung lemah (0.2-0.5) ATAU Netral (±0.2) [jangan langsung Menolak]\n"
                    "  • Menolak kuat (<-0.5) → Menolak lemah (-0.5 ke -0.2) ATAU Netral (±0.2) [jangan langsung Mendukung]\n"
                    "Jika ingin berubah posisi total (positif ke negatif atau sebaliknya), butuh MINIMAL DUA RONDE "
                    "dengan argumen BERBEDA dan PENJELASAN EKSPLISIT di tiap ronde. "
                )


        system_p = (
            f"Kamu {agen['nama']}. {role_singkat} "
            f"GAYA BICARA WAJIB: {gaya_str}. Ikuti gaya ini secara konsisten — "
            "kalau santai pakai bahasa sehari-hari, kalau formal pakai bahasa resmi, "
            "kalau suka debat tunjukkan dengan nada kritis dan tajam. "
            + voice_anchor  # BUG-12 FIX: voice_anchor per persona
            + "Pertahankan posisimu dari ronde sebelumnya kecuali ada argumen baru yang benar-benar kuat dan data baru yang mengubah pandangan. "
            "Berubah posisi tanpa alasan konkret adalah kelemahan — bukan fleksibilitas. "
            + stance_rule
            + akademisi_rule
            + conviction_rule
            + "LARANGAN KERAS: "
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
            "JANGAN pernah memulai output dengan nama agen lain diikuti titik dua ('Pengusaha: ...', 'Akademisi: ...'). "
            "Langsung ke argumenmu sendiri tanpa menyebut nama agen lain di awal kalimat. "
            "Tulis TEPAT 2-3 kalimat pendek. Setiap kalimat HARUS diakhiri tanda titik. "
            "PELANGGARAN: Menulis lebih dari 3 kalimat adalah kesalahan fatal — potong sebelum mengirim."
        )

        # ISSUE #22 — guard agen pembuka ronde 1
        adalah_pembuka = (
            ronde_ke == 1
            and not pendapat_dalam_ronde_ini
            and not pendapat_ronde_sebelumnya
        )

        # BUG-08 FIX: stance lock khusus Pemerintah — tidak boleh flip ke Menolak
        is_pemerintah = "pemerintah" in agen["nama"].lower()
        if is_pemerintah and skor_ronde_lalu is not None and skor_ronde_lalu > 0.0:
            stance_rule += (
                "STANCE LOCK PEMERINTAH: Posisimu sebelumnya MENDUKUNG atau NETRAL. "
                "Kamu TIDAK BOLEH bergerak ke posisi MENOLAK — pemerintah tidak mengkritik kebijakannya sendiri. "
                "Jika ada tekanan, akui tantangan tapi tetap pertahankan bahwa langkah yang diambil sudah benar. "
                "Maksimal posisimu adalah NETRAL jika situasi memang kompleks. "
            )

        parts = []
        
        # BUG-10 FIX: Jika ronde 1 dan agen punya initial_stance, tambahkan sebagai anchor ke parts
        if ronde_ke == 1 and "initial_stance" in agen and not konteks_memori:
            initial = agen.get("initial_stance", 0.0)
            if isinstance(initial, (int, float)):
                if initial > 0.2:
                    arah = "MENDUKUNG"
                    parts.append(
                        "POSISI AWALMU (anchor): MENDUKUNG topik ini. "
                        "Mulai dari posisi ini dan pertahankan kecuali ada argumen data baru yang kuat dan fundamental mengubah pandangan."
                    )
                elif initial < -0.2:
                    arah = "MENOLAK"
                    parts.append(
                        "POSISI AWALMU (anchor): MENOLAK topik ini. "
                        "Mulai dari posisi ini dan pertahankan kecuali ada argumen data baru yang kuat dan fundamental mengubah pandangan."
                    )
                else:
                    arah = "NETRAL"
                    parts.append(
                        "POSISI AWALMU (anchor): NETRAL tentang topik ini. "
                        "Jika ada bukti kuat yang condong ke satu arah, ambil posisi itu dan jelaskan alasan ilmiahnya."
                    )
        
        if konteks_memori:
            parts.append(konteks_memori)

        # Stabilization PR — BUG #27: change_rule berbasis skor sentimen nyata
        if skor_ronde_lalu is not None and len(agen.get("memori", [])) >= 2:
            if skor_ronde_lalu > 0.2:
                parts.append(
                    "Ronde sebelumnya posisimu cenderung MENDUKUNG. "
                    "Jika sekarang kamu menolak atau netral, jelaskan data/argumen baru yang mengubah posisimu."
                )
            elif skor_ronde_lalu < -0.2:
                parts.append(
                    "Ronde sebelumnya posisimu cenderung MENOLAK. "
                    "Jika sekarang kamu mendukung atau netral, jelaskan data/argumen baru yang mengubah posisimu."
                )
            else:
                parts.append(
                    "Ronde sebelumnya posisimu netral. Jika sekarang kamu mengambil posisi kuat, jelaskan alasan atau data yang membuatmu condong."
                )

        if ada_yang_sudah_bicara and konteks_pengaruh:
            parts.append(konteks_pengaruh)
            # Phase 4: explicit response target (jika ada)
            if current_response_target and current_response_target != agen["nama"]:
                parts.append(
                    f"Respons khusus untuk {current_response_target}. "
                    f"Counter argumen {current_response_target} dengan data dan posisimu. "
                    "Jangan ulangi argumen yang sudah disampaikan."
                )
            else:
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
        # Stabilization PR — BUG #26: filter forbidden opens (sebelum potong)
        jawaban  = filter_forbidden_opens(jawaban)
        # BUG #23 — post-processing: pastikan output maksimal 3 kalimat
        jawaban  = _batasi_kalimat(jawaban, max_kalimat=3)
        # Stabilization PR — BUG #26: filter lagi sesudah dipotong (kalimat baru bisa jadi pembuka baru)
        jawaban  = filter_forbidden_opens(jawaban)
        sentimen = score_sentiment(jawaban, topik=topik_ronde, sentiment_mode=sentiment_mode)

        # BUG-19 ENFORCEMENT: post-processing untuk Akademisi
        # Prompt-level conviction_rule sering diabaikan LLM → retry dengan instruksi lebih keras
        if ("akademisi" in agen.get("nama", "").lower() or "dosen" in agen.get("role", "").lower()):
            if sentimen["label"] == "netral":
                memori_skor = [m.get("skor", 0.0) for m in agen.get("memori", []) if "skor" in m]
                # Cek: apakah ronde sebelumnya juga netral? (2 ronde netral berturut-turut)
                if len(memori_skor) >= 1 and abs(memori_skor[-1]) < 0.2:
                    user_p += (
                        "\nPERINTAH TERAKHIR — Kamu SUDAH 2+ RONDE NETRAL. "
                        "WAJIB ambil posisi SEKARANG: MENDUKUNG atau MENOLAK. "
                        "Tulis argumen data yang membuatmu condong ke satu arah. "
                        "JANGAN KEMBALIKAN NETRAL."
                    )
                    _retry_jawaban = call_llm(system_p, user_p, max_tokens=MAX_TOKENS_AGENT, model=MODEL_AGENT)
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
                # Cek: apakah ronde sebelumnya juga netral? (2 ronde netral berturut-turut)
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
    event_impacts: dict[str, dict[str, float]] = {}  # agent_name -> impact_score
    # Phase 4: current response target (set before each agent call)
    current_response_target: str | None = None

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
            # Simpan impact untuk referensi per-agen nanti
            event_impacts[intervensi] = active_event_impacts

        output_ronde       = {"ronde": ronde_ke, "agen": []}
        pendapat_ronde_ini = []
        # Pendapat yang sudah terkumpul di ronde ini (diupdate setiap agen selesai bicara)
        pendapat_dalam_ronde_ini: list[dict] = []

        # Phase 4: tentukan urutan bicara via scheduler
        order = get_speaking_order(agents, ronde_ke, strategy=scheduler_strategy)
        urutan_agen = [agents[i] for i in order]

        # ── SEQUENTIAL — satu agen per call, bukan paralel ───────────────
        for idx, agen in enumerate(urutan_agen):
            # Phase 4: pilih target respons sebelum agen bicara
            current_response_target = select_response_target(
                current_nama=agen["nama"],
                agents=agents,
                ronde_ke=ronde_ke,
                pendapat_dalam_ronde_ini=pendapat_dalam_ronde_ini,
                pendapat_ronde_sebelumnya=pendapat_ronde_sebelumnya,
                strategy=scheduler_strategy,
            )
            try:
                res = _proses_satu_agen(agen, ronde_ke, topik_ronde, pendapat_dalam_ronde_ini, idx_agen=idx)
            except Exception as e:
                # BUG-06 FIX: log tipe error secara eksplisit agar tidak silent-swallow
                import traceback
                error_type = type(e).__name__
                error_msg  = str(e)
                print(f"[Error] {agen['nama']} ronde {ronde_ke}: {error_type}: {error_msg}")
                print(f"[Traceback] {traceback.format_exc()}")
                # Fallback response menyertakan tipe error agar bisa di-debug dari laporan
                res = {
                    "nama":     agen["nama"],
                    "pendapat": f"(tidak dapat merespons saat ini — {error_type})",
                    "sentimen": {"label": "netral", "skor": 0.0},
                    "pengaruh": agen.get("pengaruh", 0.5),
                }

            # Phase 2: track AgentAction
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

        # Phase 8: update crowd setelah tiap ronde
        if crowd_pool:
            crowd_pool.update_from_llm_agents(pendapat_ronde_ini, ronde_ke)

        # Jeda antar ronde
        if ronde_ke < jumlah_ronde:
            time.sleep(ROUND_DELAY)

    # ── GraphRAG extraction ──────────────────────────────────────────────
    graf_data = (
        {"entitas": [], "relasi": [], "disabled": True, "reason": "free_tier_mode"}
        if tier == "free" else extract_entities(topik, log_diskusi)
    )

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
    if tier == "free":
        analisis_raw = _analisis_fallback_text(topik, sentimen_agregat)
        pengaruh_map, volatilitas, _ = _build_ringkasan_agen(agents, sentimen_agregat)
        aktor_analisis = _aktor_fallback(pengaruh_map, volatilitas, sentimen_agregat)
    else:
        analisis_raw, aktor_analisis = _analisis_dan_aktor(
            topik, log_diskusi, agents, sentimen_agregat
        )
    analisis_raw = _strip_emoji(analisis_raw)
    prediksi = _parse_prediksi(analisis_raw)

    # Phase 2: Rebuild simulation_state from AgentAction records
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

    # Phase 8: Crowd data
    crowd_data = crowd_pool.to_dict() if crowd_pool else None
    crowd_distribution: dict[str, float] = {}
    if crowd_data:
        crowd_distribution = crowd_data.get("distribution", {})

    # Phase 6: Heuristic prediction + confidence
    quality_score = float(simulation_quality.get("score", 1.0) or 1.0)
    heuristic_result = heuristic_predict(
        sentimen_agregat=sentimen_agregat,
        n_agents=n_agents,
        n_rounds=jumlah_ronde,
        quality_score=quality_score,
        events=events,
    )
    prediction_confidence = heuristic_result["confidence"]
    prediction_reasoning = heuristic_result["reasoning"]

    return {
        "ronde_detail":      ronde_detail,
        "graf_data":         graf_data,
        "analisis":          analisis_raw,
        "prediksi":          prediksi,
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
            "crowd_mendukung":    crowd_distribution.get("mendukung", 0),
            "crowd_menolak":      crowd_distribution.get("menolak", 0),
            "crowd_netral":       crowd_distribution.get("netral", 0),
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
        },
        "events":           simulation_state_payload.get("events", []),
        "jumlah_ronde":     jumlah_ronde,
        "topik":            topik,
        "intervensi":       intervensi,
        "aktor_analisis":       aktor_analisis,
        "prediction_confidence": prediction_confidence,
        "prediction_reasoning":  prediction_reasoning,
        "prediction_source": {
            "prediksi":  "llm_analisis" if "tidak tersedia" not in analisis_raw.lower() else "heuristic_fallback",
            "confidence": "heuristic",
        },
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


def _build_simulation_quality(
    n_agents: int,
    jumlah_ronde: int,
    estimated_llm_calls: int,
    tier: str = "free",
) -> dict:
    """Nilai kualitas metodologis simulasi tanpa memanggil LLM."""
    score = 1.0
    limitations = []

    sentiment_mode_efektif = "inline" if tier == "free" else SENTIMENT_MODE
    graph_llm_enabled = tier != "free" and not DISABLE_GRAPH_LLM
    analysis_llm_enabled = tier != "free" and not DISABLE_FINAL_ANALYSIS_LLM

    if sentiment_mode_efektif == "inline":
        score -= 0.18
        limitations.append("Sentiment scoring memakai mode inline, jadi pembacaan konteks/negasi lebih kasar.")
    elif sentiment_mode_efektif == "ml":
        limitations.append("Sentiment scoring memakai ML classifier — deterministik, 0 LLM call.")
    if not graph_llm_enabled:
        score -= 0.12
        limitations.append("GraphRAG LLM dimatikan, peta entitas dan relasi tidak diekstrak penuh.")
    if not analysis_llm_enabled:
        score -= 0.16
        limitations.append("Analisis akhir memakai fallback rule-based, bukan narasi analis LLM.")
    if n_agents < 5:
        score -= 0.12
        limitations.append(f"Jumlah agen hanya {n_agents}; keragaman perspektif terbatas.")
    if jumlah_ronde < 3:
        score -= 0.12
        limitations.append(f"Jumlah ronde hanya {jumlah_ronde}; dinamika perubahan opini masih pendek.")

    score = max(0.0, min(1.0, round(score, 2)))
    if score >= 0.8:
        tier = "high"
        label = "Eksplorasi kuat"
    elif score >= 0.6:
        tier = "medium"
        label = "Eksplorasi menengah"
    else:
        tier = "low"
        label = "Draft cepat"

    return {
        "score": score,
        "tier": tier,
        "label": label,
        "estimated_llm_calls": estimated_llm_calls,
        "limitations": limitations,
        "interpretation": (
            "Hasil ini layak dibaca sebagai simulasi eksploratif, bukan prediksi faktual."
        ),
    }


def _analisis_fallback_text(topik: str, sentimen_agregat: dict) -> str:
    """Analisis ringkas tanpa LLM untuk mode hemat/free tier."""
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
