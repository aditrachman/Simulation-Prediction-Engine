#!/usr/bin/env python3
"""
Stability check: 3 personas x 2 models x 2 runs each.
"""
from __future__ import annotations

import json
import time
import sys

sys.path.insert(0, "/home/aditrachman/Documents/Learning-project/voxswarm")

from backend.simulation import run_simulation

TOPIK = (
    "Apakah keputusan BGN mengeluarkan biaya kendaraan distribusi dari biaya "
    "operasional Rp3.000 per penerima manfaat sudah tepat?"
)

with open("backend/data/evals/konteks_bgn.json") as f:
    KONTEKS = json.load(f)
BERITA = KONTEKS["berita"]

FAKTA_TERCANTUM = """FAKTA TERKINI:
[1] BGN menegaskan kendaraan distribusi bukan komponen biaya operasional MBG.
[2] Mobil SPPG tidak lagi ditanggung di anggaran operasional MBG.
[3] Rp3.000 per penerima manfaat tidak lagi mencakup kendaraan.

Pilih SATU fakta dari daftar dan sebut dengan kata-katamu sendiri, jangan menyalin kalimatnya. Jangan menyebut angka yang tidak ada di daftar."""

FAKTA_KLAIM = [
    {"nomor": 1, "klaim": "BGN menegaskan kendaraan distribusi bukan komponen biaya operasional MBG.", "sumber_nomor": []},
    {"nomor": 2, "klaim": "Mobil SPPG tidak lagi ditanggung di anggaran operasional MBG.", "sumber_nomor": []},
    {"nomor": 3, "klaim": "Rp3.000 per penerima manfaat tidak lagi mencakup kendaraan.", "sumber_nomor": []},
]

PERSONAS = ["Pemerintah", "Akademisi", "Masyarakat Umum"]

ROLE_KHUSUS = {
    "Masyarakat Umum": "Kamu warga biasa yang mewakili suara rakyat: sederhana, langsung, dan sangat dipengaruhi kondisi ekonomi sehari-hari. Bicara apa adanya berdasarkan pengalaman hidup nyata.",
}

from backend.agents import AGENT_REGISTRY

def build_agents():
    agen = []
    for nama in PERSONAS:
        kandidat = [v for v in AGENT_REGISTRY.values() if v["nama"] == nama]
        if kandidat:
            dasar = dict(kandidat[0])
            dasar.setdefault("memori", [])
            agen.append(dasar)
        else:
            agen.append({
                "nama": nama,
                "role": ROLE_KHUSUS[nama],
                "kepribadian": {"openness": 0.5, "agreeableness": 0.5, "neuroticism": 0.5},
                "pengaruh": 0.6,
                "memori": [],
                "initial_stance": 0.0,
            })
    return agen

import backend.simulation as sim_mod
original_bangun = sim_mod._bangun_fakta_terkini

def fixed_bangun(briefing_dipakai, topik):
    return {
        "teks": FAKTA_TERCANTUM,
        "klaim": FAKTA_KLAIM,
        "catatan_istilah": None,
        "briefing_guard": {"regenerasi_angka": 0, "regenerasi_salinan": 0},
    }

sim_mod._bangun_fakta_terkini = fixed_bangun

import backend.llm as llm_module

results = {}

for model_name in ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
    llm_module.MODEL_AGENT = model_name
    model_results = []
    
    for run in [1, 2]:
        agen = build_agents()
        print(f"Run {run} with {model_name}...")
        mulai = time.time()
        hasil = run_simulation(
            topik=TOPIK,
            agents=agen,
            jumlah_ronde=1,
            tier="free",
            konteks_real={"berita": BERITA, "sumber_status": "ok"},
        )
        durasi = time.time() - mulai
        
        for a in hasil["ronde_detail"][0]["agen"]:
            model_results.append({
                "model": model_name,
                "run": run,
                "persona": a["nama"],
                "sentimen": a.get("sentimen", {}),
                "status": a.get("status"),
                "pendapat": a.get("pendapat"),
                "durasi": durasi / len(agen),  # approx per agent
            })
    
    results[model_name] = model_results

# Restore
sim_mod._bangun_fakta_terkini = original_bangun
llm_module.MODEL_AGENT = "openai/gpt-oss-20b"

# Print comparison
output = []
output.append("=" * 60)
output.append("STABILITY CHECK: 3 PERSONAS x 2 MODELS x 2 RUNS")
output.append("=" * 60)

for model in ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
    output.append(f"\n--- {model} ---")
    for run in [1, 2]:
        output.append(f"  Run {run}:")
        for r in results[model]:
            if r["run"] == run:
                s = r["sentimen"]
                output.append(f"    {r['persona']}: {s.get('label')} {s.get('skor'):.2f} | {r['pendapat'][:80]}...")

# Check consistency
output.append("\n=== CONSISTENCY ===")
for model in ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
    run1 = [r for r in results[model] if r["run"] == 1]
    run2 = [r for r in results[model] if r["run"] == 2]
    output.append(f"\n{model}:")
    for r1 in run1:
        r2 = next(r for r in run2 if r["persona"] == r1["persona"])
        s1 = r1["sentimen"].get("label")
        s2 = r2["sentimen"].get("label")
        skor1 = r1["sentimen"].get("skor", 0)
        skor2 = r2["sentimen"].get("skor", 0)
        same = "✓" if s1 == s2 else "✗"
        output.append(f"  {r1['persona']}: {s1}({skor1:.2f}) vs {s2}({skor2:.2f}) {same} | diff={abs(skor1-skor2):.2f}")

result = "\n".join(output)
print(result)

with open("backend/data/evals/hasil_stabilitas.txt", "w") as f:
    f.write(result)