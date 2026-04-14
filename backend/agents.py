# backend/agents.py

def get_agents(kategori="Umum"):
    # Daftar agen universal agar fleksibel untuk isu apa pun [cite: 176, 205]
    agents = [
    {"nama": "Mahasiswa Idealistis", "role": "Kritis tapi masih penuh harapan, sering bawa teori dan moralitas."},
    {"nama": "Pengusaha/UMKM", "role": "Fokus pada untung rugi, keberlanjutan usaha, dan dampak kebijakan ke bisnis."},
    {"nama": "Pekerja Kantoran", "role": "Pragmatis, mikir efisiensi waktu, karir, dan stabilitas hidup."},
    {"nama": "Influencer/Sosial Media", "role": "Fokus pada engagement, opini publik, dan framing narasi."},
    ]
    return agents