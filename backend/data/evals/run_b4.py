#!/usr/bin/env python3
"""B4: uji stabilitas pembentukan FAKTA TERKINI (tanpa persona).

5x dari 8 judul fixture BGN + 5x dari input evaluasi konteks_bgn.json.
Hanya memanggil pipeline FAKTA, jeda 3 detik antar panggilan LLM.
Tiap jawaban langsung ditulis ke backend/data/evals/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path("/home/aditrachman/Documents/Learning-project/voxswarm")
sys.path.insert(0, str(ROOT))

from backend.simulation import (
    _pilih_judul_fakta,
    _susun_fakta_terkini_rewrite,
)

TOPIK = (
    "Apakah keputusan BGN mengeluarkan biaya kendaraan distribusi dari biaya "
    "operasional Rp3.000 per penerima manfaat sudah tepat?"
)

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

with open(ROOT / "backend/data/evals/konteks_bgn.json") as f:
    KONTEKS = json.load(f)

JUDUL_EVAL = [b["judul"] for b in KONTEKS.get("berita", []) if b.get("judul")]

OUT_JSON = ROOT / "backend/data/evals/hasil_b4.json"
OUT_TXT = ROOT / "backend/data/evals/hasil_b4.txt"

FRASA_META = (
    "berita seputar", "terbaru dan terkini", "kumpulan berita",
    "update terbaru", "hari ini", "indeks berita",
)
KATA_ARMADA_MITRA = ("armada", "mitra")


def _hitungan(klaim: list[dict]) -> dict:
    gabung = " ".join(k["klaim"] for k in klaim).lower()
    return {
        "armada_atau_mitra": any(w in gabung for w in KATA_ARMADA_MITRA),
        "insentif": "insentif" in gabung,
        "pengawas": "pengawas" in gabung,
        "klaim_meta": any(f in gabung for f in FRASA_META),
    }


def _tulis(hasil: dict) -> None:
    OUT_JSON.write_text(json.dumps(hasil, ensure_ascii=False, indent=2))
    baris = [
        "B4 - STABILITAS PEMBENTUKAN FAKTA TERKINI",
        f"Topik: {TOPIK}",
        f"Judul fixture BGN: {len(JUDUL_BGN)} | judul input evaluasi: {len(JUDUL_EVAL)}",
        "",
    ]
    for sumber in ("fixture_bgn", "input_evaluasi"):
        blok = hasil.get(sumber)
        if not blok:
            continue
        baris.append(f"=== {sumber} ===")
        baris.append(f"Judul terpilih: {len(blok['judul_terpilih'])}")
        for i, j in enumerate(blok["judul_terpilih"], 1):
            baris.append(f"  [{i}] {j}")
        baris.append("")
        for run in blok["runs"]:
            h = run["hitungan"]
            baris.append(f"--- run {run['run']} | asal {run['asal']} | hitungan {h}")
            for k in run["klaim"]:
                baris.append(
                    f"  [{k['nomor']}] ({k['asal']}) {k['klaim']}"
                )
            baris.append("")
        baris.append(f"Ringkasan: {blok['ringkasan']}")
        baris.append("")
    OUT_TXT.write_text("\n".join(baris))


def jalankan(label: str, judul: list[str]) -> dict:
    terpilih = _pilih_judul_fakta(judul, TOPIK, 5)
    runs: list[dict] = []
    for i in range(1, 6):
        klaim = _susun_fakta_terkini_rewrite(terpilih, TOPIK, 5)
        if klaim is None:
            klaim = [
                {"nomor": j + 1, "klaim": t, "sumber_idx": j}
                for j, t in enumerate(terpilih)
            ]
            asal = "fallback_judul"
        else:
            asal = "llm"
        for k in klaim:
            sumber = terpilih[k["sumber_idx"]] if k["sumber_idx"] < len(terpilih) else ""
            k["asal"] = "judul" if k["klaim"].strip() == sumber.strip() else "llm"
        runs.append({"run": i, "asal": asal, "klaim": klaim, "hitungan": _hitungan(klaim)})
        print(f"[{label}] run {i}: {len(klaim)} klaim, asal {asal}", flush=True)
        time.sleep(3)

    return {
        "judul_terpilih": terpilih,
        "runs": runs,
        "ringkasan": {
            "run_llm": sum(1 for r in runs if r["asal"] == "llm"),
            "run_fallback": sum(1 for r in runs if r["asal"] != "llm"),
            "klaim_total": sum(len(r["klaim"]) for r in runs),
            "klaim_asal_llm": sum(
                1 for r in runs for k in r["klaim"] if k["asal"] == "llm"
            ),
            "klaim_asal_judul": sum(
                1 for r in runs for k in r["klaim"] if k["asal"] == "judul"
            ),
            "set_armada_mitra": sum(1 for r in runs if r["hitungan"]["armada_atau_mitra"]),
            "set_insentif": sum(1 for r in runs if r["hitungan"]["insentif"]),
            "set_pengawas": sum(1 for r in runs if r["hitungan"]["pengawas"]),
            "set_klaim_meta": sum(1 for r in runs if r["hitungan"]["klaim_meta"]),
        },
    }


def main() -> None:
    hasil: dict = {"topik": TOPIK}
    hasil["fixture_bgn"] = jalankan("fixture_bgn", JUDUL_BGN)
    _tulis(hasil)
    hasil["input_evaluasi"] = jalankan("input_evaluasi", JUDUL_EVAL)
    _tulis(hasil)
    print(OUT_TXT.read_text(), flush=True)


if __name__ == "__main__":
    main()
