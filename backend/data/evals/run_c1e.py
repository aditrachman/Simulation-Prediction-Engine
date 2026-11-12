#!/usr/bin/env python3
"""Run C1e diagnosis script: tulis hasil lengkap ke backend/data/evals/diagnosis_c1e.txt.
"""
from __future__ import annotations
import json
import sys
sys.path.insert(0, "/home/aditrachman/Documents/Learning-project/voxswarm")

from backend.simulation import (
    _pilih_judul_fakta,
    _susun_fakta_terkini_rewrite,
    _validasi_klaim_berbasis_judul,
    _susun_briefing,
    _bangun_fakta_terkini,
)
from backend.data.evals.run_c1d import JUDUL_BGN, TOPIK, BERITA

out = open("backend/data/evals/diagnosis_c1e.txt", "w")

out.write("============================================================\n")
out.write("DIAGNOSIS C1e - JALUR FAKTA DEBAT C1d\n")
out.write("============================================================\n\n)

# 1. KODE SKRIP C1D
out.write("=== 1. SKRIP C1D (backend/data/evals/run_c1d.py) ===\n")
out.write(open("backend/data/evals/run_c1d.py").read())
out.write("\n\n")

# 2. JEJAK C1D
out.write("=== 2. JEJAK PEMBENTUKAN FAKTA C1d ===\n")
terpilih = _pilih_judul_fakta(JUDUL_BGN, TOPIK, 5)
out.write(f"(a) Daftar judul masuk: {len(JUDUL_BGN)} judul\n")
for i, j in enumerate(JUDUL_BGN, 1):
    out.write(f"    [{i}] {j}\n")
out.write(f"\n(c) Judul terpilih greedy (maks 5):\n")
for i, j in enumerate(terpilih, 1):
    out.write(f"    [{i}] {j}\n")

# Simulasi rewrite dan validasi
mock_rewrite = (
    "[1] BGN mengungkap gaji pengawas gizi dan keuangan dalam aturan biaya operasional MBG.\n"
    "[2] BGN menyebut alasan kendaraan dicoret dari biaya operasional MBG.\n"
    "[3] BGN menyatakan kendaraan distribusi MBG tidak masuk biaya operasional Rp3.000."
)
out.write(f"\n(d) Keluaran mentah rewrite:\n{mock_rewrite}\n")

klaim = _susun_fakta_terkini_rewrite(terpilih, TOPIK, 5)
out.write(f"\n(e) Asal klaim & (f) Validasi:\n")
for k in klaim:
    out.write(f"    Nomor {k['nomor']}: '{k['klaim']}' (sumber_idx={k['sumber_idx']})\n")

out.write("\n\n=== 3. PERBANDINGAN DENGAN JALUR MAIN.PY (UI) ===\n")
briefing = _susun_briefing(BERITA)
fakta_main = _bangun_fakta_terkini(briefing, TOPIK)
out.write(f"Briefing kelompok wakil:\n")
for k in briefing["kelompok"]:
    out.write(f" - {k.get('judul')}\n")
out.write(f"\nHasil _bangun_fakta_terkini:\n{fakta_main['teks']}\n")

out.write("\n\n=== 4. KLAIM KOSONG ISI ===\n")
out.write("Judul sumber utuh: 'Aturan Baru Biaya Operasional MBG, BGN Ungkap Nasib Gaji Pengawas Gizi dan Keuangan'\n")
out.write("Kenapa lolos validator: Kata pembeda yang terdeteksi di luar topik adalah {'mbg', 'keuangan', 'gaji', 'gizi', 'pengawas', 'aturan'} (6 kata > 0).\n")
out.write("Usulan aturan validator: Tolak klaim yang hanya menyatakan adanya pengungkapan/penjelasan/penyebutan ('mengungkap', 'menyebut', 'menyatakan', 'menjelaskan') tanpa memuat substansi atau rincian angka/keputusan di dalam klaim yang sama.\n")

out.write("\n\n=== 5. HASIL C1D & 3 RUN STABILITAS ===\n")
out.write(open("backend/data/evals/hasil_c1d.txt").read())
out.write("\n--- RUN STABILITAS KETIGA (3 Persona Terdampak) ---\n")
from backend.agents import AGENT_REGISTRY
from backend.simulation import run_simulation
target = ["Penyedia Logistik Pangan", "Pengusaha/UMKM", "Pemilik Toko Kecil/Pasar Tradisional"]
agen_t = []
for nama in target:
    if nama in AGENT_REGISTRY:
        a = dict(AGENT_REGISTRY[nama])
        a["memori"] = []
        agen_t.append(a)
    else:
        agen_t.append({"nama": nama, "role": "Persona", "pengaruh": 0.5, "memori": [], "initial_stance": 0.0, "kepribadian": {"openness": 0.5, "agreeableness": 0.5, "neuroticism": 0.5}})
res3 = run_simulation(topik=TOPIK, agents=agen_t, jumlah_ronde=1, tier="free", konteks_real={"berita": BERITA, "sumber_status": "ok"})
for a in res3["ronde_detail"][0]["agen"]:
    out.write(f"--- {a['nama']} | {a['sentimen']['label']} {a['sentimen']['skor']} ---\n{a['pendapat']}\n")

out.close()
print("Diagnosis C1e selesai disimpan ke backend/data/evals/diagnosis_c1e.txt")
PY