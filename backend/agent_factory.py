# backend/agent_factory.py
# Phase 8: AgentFactory — injeksi agen kontekstual berdasarkan keyword topik

import re
import json

from backend.llm import call_llm

# ponytail: signature_keywords = nama-identifying match dgn priority 999 (auto-lolos)
#            keywords = keyword pendukung, minimal 2 match baru masuk
ARCHETYPE_POOL = {
    "Perwira_TNI": {
        "nama": "Perwira TNI",
        "role": "Kamu perwira tinggi TNI yang bicara tegas, disiplin, dan mengutamakan pertahanan & keamanan nasional. Pandanganmu selalu mempertimbangkan dampak terhadap stabilitas negara.",
        "kepribadian": {"openness": 0.4, "agreeableness": 0.4, "neuroticism": 0.3},
        "pengaruh": 0.8,
        "initial_stance": 0.3,
        "signature_keywords": ["tni"],
        "keywords": ["militer", "pertahanan", "keamanan", "prabowo", "alutsista", "perang", "senjata", "bela negara"],
    },
    "Dokter_Nakes": {
        "nama": "Dokter/Nakes",
        "role": "Kamu tenaga kesehatan yang bicara berdasarkan fakta medis dan pengalaman di lapangan. Peduli pada sistem kesehatan dan kesejahteraan pasien.",
        "kepribadian": {"openness": 0.6, "agreeableness": 0.6, "neuroticism": 0.4},
        "pengaruh": 0.75,
        "initial_stance": 0.0,
        "signature_keywords": ["dokter"],
        "keywords": ["kesehatan", "rumah sakit", "vaksin", "bpjs", "obat", "pandemi", "imunisasi", "bergizi", "makan", "stunting"],
    },
    "Petani": {
        "nama": "Petani",
        "role": "Kamu petani yang bicara sederhana dan langsung. Hidupmu tergantung pada hasil panen, cuaca, dan harga pupuk. Kamu ingin kebijakan yang berpihak pada petani kecil.",
        "kepribadian": {"openness": 0.3, "agreeableness": 0.7, "neuroticism": 0.5},
        "pengaruh": 0.65,
        "initial_stance": 0.0,
        "signature_keywords": ["petani"],
        "keywords": ["pertanian", "pangan", "pupuk", "beras", "panen", "irigasi", "lahan", "sawah"],
    },
    "Nelayan": {
        "nama": "Nelayan",
        "role": "Kamu nelayan tradisional yang menggantungkan hidup pada laut. Kamu khawatir dengan kebijakan yang mengancam sumber penghasilanmu.",
        "kepribadian": {"openness": 0.3, "agreeableness": 0.65, "neuroticism": 0.55},
        "pengaruh": 0.6,
        "initial_stance": -0.1,
        "signature_keywords": ["nelayan"],
        "keywords": ["laut", "perikanan", "ikan", "pelabuhan", "maritim", "kapal"],
    },
    "Ulama": {
        "nama": "Ulama",
        "role": "Kamu ulama yang bicara dengan hikmah dan moralitas. Kamu melihat setiap isu dari sisi etika, agama, dan dampak sosial bagi umat.",
        "kepribadian": {"openness": 0.35, "agreeableness": 0.55, "neuroticism": 0.35},
        "pengaruh": 0.85,
        "initial_stance": 0.1,
        "signature_keywords": ["ulama"],
        "keywords": ["moral", "etika", "agama", "syariah", "fatwa", "masjid", "zakat", "halal"],
    },
    "Buruh_Pabrik": {
        "nama": "Buruh Pabrik",
        "role": "Kamu buruh pabrik yang bekerja keras tapi pendapatan pas-pasan. Kamu sangat peka terhadap isu upah, PHK, dan kenaikan harga kebutuhan pokok.",
        "kepribadian": {"openness": 0.3, "agreeableness": 0.5, "neuroticism": 0.7},
        "pengaruh": 0.65,
        "initial_stance": -0.3,
        "signature_keywords": ["buruh"],
        "keywords": ["upah", "phk", "pabrik", "gaji", "umr", "thr", "pekerja", "demo buruh"],
    },
    "Aktivis_Lingkungan": {
        "nama": "Aktivis Lingkungan",
        "role": "Kamu aktivis lingkungan yang vokal menolak perusakan alam. Kamu selalu mempertanyakan dampak ekologis dari setiap kebijakan.",
        "kepribadian": {"openness": 0.9, "agreeableness": 0.2, "neuroticism": 0.5},
        "pengaruh": 0.7,
        "initial_stance": -0.3,
        "signature_keywords": ["lingkungan"],
        "keywords": ["hutan", "polusi", "ekologi", "iklim", "limbah", "reklamasi", "tambang", "green"],
    },
    "Guru": {
        "nama": "Guru",
        "role": "Kamu guru yang peduli pada pendidikan dan masa depan generasi muda. Kamu bicara berdasarkan pengalaman mengajar dan realitas di sekolah.",
        "kepribadian": {"openness": 0.6, "agreeableness": 0.7, "neuroticism": 0.4},
        "pengaruh": 0.7,
        "initial_stance": 0.1,
        "signature_keywords": ["guru"],
        "keywords": ["pendidikan", "sekolah", "kurikulum", "ppdb", "unbk", "beasiswa", "siswa", "mahal", "makanan", "anak"],
    },
    "Startup_Founder": {
        "nama": "Founder Startup",
        "role": "Kamu pendiri startup teknologi yang optimis pada inovasi digital. Kamu bicara tentang peluang, efisiensi, dan masa depan industri 4.0.",
        "kepribadian": {"openness": 0.95, "agreeableness": 0.5, "neuroticism": 0.3},
        "pengaruh": 0.7,
        "initial_stance": 0.3,
        "signature_keywords": ["startup"],
        "keywords": ["digital", "teknologi", "inovasi", "ai", "aplikasi", "online", "e-commerce"],
    },
    "Kepala_Daerah": {
        "nama": "Kepala Daerah",
        "role": "Kamu kepala daerah yang pragmatis — harus menyeimbangkan kepentingan pusat dan daerah. Kamu bicara tentang anggaran, pembangunan, dan pelayanan publik.",
        "kepribadian": {"openness": 0.5, "agreeableness": 0.6, "neuroticism": 0.3},
        "pengaruh": 0.75,
        "initial_stance": 0.2,
        "signature_keywords": ["kepala daerah"],
        "keywords": ["daerah", "provinsi", "kabupaten", "otonomi", "pilkada", "pembangunan daerah", "apbd", "ruu", "perda", "regulasi", "kebijakan", "apbn", "legislasi"],
    },
    "Ibu_Rumah_Tangga": {
        "nama": "Ibu Rumah Tangga",
        "role": "Kamu ibu rumah tangga yang mengatur keuangan keluarga. Kamu sangat sensitif terhadap harga sembako, listrik, dan biaya sekolah anak. Bicara apa adanya dari pengalaman sehari-hari.",
        "kepribadian": {"openness": 0.3, "agreeableness": 0.75, "neuroticism": 0.7},
        "pengaruh": 0.65,
        "initial_stance": -0.2,
        "signature_keywords": ["ibu rumah tangga"],
        "keywords": ["sembako", "bbm", "gas", "listrik", "harga", "sembilan bahan", "dapur", "keluarga"],
    },
    "Ibu_Hamil": {
        "nama": "Ibu Hamil/Menyusui",
        "role": "Kamu ibu hamil atau menyusui yang sangat peduli pada gizi anak dan kesehatan keluarga. Kamu mengikuti program kesehatan pemerintah dan merasakan langsung dampaknya di posyandu dan puskesmas.",
        "kepribadian": {"openness": 0.5, "agreeableness": 0.7, "neuroticism": 0.6},
        "pengaruh": 0.7,
        "initial_stance": 0.1,
        "signature_keywords": ["ibu hamil"],
        "keywords": ["bergizi", "makan", "anak", "posyandu", "stunting", "asi", "balita", "imunisasi"],
    },
    "Pengamat_Hukum": {
        "nama": "Pengamat Hukum",
        "role": "Kamu pengamat hukum yang kritis terhadap penegakan aturan. Kamu selalu mempertanyakan kepatuhan hukum, celah regulasi, dan keadilan.",
        "kepribadian": {"openness": 0.8, "agreeableness": 0.25, "neuroticism": 0.4},
        "pengaruh": 0.72,
        "initial_stance": -0.2,
        "signature_keywords": ["hukum"],
        "keywords": ["korupsi", "kpk", "peradilan", "regulasi", "putusan", "hakim", "uji materi", "ruu", "undang-undang", "legislasi", "peraturan", "mahkamah"],
    },
    "Diaspora": {
        "nama": "Diaspora Indonesia",
        "role": "Kamu warga Indonesia yang tinggal di luar negeri. Kamu punya perspektif global dan sering membandingkan kebijakan Indonesia dengan negara lain.",
        "kepribadian": {"openness": 0.85, "agreeableness": 0.45, "neuroticism": 0.35},
        "pengaruh": 0.65,
        "initial_stance": 0.1,
        "signature_keywords": ["diaspora"],
        "keywords": ["luar negeri", "global", "wni", "imigrasi", "ekspatriat", "asing"],
    },
    "Pengusaha_Besar": {
        "nama": "Pengusaha Besar",
        "role": "Kamu pengusaha besar dengan jaringan luas. Kamu bicara tentang investasi, iklim usaha, dan kebijakan yang mempengaruhi pertumbuhan ekonomi makro.",
        "kepribadian": {"openness": 0.6, "agreeableness": 0.5, "neuroticism": 0.25},
        "pengaruh": 0.85,
        "initial_stance": 0.2,
        "signature_keywords": ["pengusaha"],
        "keywords": ["investasi", "korporasi", "saham", "ekonomi makro", "pajak", "ekspor", "impor"],
    },
    "Aktivis_HAM": {
        "nama": "Aktivis HAM",
        "role": "Kamu aktivis HAM yang vokal memperjuangkan hak asasi. Kamu kritis terhadap pelanggaran kebebasan berekspresi, diskriminasi, dan kekerasan negara.",
        "kepribadian": {"openness": 0.9, "agreeableness": 0.15, "neuroticism": 0.6},
        "pengaruh": 0.72,
        "initial_stance": -0.3,
        "signature_keywords": ["ham"],
        "keywords": ["hak asasi", "diskriminasi", "kebebasan", "represi", "penculikan", "pembubaran"],
    },
}


