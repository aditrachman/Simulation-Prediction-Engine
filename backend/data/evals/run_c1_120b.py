#!/usr/bin/env python3
"""
Optional C1 Part 6: Re-run 3 personas with gpt-oss-120b.
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

# Load berita from cache
with open("backend/data/evals/konteks_bgn.json") as f:
    KONTEKS = json.load(f)

BERITA = KONTEKS["berita"]

# 3 personas to test
NAMA_TEST = ["Masyarakat Umum", "Pengusaha/UMKM", "Pemilik Toko Kecil/Pasar Tradisional"]

ROLE_KHUSUS = {
    "Masyarakat Umum": (
        "Kamu warga biasa yang mewakili suara rakyat: sederhana, langsung, dan sangat dipengaruhi kondisi ekonomi sehari-hari. "
        "Bicara apa adanya berdasarkan pengalaman hidup nyata."
    ),
    "Pengusaha/UMKM": (
        "Kamu pengusaha UMKM yang fokus pada untung-rugi dan dampak kebijakan terhadap bisnis dan lapangan kerja. "
        "Berbicara pragmatis, langsung ke angka dan dampak ekonomi nyata."
    ),
    "Pemilik Toko Kecil/Pasar Tradisional": (
        "Kamu pemilik warung dan pedagang pasar tradisional. "
        "Fokus pada omzet, harga bahan, dan dampak biaya operasional ke dagangan."
    ),
}

AGEN = []
for nama in NAMA_TEST:
    AGEN.append({
        "nama": nama,
        "role": ROLE_KHUSUS[nama],
        "kepribadian": {"openness": 0.5, "agreeableness": 0.5, "neuroticism": 0.5},
        "pengaruh": 0.6,
        "memori": [],
        "initial_stance": 0.0,
    })

print(f"Testing {len(AGEN)} agents with gpt-oss-120b...")

# Temporarily override MODEL_AGENT
import backend.llm as llm_module
ORIGINAL_MODEL = llm_module.MODEL_AGENT
llm_module.MODEL_AGENT = "openai/gpt-oss-120b"

try:
    mulai = time.time()
    hasil = run_simulation(
        topik=TOPIK,
        agents=AGEN,
        jumlah_ronde=1,
        tier="free",
        konteks_real={"berita": BERITA, "sumber_status": "ok"},
    )
    durasi = time.time() - mulai
    print(f"Duration: {durasi:.1f}s")

    fakta = hasil["briefing_dipakai"]["fakta_terkini"]
    jawaban = hasil["ronde_detail"][0]["agen"]

    output = []
    output.append(f"=== TEST gpt-oss-120b ({durasi:.1f}s) ===")
    output.append(f"FAKTA: {fakta['teks'][:200]}...")
    output.append("")
    for a in jawaban:
        s = a.get("sentimen") or {}
        output.append(f"--- {a['nama']} | model gpt-oss-120b | {s.get('label', '-')} {s.get('skor', '-')}")
        output.append(a.get("pendapat", ""))
        output.append(f"6 kata pertama: {' '.join((a.get('pendapat') or '').split()[:6])}")
        output.append("")

    # Check for salah tafsir and alasan luar
    for a in jawaban:
        teks = (a.get("pendapat") or "").lower()
        if "biaya kendaraan jadi" in teks or "kendaraan jadi 3.000" in teks:
            output.append(f"⚠️ SALAH TAFSIR: {a['nama']}: {teks[:100]}")
        if any(w in teks for w in ["lebih efisien", "transparan", "efektif"]):
            output.append(f"⚠️ ALASAN LUAR FAKTA: {a['nama']}: {teks[:100]}")

    result = "\n".join(output)
    print(result)

    with open("backend/data/evals/hasil_c1_120b.txt", "w") as f:
        f.write(result)

except Exception as e:
    error_msg = f"ERROR: {type(e).__name__}: {e}"
    print(error_msg)
    with open("backend/data/evals/hasil_c1_120b.txt", "w") as f:
        f.write(error_msg)
finally:
    llm_module.MODEL_AGENT = ORIGINAL_MODEL