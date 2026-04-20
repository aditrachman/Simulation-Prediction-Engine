# backend/agents.py
# Upgraded: agent profiles now include personality axes, memory seed, and influence weights
# + dukungan agen custom yang dikirim dari frontend

from typing import Optional


AGENT_REGISTRY = {
    "Mahasiswa": {
        "nama": "Mahasiswa",
        "role": (
            "Kamu mahasiswa aktivis yang kritis terhadap kebijakan pemerintah. "
            "Kamu peduli pada keadilan sosial, transparansi, dan hak-hak rakyat kecil."
        ),
        "kepribadian": {"openness": 0.9, "agreeableness": 0.4, "neuroticism": 0.6},
        "pengaruh": 0.7,
        "memori": [],
    },
    "Pengusaha": {
        "nama": "Pengusaha/UMKM",
        "role": (
            "Kamu pengusaha UMKM yang fokus pada untung-rugi, keberlanjutan usaha, "
            "dan dampak kebijakan terhadap bisnis dan lapangan kerja."
        ),
        "kepribadian": {"openness": 0.5, "agreeableness": 0.6, "neuroticism": 0.3},
        "pengaruh": 0.8,
        "memori": [],
    },
    "Pekerja": {
        "nama": "Pekerja Kantoran",
        "role": (
            "Kamu pekerja kantoran yang pragmatis. "
            "Prioritasmu adalah efisiensi waktu, stabilitas karir, dan keseimbangan hidup-kerja."
        ),
        "kepribadian": {"openness": 0.4, "agreeableness": 0.7, "neuroticism": 0.5},
        "pengaruh": 0.6,
        "memori": [],
    },
    "Pemerintah": {
        "nama": "Pemerintah",
        "role": (
            "Kamu pejabat pemerintah yang bertugas menjelaskan kebijakan resmi, "
            "regulasi, dan undang-undang. Kamu selalu merujuk pada dasar hukum yang berlaku."
        ),
        "kepribadian": {"openness": 0.3, "agreeableness": 0.5, "neuroticism": 0.2},
        "pengaruh": 0.9,
        "memori": [],
    },
    "Akademisi": {
        "nama": "Akademisi",
        "role": (
            "Kamu dosen dan peneliti yang menganalisis isu berdasarkan data empiris, "
            "teori ilmiah, dan studi komparatif dari berbagai negara."
        ),
        "kepribadian": {"openness": 0.95, "agreeableness": 0.6, "neuroticism": 0.3},
        "pengaruh": 0.75,
        "memori": [],
    },
    "Media": {
        "nama": "Jurnalis/Media",
        "role": (
            "Kamu jurnalis independen yang bertugas melaporkan fakta secara berimbang, "
            "mengungkap narasi tersembunyi, dan mempertanyakan klaim semua pihak."
        ),
        "kepribadian": {"openness": 0.8, "agreeableness": 0.45, "neuroticism": 0.5},
        "pengaruh": 0.85,
        "memori": [],
    },
    "Masyarakat": {
        "nama": "Masyarakat Umum",
        "role": (
            "Kamu warga biasa yang mewakili suara rakyat kebanyakan: "
            "sederhana, langsung, dan sangat dipengaruhi oleh kondisi ekonomi sehari-hari."
        ),
        "kepribadian": {"openness": 0.4, "agreeableness": 0.75, "neuroticism": 0.6},
        "pengaruh": 0.65,
        "memori": [],
    },
}

# Mapping kategori ke subset agen yang relevan
KATEGORI_MAP = {
    "Ekonomi":   ["Pengusaha", "Pekerja", "Pemerintah", "Akademisi", "Masyarakat"],
    "Politik":   ["Mahasiswa", "Pemerintah", "Media", "Akademisi", "Masyarakat"],
    "Sosial":    ["Mahasiswa", "Masyarakat", "Media", "Akademisi", "Pekerja"],
    "Hukum":     ["Pemerintah", "Akademisi", "Media", "Mahasiswa", "Pekerja"],
    "Teknologi": ["Akademisi", "Pengusaha", "Pekerja", "Mahasiswa", "Media"],
    "Umum":      ["Mahasiswa", "Pengusaha", "Pekerja", "Pemerintah", "Akademisi", "Media"],
}


def get_agents(kategori: str = "Umum", agen_custom: list[dict] | None = None) -> list[dict]:
    """
    Kembalikan daftar agen berdasarkan kategori.
    Setiap agen mendapat salinan fresh (memori dikosongkan) untuk setiap sesi simulasi.

    Args:
        kategori: Nama kategori dari KATEGORI_MAP.
        agen_custom: Daftar agen tambahan yang dikirim dari frontend.
                     Format: [{ "nama": str, "role": str, "pengaruh": float, "kepribadian": dict }]
    """
    kunci_agen = KATEGORI_MAP.get(kategori, KATEGORI_MAP["Umum"])
    hasil = []

    # Agen bawaan dari registry
    for kunci in kunci_agen:
        if kunci in AGENT_REGISTRY:
            agen = dict(AGENT_REGISTRY[kunci])
            agen["memori"] = []
            hasil.append(agen)

    # Tambahkan agen custom dari frontend (jika ada)
    if agen_custom:
        for ac in agen_custom:
            nama = (ac.get("nama") or "").strip()
            role = (ac.get("role") or "").strip()
            if not nama or not role:
                continue   # skip entri tidak valid

            # Pastikan nama unik agar tidak bentrok dengan agen bawaan
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