# ponytail: fallback ketika keyword match 0 — pilih archetype relevan berdasarkan kategori
KATEGORI_ARCHETYPE_FALLBACK: dict[str, list[str]] = {
    "Ekonomi":   ["Pengusaha_Besar", "Buruh_Pabrik", "Petani"],
    "Politik":   ["Kepala_Daerah", "Pengamat_Hukum", "Ulama"],
    "Sosial":    ["Ibu_Rumah_Tangga", "Guru", "Aktivis_Lingkungan", "Aktivis_HAM"],
    "Hukum":     ["Pengamat_Hukum", "Aktivis_HAM"],
    "Teknologi": ["Startup_Founder", "Dokter_Nakes"],
    "Kebijakan": ["Kepala_Daerah", "Pengamat_Hukum", "Perwira_TNI"],
    "RUU":       ["Pengamat_Hukum", "Aktivis_HAM", "Kepala_Daerah"],
    "Anggaran":  ["Pengusaha_Besar", "Kepala_Daerah", "Buruh_Pabrik"],
    "Umum":      ["Ibu_Rumah_Tangga", "Guru", "Buruh_Pabrik"],
}


def get_contextual_agents(topik: str, max_agents: int = 3, kategori: str | None = None) -> list[dict]:
    """
    Cari archetype yang relevan dengan topik berdasarkan keyword matching.

    Signature keywords: auto-lolos (priority 999) — identitas nama archetype.
    Keywords pendukung: minimal 2 match baru masuk (cegah false positive).
    Kategori fallback: dipake kalo keyword match 0 — pilih archetype relevan dari kategori.

    Args:
        topik: Topik simulasi (akan dicocokkan dengan keywords tiap archetype).
        max_agents: Maksimal agen kontekstual yang dikembalikan.
        kategori: Kategori (fallback kalo keyword match 0).

    Returns:
        List agen dict (salinan fresh dengan memori kosong).
    """
    topik_lower = topik.lower()

    _match = lambda kw: re.search(rf'\b{re.escape(kw)}\b', topik_lower)

    skor_archetype: list[tuple[str, int]] = []
    for kunci, archetype in ARCHETYPE_POOL.items():
        # Signature check — auto-lolos kalo nama archetype disebut
        sig = archetype.get("signature_keywords", [])
        if any(_match(kw) for kw in sig):
            skor_archetype.append((kunci, 999))
            continue

        # Keyword pendukung — minimal 2 match
        skor = sum(1 for kw in archetype["keywords"] if _match(kw))
        if skor >= 2:
            skor_archetype.append((kunci, skor))

    # ── Kategori fallback: kalo keyword match 0, pilih berdasarkan kategori ──
    if not skor_archetype and kategori:
        kunci_fallback = KATEGORI_ARCHETYPE_FALLBACK.get(kategori, [])
        for kunci in kunci_fallback[:max_agents]:
            skor_archetype.append((kunci, 1))  # skor 1 = fallback

    # Urutkan: signature (999) di atas, lalu keyword count
    skor_archetype.sort(key=lambda x: -x[1])

    hasil = []
    for kunci, _ in skor_archetype[:max_agents]:
        archetype = ARCHETYPE_POOL[kunci]
        agen = dict(archetype)
        agen["memori"] = []
        agen.pop("signature_keywords", None)
        agen.pop("keywords", None)
        hasil.append(agen)

    return hasil


