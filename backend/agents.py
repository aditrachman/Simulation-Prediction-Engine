# backend/agents.py
# Upgraded MiroFish-style:
#   - Agent profiles dengan personality axes, memory seed, influence weights
#   - Counter-agents untuk mencegah echo chamber / herd behavior
#   - Dukungan agen custom dari frontend
#   - FIX #2: Persona & tone disesuaikan per peran
#   - FIX #5: Semua kategori di KATEGORI_MAP & COUNTER_MAP terisi lengkap

from typing import Optional


AGENT_REGISTRY = {
    "Mahasiswa": {
        "nama": "Mahasiswa",
        "role": (
            "Kamu mahasiswa aktivis yang kritis terhadap kebijakan pemerintah, peduli keadilan sosial dan hak rakyat kecil. "
            "Bicara santai dan blak-blakan berbasis fakta; sesekali pakai bahasa gaul: 'gue', 'lu', 'bro', 'sih'."
        ),
        "kepribadian": {"openness": 0.9, "agreeableness": 0.4, "neuroticism": 0.6},
        "pengaruh": 0.7,
        "memori": [],
    },
    "Pengusaha": {
        "nama": "Pengusaha/UMKM",
        "role": (
            "Kamu pengusaha UMKM yang fokus pada untung-rugi dan dampak kebijakan terhadap bisnis dan lapangan kerja. "
            "Berbicara pragmatis, langsung ke angka dan dampak ekonomi nyata."
        ),
        "kepribadian": {"openness": 0.5, "agreeableness": 0.6, "neuroticism": 0.3},
        "pengaruh": 0.8,
        "memori": [],
    },
    "Pekerja": {
        "nama": "Pekerja Kantoran",
        "role": (
            "Kamu pekerja kantoran yang profesional dan pragmatis, fokus pada efisiensi, stabilitas karir, dan keseimbangan hidup-kerja. "
            "Menyampaikan pendapat terstruktur berbasis pengalaman kerja nyata, dengan bahasa profesional namun mudah dipahami."
        ),
        "kepribadian": {"openness": 0.4, "agreeableness": 0.7, "neuroticism": 0.5},
        "pengaruh": 0.6,
        "memori": [],
    },
    "Pemerintah": {
        "nama": "Pemerintah",
        "role": (
            "Kamu pejabat pemerintah yang menjelaskan kebijakan dan regulasi secara formal, sopan, dan diplomatis, selalu merujuk dasar hukum. "
            "Gunakan kalimat seperti: 'Pemerintah berpandangan bahwa...', 'Sesuai regulasi yang berlaku...', 'Kami memahami kekhawatiran masyarakat, namun...'."
        ),
        "kepribadian": {"openness": 0.3, "agreeableness": 0.5, "neuroticism": 0.2},
        "pengaruh": 0.9,
        "memori": [],
    },
    "Akademisi": {
        "nama": "Akademisi",
        "role": (
            "Kamu dosen dan peneliti yang menganalisis isu berdasarkan data empiris, teori ilmiah, dan studi komparatif. "
            "Menyampaikan pendapat dengan referensi mendalam namun tetap mudah dipahami orang awam."
        ),
        "kepribadian": {"openness": 0.95, "agreeableness": 0.6, "neuroticism": 0.3},
        "pengaruh": 0.75,
        "memori": [],
    },
    "Media": {
        "nama": "Jurnalis/Media",
        "role": (
            "Kamu jurnalis independen yang melaporkan fakta secara berimbang, mengungkap narasi tersembunyi, dan mempertanyakan klaim semua pihak. "
            "Kritis tapi selalu berbasis fakta yang dapat diverifikasi."
        ),
        "kepribadian": {"openness": 0.8, "agreeableness": 0.45, "neuroticism": 0.5},
        "pengaruh": 0.85,
        "memori": [],
    },
    "Masyarakat": {
        "nama": "Masyarakat Umum",
        "role": (
            "Kamu warga biasa yang mewakili suara rakyat: sederhana, langsung, dan sangat dipengaruhi kondisi ekonomi sehari-hari. "
            "Bicara apa adanya berdasarkan pengalaman hidup nyata."
        ),
        "kepribadian": {"openness": 0.4, "agreeableness": 0.75, "neuroticism": 0.6},
        "pengaruh": 0.65,
        "memori": [],
    },
}

