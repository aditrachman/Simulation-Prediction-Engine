#!/usr/bin/env python3
"""Run C1d: 10 persona BGN, topik BGN, 1 ronde, 3 detik jeda.
Tulis ke backend/data/evals/hasil_c1d.txt.
"""
from __future__ import annotations
import json
import time
import sys
from unittest.mock import patch
sys.path.insert(0, "/home/aditrachman/Documents/Learning-project/voxswarm")

from backend.agents import AGENT_REGISTRY
from backend.simulation import run_simulation

TOPIK = "Apakah keputusan BGN mengeluarkan biaya kendaraan distribusi dari biaya operasional Rp3.000 per penerima manfaat sudah tepat?"

JUDUL_BGN = [
    "BGN: Kendaraan Distribusi MBG Tak Masuk Biaya Operasional Rp3.000",
    "Alasan Kendaraan Dicoret dari Biaya Operasional MBG",
    "Biaya Operasional MBG Rp3.000, Mobil SPPG Tak Lagi Ditanggung",
    "Aturan Baru Biaya Operasional MBG, BGN Ungkap Nasib Gaji Pengawas Gizi dan Keuangan",
    "Aturan Baru MBG, Kendaraan Distribusi Tak Lagi Ditanggung Operasional Dapur, Insentif Harian Juga Dipangkas",
    "BGN Hapus Biaya Kendaraan MBG, Mitra SPPG Kini Wajib Siapkan Armada Sendiri",
    "BGN Hapus Biaya Distribusi MBG Rp3.000 Per Penerima: Kami Kembalikan Kebijakan Semestinya",
    "BGN sebut Kendaraan Distribusi MBG Tak Masuk Biaya Operasional Rp3.000: Karena Wajib Dipenuhi SPPG",
]

# Siapkan berita dari fixture
BERITA = [{"judul": j, "sumber": "Fixture", "link": "https://example.com", "tanggal_iso": "2026-11-08T01:00:00+00:00"} for j in JUDUL_BGN]

PERSONA_NAMA = [
    "Pemerintah", "Akademisi", "Pengusaha/UMKM", "Ibu Hamil/Menyusui",
    "Pekerja Kantoran", "Masyarakat Umum", "Dokter/Nakes", 
    "Pemilik Toko Kecil/Pasar Tradisional", "Skeptis Ekonomi", "Penyedia Logistik Pangan"
]

def build_agents():
    agen = []
    for nama in PERSONA_NAMA:
        if nama in AGENT_REGISTRY:
            a = dict(AGENT_REGISTRY[nama])
            a["memori"] = []
            agen.append(a)
        else:
            # Fallback untuk role khusus
            agen.append({
                "nama": nama, "role": "Persona", "pengaruh": 0.5, "memori": [], "initial_stance": 0.0, "kepribadian": {"openness": 0.5, "agreeableness": 0.5, "neuroticism": 0.5}
            })
    return agen

def run_debat(agents, label):
    return run_simulation(topik=TOPIK, agents=agents, jumlah_ronde=1, tier="free", konteks_real={"berita": BERITA, "sumber_status": "ok"})

def format_jawaban(hasil):
    lines = []
    fakta = hasil["briefing_dipakai"]["fakta_terkini"]
    lines.append("=== FAKTA TERKINI ===")
    lines.append(fakta["teks"])
    for k in fakta["klaim"]:
        lines.append(f"  [{k['nomor']}] ({k.get('asal', 'llm')}) {k['klaim']}")
    lines.append("\n=== JAWABAN ===")
    jawaban = hasil["ronde_detail"][0]["agen"]
    for a in jawaban:
        s = a.get("sentimen") or {}
        lines.append(f"--- {a['nama']} | {s.get('label', '-')} {s.get('skor', '-')} ---")
        lines.append(a.get("pendapat", ""))
    return "\n".join(lines)

def main():
    agen_semua = build_agents()
    hasil1 = run_debat(agen_semua, "DEBAT_UTAMA")
    
    # 3 persona terdampak
    target_nama = ["Penyedia Logistik Pangan", "Pengusaha/UMKM", "Pemilik Toko Kecil/Pasar Tradisional"]
    agen_terdampak = [a for a in agen_semua if a["nama"] in target_nama]
    
    hasil2 = run_debat(agen_terdampak, "TERDAMPAK_1")
    hasil3 = run_debat(agen_terdampak, "TERDAMPAK_2")
    
    # Simpan hasil ke file teks
    out = open("backend/data/evals/hasil_c1d.txt", "w")
    out.write("DEBAT 10 PERSONA (1 RONDE)\n" + format_jawaban(hasil1) + "\n\n")
    out.write("ULANGAN PERSONA TERDAMPAK (2x)\n")
    out.write(format_jawaban(hasil2) + "\n\n" + format_jawaban(hasil3))
    out.close()
    print("Selesai. Cek backend/data/evals/hasil_c1d.txt")

if __name__ == "__main__":
    main()