def _parse_json_array(text: str) -> list | None:
    """Parse JSON array dari teks mentah LLM, repair kalau truncated."""
    # Bersihin markdown code fence
    clean = re.sub(r"```(?:json)?|```", "", text).strip()

    # Coba parse langsung
    try:
        parsed = json.loads(clean)
        return parsed if isinstance(parsed, list) else None
    except json.JSONDecodeError:
        pass

    # Cari [...] terakhir di teks
    m = re.search(r"\[.*", clean, re.DOTALL)
    if not m:
        return None
    candidate = m.group()

    # ── Repair bertahap ──
    # 1. Fix truncated number di akhir: ": 0." → ": 0.0"
    candidate = re.sub(r':\s*(-?\d+)\.\s*$', r': \1.0', candidate)

    # 2. Tutup kurung kurawal yang belum ditutup
    while candidate.count("{") > candidate.count("}"):
        candidate += "}"
    # 3. Tutup kurung siku yang belum ditutup
    while candidate.count("[") > candidate.count("]"):
        candidate += "]"

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, list) else None
    except json.JSONDecodeError:
        pass

    return None


def _is_semantic_duplicate(nama_baru: str, existing_names: list[str]) -> bool:
    """
    Deteksi duplikat semantik sederhana: overlap kata kunci antar nama.
    Kalau >= 1 kata non-stopword (len > 3) overlap, anggap duplikat.
    """
    stopwords = {"dan", "atau", "yang", "di", "ke", "dari", "ini", "itu", "para"}
    kata_baru = {k for k in nama_baru.lower().replace("/", " ").split() if len(k) > 3 and k not in stopwords}
    if not kata_baru:
        return False
    for existing in existing_names:
        kata_existing = {k for k in existing.lower().replace("/", " ").split() if len(k) > 3 and k not in stopwords}
        if kata_baru & kata_existing:
            return True
    return False


