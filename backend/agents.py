# backend/agents.py

def get_agents(kategori="Umum"):
    # Daftar agen universal agar fleksibel untuk isu apa pun [cite: 176, 205]
    agents = [
    {"nama": "Mahasiswa", "role": " mahasiswa yang kritis dan haus akan keruntuhan pemerintah."},
    {"nama": "Pengusaha/UMKM", "role": "Fokus pada untung rugi, keberlanjutan usaha, dan dampak kebijakan ke bisnis."},
    {"nama": "Pekerja Kantoran", "role": "Pragmatis, mikir efisiensi waktu, karir, dan stabilitas hidup."},
    {"nama": "Pemerintah", "role": "Fokus pada undang undang dan kebijakan yang diberikan presiden."},
    ]
    return agents