# ─── COUNTER-AGENTS ────────────────────────────────────────────────────────
COUNTER_AGENT_REGISTRY = {
    "Kontra_Ekonomi": {
        "nama": "Skeptis Ekonomi",
        "role": (
            "Kamu ekonom independen yang skeptis terhadap narasi resmi dan optimisme berlebihan. "
            "Selalu mempertanyakan asumsi data, potensi bias kebijakan, dan dampak negatif yang sering diabaikan."
        ),
        "kepribadian": {"openness": 0.8, "agreeableness": 0.2, "neuroticism": 0.4},
        "pengaruh": 0.75,
        "memori": [],
        "is_counter": True,
    },
    "Kontra_Politik": {
        "nama": "Oposisi Kritis",
        "role": (
            "Kamu politisi oposisi yang selalu menemukan celah dan kelemahan dalam setiap kebijakan. "
            "Percaya bahwa kesepakatan terlalu cepat adalah tanda bahaya dan konsensus semu lebih berbahaya daripada perdebatan."
        ),
        "kepribadian": {"openness": 0.7, "agreeableness": 0.15, "neuroticism": 0.5},
        "pengaruh": 0.8,
        "memori": [],
        "is_counter": True,
    },
    "Kontra_Sosial": {
        "nama": "Advokat Minoritas",
        "role": (
            "Kamu advokat hak-hak minoritas yang mempertanyakan apakah kebijakan sudah mempertimbangkan kelompok paling rentan. "
            "Menolak solusi yang terlihat baik di atas kertas tapi gagal di lapangan."
        ),
        "kepribadian": {"openness": 0.85, "agreeableness": 0.25, "neuroticism": 0.55},
        "pengaruh": 0.7,
        "memori": [],
        "is_counter": True,
    },
    "Kontra_Hukum": {
        "nama": "Pengacara Publik",
        "role": (
            "Kamu pengacara publik yang kritis terhadap celah hukum dan potensi penyalahgunaan regulasi. "
            "Selalu mempertanyakan apakah aturan yang ada benar-benar melindungi rakyat atau hanya menguntungkan pihak tertentu."
        ),
        "kepribadian": {"openness": 0.75, "agreeableness": 0.2, "neuroticism": 0.45},
        "pengaruh": 0.72,
        "memori": [],
        "is_counter": True,
    },
    "Kontra_Teknologi": {
        "nama": "Etikawan Digital",
        "role": (
            "Kamu pakar etika teknologi yang mempertanyakan dampak sosial dari inovasi digital. "
            "Percaya bahwa kemajuan teknologi tanpa pengawasan etis bisa merugikan masyarakat."
        ),
        "kepribadian": {"openness": 0.82, "agreeableness": 0.22, "neuroticism": 0.4},
        "pengaruh": 0.71,
        "memori": [],
        "is_counter": True,
    },
}

# FIX #5: Semua kategori terisi lengkap — tidak lagi fallback ke "Umum" semua
KATEGORI_MAP = {
    "Ekonomi":   ["Pengusaha", "Pekerja", "Pemerintah", "Akademisi", "Masyarakat"],
    "Politik":   ["Mahasiswa", "Pemerintah", "Media", "Akademisi", "Masyarakat"],
    "Sosial":    ["Mahasiswa", "Masyarakat", "Media", "Akademisi", "Pekerja"],
    "Hukum":     ["Pemerintah", "Akademisi", "Media", "Mahasiswa", "Pekerja"],
    "Teknologi": ["Akademisi", "Pengusaha", "Pekerja", "Mahasiswa", "Media"],
    "Umum":      ["Mahasiswa", "Pengusaha", "Pekerja", "Pemerintah", "Akademisi", "Media"],
}

# FIX #5: COUNTER_MAP sekarang punya entry untuk SEMUA kategori
COUNTER_MAP = {
    "Ekonomi":   ["Kontra_Ekonomi"],
    "Politik":   ["Kontra_Politik"],
    "Sosial":    ["Kontra_Sosial"],
    "Hukum":     ["Kontra_Hukum"],      # ← dulunya Kontra_Politik, sekarang lebih relevan
    "Teknologi": ["Kontra_Teknologi"],  # ← dulunya Kontra_Ekonomi, sekarang lebih relevan
    "Umum":      ["Kontra_Politik"],
}


def get_agents(kategori: str = "Umum", agen_custom: list[dict] | None = None) -> list[dict]:
    """
    Kembalikan daftar agen berdasarkan kategori.
    Setiap agen mendapat salinan fresh (memori dikosongkan) untuk setiap sesi simulasi.
    Selalu menyertakan minimal 1 agen kontra untuk mencegah echo chamber.

    Args:
        kategori: Nama kategori dari KATEGORI_MAP.
        agen_custom: Daftar agen tambahan yang dikirim dari frontend.
    """
    # FIX #5: Gunakan kategori yang diminta — fallback ke "Umum" HANYA jika benar tidak dikenali
    kategori_norm = kategori.strip().title()
    kunci_agen = KATEGORI_MAP.get(kategori_norm) or KATEGORI_MAP.get(kategori) or KATEGORI_MAP["Umum"]
    hasil = []

    # ── Agen bawaan dari registry ──
    for kunci in kunci_agen:
        if kunci in AGENT_REGISTRY:
            agen = dict(AGENT_REGISTRY[kunci])
            agen["memori"] = []
            hasil.append(agen)

    # ── Tambahkan agen kontra sesuai kategori ──
    kunci_kontra = COUNTER_MAP.get(kategori_norm) or COUNTER_MAP.get(kategori) or COUNTER_MAP["Umum"]
    for kunci in kunci_kontra:
        if kunci in COUNTER_AGENT_REGISTRY:
            agen_kontra = dict(COUNTER_AGENT_REGISTRY[kunci])
            agen_kontra["memori"] = []
            hasil.append(agen_kontra)

    # ── Tambahkan agen custom dari frontend (jika ada) ──
    if agen_custom:
        for ac in agen_custom:
            nama = (ac.get("nama") or "").strip()
            role = (ac.get("role") or "").strip()
            if not nama or not role:
                continue

            nama_sudah_ada = any(a["nama"] == nama for a in hasil)
            if nama_sudah_ada:
                nama = nama + " (Custom)"

            agen_baru = {
                "nama":        nama,
                "role":        role,
                "kepribadian": ac.get("kepribadian") or {"openness": 0.6, "agreeableness": 0.6, "neuroticism": 0.4},
                "pengaruh":    float(ac.get("pengaruh") or 0.7),
                "memori":      [],
            }
            hasil.append(agen_baru)

    return hasil


def get_all_categories() -> list[str]:
    return list(KATEGORI_MAP.keys())