def propose_llm_agents(topik: str, max_agents: int = 3,
                       existing_names: list[str] | None = None) -> list[dict]:
    """
    LLM-based agent proposal untuk tier Lengkap.
    Minta LLM propose 3-4 stakeholder relevan spesifik ke topik,
    lalu return sebagai agent objects siap pakai.

    Args:
        topik: Topik simulasi.
        max_agents: Maksimal agen yang dikembalikan.
        existing_names: Roster agent yang sudah ada — LLM diinstruksikan hindari overlap.

    Returns:
        List agen dict (dengan role, pengaruh, initial_stance dari LLM).
    """
    existing = existing_names or []

    prompt = (
        f"Topik kebijakan: {topik}\n\n"
        "Sebutkan 3-4 kelompok MASYARAKAT atau STAKEHOLDER yang PALING relevan dan "
        "terdampak langsung oleh topik ini. "
        "Jangan sebut aktor generik seperti Pemerintah, Media, Akademisi, atau Mahasiswa "
        "\u2014 fokus pada kelompok spesifik yang terkait langsung dengan topik.\n"
    )

    if existing:
        prompt += (
            "\nRoster stakeholder yang SUDAH ADA di simulasi ini:\n"
            f"{chr(10).join('- ' + n for n in existing)}\n\n"
            "PENTING: Jangan usulkan kelompok yang secara makna SAMA atau TUMPANG TINDIH "
            "dengan roster di atas. Misalnya kalau sudah ada 'Ibu Hamil/Menyusui', "
            "jangan usulkan 'Ibu Menyusui' atau 'Ibu Hamil' secara terpisah. "
            "Fokus ke stakeholder yang BENAR-BENAR BEDA dan belum terwakili.\n\n"
        )

    prompt += (
        "Untuk setiap kelompok, berikan:\n"
        "- nama: nama singkat kelompok (contoh: 'Ibu Hamil', 'Petani Lokal', 'Penyedia Katering Sekolah')\n"
        "- role: 1-2 kalimat deskripsi singkat tentang perspektif kelompok ini terhadap topik\n"
        "- pengaruh: skor 0.0-1.0 seberapa besar pengaruh kelompok ini dalam opini publik terkait topik\n"
        "- initial_stance: skor -1.0 s/d 1.0 (negatif = cenderung menolak, positif = cenderung mendukung)\n\n"
        "Balas HANYA JSON array:\n"
        '[{"nama":"...","role":"...","pengaruh":0.0,"initial_stance":0.0}]'
    )

    raw = call_llm(
        "Kamu adalah analis kebijakan publik. Balas HANYA JSON array valid.",
        prompt,
        max_tokens=600,
    )
    parsed = _parse_json_array(raw)
    if not parsed:
        return []

    hasil = []
    for item in parsed[:max_agents]:
        nama = (item.get("nama") or "").strip()
        role = (item.get("role") or "").strip()
        if not nama or not role:
            continue
        hasil.append({
            "nama":        nama,
            "role":        role,
            "kepribadian": {"openness": 0.6, "agreeableness": 0.6, "neuroticism": 0.4},
            "pengaruh":    float(item.get("pengaruh") or 0.7),
            "memori":      [],
            "initial_stance": float(item.get("initial_stance") or 0.0),
        })

    return hasil
