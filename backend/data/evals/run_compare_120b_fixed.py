#!/usr/bin/env python3
"""
Fair comparison: 120b with same 10 personas, SAME context, SAME FAKTA as 20b run.
"""
from __future__ import annotations

import json
import time
import sys

sys.path.insert(0, "/home/aditrachman/Documents/Learning-project/voxswarm")

from backend.simulation import run_simulation

# Force 120b
import backend.llm as llm_module
ORIGINAL_MODEL = llm_module.MODEL_AGENT
llm_module.MODEL_AGENT = "openai/gpt-oss-120b"

TOPIK = (
    "Apakah keputusan BGN mengeluarkan biaya kendaraan distribusi dari biaya "
    "operasional Rp3.000 per penerima manfaat sudah tepat?"
)

# Load berita from cache
with open("backend/data/evals/konteks_bgn.json") as f:
    KONTEKS = json.load(f)

BERITA = KONTEKS["berita"]

# SAME FAKTA as 20b run (from hasil_c1.txt)
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

from backend.agents import AGENT_REGISTRY

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

# Patch the FAKTA building to return our fixed FAKTA
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

print(f"Running 10 personas with 120b (fixed FAKTA)...")
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

# Restore
sim_mod._bangun_fakta_terkini = original_bangun
llm_module.MODEL_AGENT = ORIGINAL_MODEL

fakta = hasil["briefing_dipakai"]["fakta_terkini"]
jawaban = hasil["ronde_detail"][0]["agen"]

output = []
output.append("=" * 60)
output.append("EVALUASI 120b - SAME 10 PERSONA, SAME FAKTA AS 20b")
output.append("=" * 60)
output.append(f"Topik: {TOPIK}")
output.append(f"Model: openai/gpt-oss-120b")
output.append(f"Durasi: {durasi:.1f}s")
output.append("")
output.append("=== BLOK FAKTA TERKINI (IDENTICAL TO 20b) ===")
output.append(fakta["teks"])
for k in fakta["klaim"]:
    output.append(f"[{k['nomor']}] ({len(k['klaim'].split())} kata) {k['klaim']}")
output.append("")
output.append(f"=== JAWABAN RONDE 1 ({len(jawaban)} persona) ===")
for a in jawaban:
    s = a.get("sentimen") or {}
    output.append("")
    output.append(f"--- {a['nama']} | model gpt-oss-120b | {s.get('label', '-')} {s.get('skor', '-')} | status {a.get('status', 'ok')}")
    output.append(a.get("pendapat", ""))
    output.append(f"6 kata pertama: {' '.join((a.get('pendapat') or '').split()[:6])}")

# Analysis
KATA_SUDUT_LAIN = ("mitra", "armada", "insentif", "gaji", "pengawas", "kembalikan", "syarat", "penundaan", "kritik")
def empat_awal(teks):
    return " ".join(teks.split()[:4]).lower()

kata_klaim = []
for k in fakta["klaim"]:
    kata_klaim.append({
        w for w in k["klaim"].lower().split()
        if len(w) > 4 and w not in {"kendaraan", "distribusi", "operasional", "biaya", "tidak", "dalam", "per", "anggaran", "rp3", "rp3000", "komponen", "mencakup", "sppg", "mobil"}
    })

dirujuk = set()
for a in jawaban:
    teks = (a.get("pendapat") or "").lower()
    for i, kata in enumerate(kata_klaim):
        if kata and any(w in teks for w in kata):
            dirujuk.add(i + 1)

sudut_lain = []
for a in jawaban:
    if any(w in (a.get("pendapat") or "").lower() for w in KATA_SUDUT_LAIN):
        sudut_lain.append(a["nama"])

awal_bgn = []
for a in jawaban:
    p = (a.get("pendapat") or "").strip()
    if p.startswith("BGN") or p.startswith("Badan Gizi"):
        awal_bgn.append(a["nama"])

alasan_luar = []
for a in jawaban:
    teks = (a.get("pendapat") or "").lower()
    if any(w in teks for w in ["lebih efisien", "transparan", "efektif", "efisiensi", "lebih hemat", "lebih fokus", "lebih jelas", "lebih tepat"]):
        ada_di_fakta = any(w in t for t in [k["klaim"].lower() for k in fakta["klaim"]] for w in ["efisien", "transparan", "hemat", "fokus", "jelas", "tepat"])
        if not ada_di_fakta:
            alasan_luar.append(a["nama"])

salah_angka = []
for a in jawaban:
    teks = (a.get("pendapat") or "").lower()
    if "biaya kendaraan jadi" in teks or "kendaraan jadi 3.000" in teks or "kendaraan jadi rp3.000" in teks or "biaya kendaraan turun" in teks:
        salah_angka.append((a["nama"], teks[:120]))

peta = {}
for a in jawaban:
    peta.setdefault(empat_awal(a.get("pendapat", "")), []).append(a["nama"])
identik = {k: v for k, v in peta.items() if len(v) > 1}

output.append("")
output.append("=== HITUNGAN 120b (FIXED FAKTA) ===")
output.append(f"(i) Klaim berbeda yang dirujuk: {len(dirujuk)} dari {len(fakta['klaim'])} -> {sorted(dirujuk)}")
output.append(f"(ii) Jawaban memuat kata sudut selain klaim 1: {len(sudut_lain)} -> {sudut_lain}")
output.append(f"(iii) Jawaban diawali 'BGN' atau nama lembaga: {len(awal_bgn)} -> {awal_bgn}")
output.append(f"(iv) Jawaban menyatakan alasan di luar FAKTA: {len(alasan_luar)} -> {alasan_luar}")
output.append(f"(v) Jawaban salah tafsir angka: {len(salah_angka)}")
for nama, teks in salah_angka:
    output.append(f"    {nama}: {teks}")
output.append(f"(vi) Jawaban dengan 4 kata awal identik: {sum(len(v) for v in identik.values())} -> {identik}")

result = "\n".join(output)
print(result)

with open("backend/data/evals/hasil_compare_120b_fixed.txt", "w") as f:
    f.write(result)