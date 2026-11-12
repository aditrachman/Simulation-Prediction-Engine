#!/usr/bin/env python3
"""
Evaluasi C1: Run live 10 persona BGN, ronde 1, jeda 3 detik.
Simpan bukti ke backend/data/evals/hasil_c1.json dan tampilkan.
"""
from __future__ import annotations

import json
import time
import sys

sys.path.insert(0, "/home/aditrachman/Documents/Learning-project/voxswarm")

from backend.agents import AGENT_REGISTRY
from backend.simulation import run_simulation


TOPIK = (
    "Apakah keputusan BGN mengeluarkan biaya kendaraan distribusi dari biaya "
    "operasional Rp3.000 per penerima manfaat sudah tepat?"
)

# Load berita from cache
with open("backend/data/evals/konteks_bgn.json") as f:
    KONTEKS = json.load(f)

BERITA = KONTEKS["berita"]

# Role untuk 5 persona non-registry (ditulis manual di skrip)
ROLE_KHUSUS = {
    "Ibu Hamil/Menyusui": (
        "Kamu ibu hamil yang bergantung pada bantuan pangan dan layanan posyandu. "
        "Bicara sederhana, fokus pada apakah makanan bergizi tetap sampai ke anak."
    ),
    "Dokter/Nakes": (
        "Kamu dokter yang memantau gizi ibu dan anak di puskesmas. "
        "Fokus pada mutu makanan dan layanan kesehatan yang bisa terdampak."
    ),
    "Pemilik Toko Kecil/Pasar Tradisional": (
        "Kamu pemilik warung dan pedagang pasar tradisional. "
        "Fokus pada omzet, harga bahan, dan dampak biaya operasional ke dagangan."
    ),
    "Skeptis Ekonomi": (
        "Kamu ekonom skeptis yang menguji klaim anggaran fiskal dengan data. "
        "Fokus pada pembebanan biaya, insentif, dan transparansi anggaran."
    ),
    "Penyedia Logistik Pangan": (
        "Kamu penyedia jasa logistik dan armada pengiriman pangan. "
        "Fokus pada kendaraan, biaya angkut, dan siapa yang menanggung operasional."
    ),
}

NAMA_PERSONA = [
    "Pemerintah",
    "Akademisi",
    "Pengusaha/UMKM",
    "Ibu Hamil/Menyusui",
    "Pekerja Kantoran",
    "Masyarakat Umum",
    "Dokter/Nakes",
    "Pemilik Toko Kecil/Pasar Tradisional",
    "Skeptis Ekonomi",
    "Penyedia Logistik Pangan",
]

# Build agent list
AGEN = []
for nama in NAMA_PERSONA:
    kandidat = [v for v in AGENT_REGISTRY.values() if v["nama"] == nama]
    if kandidat:
        dasar = dict(kandidat[0])
        dasar.setdefault("memori", [])
        AGEN.append(dasar)
    else:
        AGEN.append({
            "nama": nama,
            "role": ROLE_KHUSUS[nama],
            "kepribadian": {"openness": 0.5, "agreeableness": 0.5, "neuroticism": 0.5},
            "pengaruh": 0.6,
            "memori": [],
            "initial_stance": 0.0,
        })

print(f"Running simulation with {len(AGEN)} agents...")
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

# Extract FAKTA TERKINI block
fakta = hasil["briefing_dipakai"]["fakta_terkini"]
klaim = fakta["klaim"]
jawaban = hasil["ronde_detail"][0]["agen"]

# Model info
model_info = hasil.get("model_info", {})
model_agen = model_info.get("agen", "unknown")

# Analisis per jawaban
KATA_SUDUT_LAIN = ("mitra", "armada", "insentif", "gaji", "pengawas", "kembalikan", "syarat", "penundaan", "kritik")

def empat_awal(teks):
    return " ".join(teks.split()[:4]).lower()

# (i) klaim berbeda yang dirujuk
kata_klaim = []
for k in klaim:
    kata_klaim.append({
        w for w in k["klaim"].lower().split()
        if len(w) > 4 and w not in {"kendaraan", "distribusi", "operasional", "biaya", "tidak", "dalam", "per", "anggaran", "rp3", "rp3000"}
    })

dirujuk = set()
for a in jawaban:
    teks = (a.get("pendapat") or "").lower()
    for i, kata in enumerate(kata_klaim):
        if kata and any(w in teks for w in kata):
            dirujuk.add(i + 1)

# (ii) jawaban dengan kata sudut selain klaim 1
sudut_lain = []
for a in jawaban:
    if any(w in (a.get("pendapat") or "").lower() for w in KATA_SUDUT_LAIN):
        sudut_lain.append(a["nama"])

# (iii) jawaban diawali "BGN" atau nama lembaga
awal_bgn = []
for a in jawaban:
    p = (a.get("pendapat") or "").strip()
    if p.startswith("BGN") or p.startswith("Badan Gizi"):
        awal_bgn.append(a["nama"])

# (iv) jawaban menyatakan alasan di luar FAKTA ("lebih efisien", "transparan", dll)
alasan_luar = []
for a in jawaban:
    teks = (a.get("pendapat") or "").lower()
    if any(w in teks for w in ["lebih efisien", "transparan", "efisien", "efektif"]):
        # Cek apakah kata itu ada di FAKTA
        ada_di_fakta = any(w in t for t in [k["klaim"].lower() for k in klaim] for w in ["efisien", "transparan"])
        if not ada_di_fakta:
            alasan_luar.append(a["nama"])

# (v) jawaban salah tafsir angka
salah_angka = []
for a in jawaban:
    teks = (a.get("pendapat") or "").lower()
    if "biaya kendaraan jadi" in teks or "biaya kendaraan turun" in teks or "kendaraan jadi 3.000" in teks or "kendaraan jadi rp3.000" in teks:
        salah_angka.append((a["nama"], teks[:120]))

# (vi) 4 kata awal identik
peta = {}
for a in jawaban:
    peta.setdefault(empat_awal(a.get("pendapat", "")), []).append(a["nama"])
identik = {k: v for k, v in peta.items() if len(v) > 1}

# Build output
output_lines = []
output_lines.append("=" * 60)
output_lines.append("EVALUASI C1 - RUN BGN 10 PERSONA")
output_lines.append("=" * 60)
output_lines.append(f"Topik: {TOPIK}")
output_lines.append(f"Model: {model_agen}")
output_lines.append(f"Durasi: {durasi:.1f}s")
output_lines.append("")
output_lines.append("=== BLOK FAKTA TERKINI YANG MASUK PROMPT ===")
output_lines.append(fakta["teks"])
output_lines.append("")
output_lines.append(f"Jumlah klaim: {len(klaim)}")
for k in klaim:
    output_lines.append(f"[{k['nomor']}] ({len(k['klaim'].split())} kata) {k['klaim']}")
output_lines.append("")
output_lines.append(f"=== JAWABAN RONDE 1 ({len(jawaban)} persona) ===")
for a in jawaban:
    s = a.get("sentimen") or {}
    output_lines.append("")
    output_lines.append(f"--- {a['nama']} | model {model_agen} | {s.get('label', '-')} {s.get('skor', '-')} | status {a.get('status', 'ok')}")
    output_lines.append(a.get("pendapat", ""))
    output_lines.append(f"6 kata pertama: {' '.join((a.get('pendapat') or '').split()[:6])}")

output_lines.append("")
output_lines.append("=== HITUNGAN ===")
output_lines.append(f"(i) Klaim berbeda yang dirujuk: {len(dirujuk)} dari {len(klaim)} -> {sorted(dirujuk)}")
output_lines.append(f"(ii) Jawaban memuat kata sudut selain klaim 1: {len(sudut_lain)} -> {sudut_lain}")
output_lines.append(f"(iii) Jawaban diawali 'BGN' atau nama lembaga: {len(awal_bgn)} -> {awal_bgn}")
output_lines.append(f"(iv) Jawaban menyatakan alasan di luar FAKTA: {len(alasan_luar)} -> {alasan_luar}")
output_lines.append(f"(v) Jawaban salah tafsir angka: {len(salah_angka)}")
for nama, teks in salah_angka:
    output_lines.append(f"    {nama}: {teks}")
output_lines.append(f"(vi) Jawaban dengan 4 kata awal identik: {sum(len(v) for v in identik.values())} -> {identik}")

# Agent roles
output_lines.append("")
output_lines.append("=== AGENT_ROLES (metadata) ===")
roles = hasil.get("agent_roles", {})
for nama, info in roles.items():
    output_lines.append(f"  {nama}: sumber={info.get('sumber')}, voice_anchor={info.get('voice_anchor')}")

# Save to file
output_text = "\n".join(output_lines)
with open("backend/data/evals/hasil_c1.txt", "w") as f:
    f.write(output_text)

# Also save JSON for programmatic access
with open("backend/data/evals/hasil_c1.json", "w") as f:
    json.dump({
        "topik": TOPIK,
        "model": model_agen,
        "durasi": durasi,
        "fakta_terkini": fakta["teks"],
        "klaim": klaim,
        "jawaban": [
            {
                "nama": a["nama"],
                "model": model_agen,
                "sentimen": a.get("sentimen"),
                "status": a.get("status"),
                "pendapat": a.get("pendapat"),
                "kata_awal": " ".join((a.get("pendapat") or "").split()[:6]),
            }
            for a in jawaban
        ],
        "hitungan": {
            "klaim_dirujuk": len(dirujuk),
            "klaim_dirujuk_detail": sorted(dirujuk),
            "sudut_lain": len(sudut_lain),
            "sudut_lain_detail": sudut_lain,
            "awal_bgn": len(awal_bgn),
            "awal_bgn_detail": awal_bgn,
            "alasan_luar_fakta": len(alasan_luar),
            "alasan_luar_fakta_detail": alasan_luar,
            "salah_angka": len(salah_angka),
            "salah_angka_detail": [{"nama": n, "teks": t} for n, t in salah_angka],
            "empat_kata_identik": identik,
        },
        "agent_roles": hasil.get("agent_roles", {}),
    }, f, ensure_ascii=False, indent=2)

print(output_text)