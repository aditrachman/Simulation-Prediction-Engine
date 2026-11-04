# backend/services/casestudy_builder.py
# Builder CaseStudy: build_computed(run) -> dict parsial CaseStudy.
# Hanya logika yang DIHITUNG dari run, tanpa LLM.

from __future__ import annotations

from collections import Counter
from typing import Any

STANCE_LABELS = ("menolak", "netral", "mendukung")
STANCE_TO_TIPE = {"menolak": "tolak", "netral": "netral", "mendukung": "dukung"}
TIPE_TO_NAMA_KUBU = {"tolak": "Kritikus", "netral": "Penengah", "dukung": "Pendukung"}


def _stance_from_score(score: float | None) -> str:
    if score is None:
        return "netral"
    if score > 0.2:
        return "mendukung"
    if score < -0.2:
        return "menolak"
    return "netral"


def _distribusi(stance_list: list[str]) -> dict[str, int]:
    c = Counter(stance_list)
    return {
        "menolak": c.get("menolak", 0),
        "netral": c.get("netral", 0),
        "mendukung": c.get("mendukung", 0),
    }


def _format_relevansi(val: float | None) -> str:
    if val is None:
        return "0,00"
    # pakai koma desimal Indonesia
    return f"{val:.2f}".replace(".", ",")


def _kata_naik_turun(teks: str) -> str | None:
    """Deteksi arah angka: 'naik'/'meningkat'/'peningkatan' vs 'turun'/'menurun'/'penurunan'/'berkurang'."""
    t = teks.lower()
    if any(k in t for k in ("naik", "meningkat", "menguat", "bertambah", "peningkatan")):
        return "naik"
    if any(k in t for k in ("turun", "menurun", "berkurang", "melemah", "mengecil", "penurunan")):
        return "turun"
    return None


def build_computed(run: dict) -> dict:
    """
    Bangun field-field CaseStudy yang dihitung dari run (tanpa LLM).

    Args:
        run: Dict hasil run_simulation (memuat topik, kategori, tanggal, mode,
             sumber[], briefing, agen[], ronde_detail[], kualitas).

    Returns:
        Dict parsial CaseStudy (field yang dihitung, bukan narasi).
    """
    runde_detail = run.get("ronde_detail", [])
    if not runde_detail:
        return {}

    # ── Meta ────────────────────────────────────────────────────────────────
    n_agen = len(run.get("agen", [])) or len(runde_detail[0].get("agen", []))
    n_ronde = len(runde_detail)
    n_sumber = len(run.get("sumber", []))
    tanggal = run.get("tanggal", "4 Nov 2026")
    relevansi_vals = [s.get("relevansi") for s in run.get("sumber", []) if s.get("relevansi") is not None]
    relevansi_rata = sum(relevansi_vals) / len(relevansi_vals) if relevansi_vals else None

    # ── Stance per agen per ronde ──────────────────────────────────────────
    # Kumpulkan stance tiap agen di tiap ronde
    agen_stance_per_ronde: dict[str, list[str]] = {}
    agen_berubah_karena: dict[str, list[str]] = {}  # ronde -> alasan
    agen_alasan_per_ronde: dict[str, list[str]] = {}
    agen_fallback_per_ronde: dict[str, list[bool]] = {}
    agen_klaim_per_ronde: dict[str, list[dict]] = {}
    agen_score_per_ronde: dict[str, list[float]] = {}

    for rd in runde_detail:
        rno = rd["ronde"]
        for a in rd.get("agen", []):
            nama = a["nama"]
            stance = a.get("stance") or _stance_from_score(a.get("score"))
            agen_stance_per_ronde.setdefault(nama, []).append(stance)
            agen_berubah_karena.setdefault(nama, []).append(a.get("berubah_karena") or "")
            agen_alasan_per_ronde.setdefault(nama, []).append(a.get("alasan") or "")
            agen_fallback_per_ronde.setdefault(nama, []).append(bool(a.get("fallback")))
            agen_klaim_per_ronde.setdefault(nama, []).append({
                "klaim_agen": a.get("klaim_agen", False),
                "angka_klaim": a.get("angka_klaim", []),
            })
            agen_score_per_ronde.setdefault(nama, []).append(a.get("score", 0.0))

    # ── Hasil.distribusi: stance ronde terakhir + fallback_count ───────────
    stance_terakhir = [agen_stance_per_ronde[n][-1] for n in agen_stance_per_ronde]
    fallback_total = sum(
        1 for rd in runde_detail for a in rd.get("agen", []) if a.get("fallback")
    )
    distribusi_akhir = _distribusi(stance_terakhir)
    distribusi_akhir["fallback_count"] = fallback_total

    # Distribusi per ronde
    distribusi_per_ronde = []
    for rd in runde_detail:
        stances_r = [a.get("stance") or _stance_from_score(a.get("score")) for a in rd.get("agen", [])]
        fb_r = sum(1 for a in rd.get("agen", []) if a.get("fallback"))
        d = _distribusi(stances_r)
        d["fallback_count"] = fb_r
        distribusi_per_ronde.append(d)

    # ── Kubu: kelompokkan menurut stance AKHIR ────────────────────────────
    kubu_map: dict[str, list[str]] = {"tolak": [], "netral": [], "dukung": []}
    for nama, stances in agen_stance_per_ronde.items():
        akhir = stances[-1]
        tipe = STANCE_TO_TIPE.get(akhir, "netral")
        kubu_map[tipe].append(nama)

    kubu = []
    for tipe in ("tolak", "netral", "dukung"):
        if not kubu_map[tipe]:
            continue
        nama_kubu = TIPE_TO_NAMA_KUBU[tipe]
        if tipe == "tolak":
            catatan = "Menolak: kepuasan bukan bukti tepat sasaran."
        elif tipe == "netral":
            catatan = "Netral: terbuka pada bukti tambahan."
        else:
            catatan = "Mendukung: manfaat terlihat di posyandu."
        kubu.append({
            "nama": nama_kubu,
            "tipe": tipe,
            "catatan": catatan,
            "agen": kubu_map[tipe],
        })

    # ── Titik Balik: satu entri per agen yang pernah berubah, pakai perubahan TERAKHIR ────
    titik_balik = []
    for nama, stances in agen_stance_per_ronde.items():
        # Cari indeks perubahan terakhir yang BUKAN fallback
        perubahan_idx = None
        for i in range(1, len(stances)):
            if stances[i] != stances[i - 1] and not agen_fallback_per_ronde[nama][i]:
                perubahan_idx = i
        if perubahan_idx is not None:
            dari = stances[perubahan_idx - 1]
            ke = stances[perubahan_idx]
            kapan = f"Ronde {perubahan_idx + 1}"
            # Prioritaskan berubah_karena, fallback ke alasan agen
            alasan_bk = agen_berubah_karena[nama][perubahan_idx]
            alasan = alasan_bk if alasan_bk else agen_alasan_per_ronde[nama][perubahan_idx]
            titik_balik.append({
                "agen": nama,
                "dari": dari,
                "ke": ke,
                "kapan": kapan,
                "alasan": alasan,
            })

    # ── Ronde: ringkas + kutipan ──────────────────────────────────────────
    ronde_out = []
    for i, rd in enumerate(runde_detail):
        rno = rd["ronde"]
        dist = distribusi_per_ronde[i]

        # Pilih kutipan: prioritas agen yang berubah stance di ronde ini (non-fallback),
        # lalu |score| terbesar.
        kandidat = []
        for a in rd.get("agen", []):
            if a.get("fallback"):
                continue
            nama = a["nama"]
            berubah_di_ini = False
            if rno > 1 and len(agen_stance_per_ronde.get(nama, [])) >= rno:
                if agen_stance_per_ronde[nama][rno - 1] != agen_stance_per_ronde[nama][rno - 2]:
                    if not agen_fallback_per_ronde[nama][rno - 1]:
                        berubah_di_ini = True
            score = abs(a.get("score", 0.0))
            kandidat.append((berubah_di_ini, score, a))

        if kandidat:
            kandidat.sort(key=lambda x: (x[0], x[1]), reverse=True)
            pilih = kandidat[0][2]
            kutipan = {
                "teks": pilih.get("alasan", ""),
                "agen": pilih["nama"],
                "jenis": "klaim" if pilih.get("klaim_agen") else "langsung",
            }
        else:
            kutipan = None

        # Judul & ringkas sederhana (bisa diganti narator nanti)
        if rno == 1:
            judul = "Apa arti angka 72,8%?"
            ringkas = "Hampir semua peserta mempertanyakan angka kepuasan."
        elif rno == 2:
            judul = "Isu bergeser ke distribusi"
            ringkas = "Debat pindah ke soal siapa yang menerima."
        else:
            judul = "Bukti lapangan muncul, tafsirnya beda"
            ringkas = "Data dari lapangan masuk ke debat, tafsir berbeda."

        ronde_out.append({
            "no": rno,
            "judul": judul,
            "ringkas": ringkas,
            "distribusi": dist,
            "kutipan": kutipan,
        })

    # ── Bukti Diperdebatkan: angka_klaim beririsan tapi arah berlawanan ──────
    # Kumpulkan semua klaim per ronde
    bukti = []
    for i, rd in enumerate(runde_detail):
        rno = rd["ronde"]
        klaim_agen = {}
        for a in rd.get("agen", []):
            angka_list = a.get("angka_klaim", [])
            for angka in angka_list:
                # Normalisasi angka untuk cocokan (hapus spasi, persen, koma/titik)
                norm = angka.replace(" ", "").replace("%", "").replace(",", ".")
                klaim_agen.setdefault(norm, []).append({
                    "agen": a["nama"],
                    "teks": a.get("alasan", ""),
                    "arah": _kata_naik_turun(a.get("alasan", "")),
                })

        for norm_angka, entri_list in klaim_agen.items():
            if len(entri_list) >= 2:
                arah_set = set(e["arah"] for e in entri_list if e["arah"])
                if "naik" in arah_set and "turun" in arah_set:
                    for e in entri_list:
                        bukti.append({
                            "agen": f"{e['agen']} · Ronde {rno}",
                            "teks": e["teks"],
                        })
                    # Hanya catat sekali per angka per ronde
                    break

    # ── Kepercayaan ────────────────────────────────────────────────────────
    if n_sumber == 0:
        level = "Rendah"
    elif n_sumber <= 1 or (relevansi_rata is not None and relevansi_rata < 0.3):
        level = "Rendah–Sedang"
    elif n_sumber <= 3:
        level = "Sedang"
    else:
        level = "Sedang–Tinggi"

    catatan = f"{n_sumber} sumber"
    if relevansi_rata is not None:
        catatan += f" · relevansi konteks {_format_relevansi(relevansi_rata)}"

    kepercayaan = {"level": level, "catatan": catatan}

    # ── Keterbatasan ──────────────────────────────────────────────────────
    keterbatasan_parts = []
    if n_sumber <= 1:
        keterbatasan_parts.append(
            "Simulasi ini hanya memakai 1 artikel sumber, dan angka yang "
            "muncul di debat adalah klaim para agen, bukan data yang sudah diverifikasi."
        )
    else:
        keterbatasan_parts.append(
            f"Simulasi ini memakai {n_sumber} artikel sumber, dan angka yang "
            "muncul di debat adalah klaim para agen, bukan data yang sudah diverifikasi."
        )

    kualitas = run.get("kualitas", {})
    fb_count = kualitas.get("fallback_count", 0)
    total_giliran = kualitas.get("total_giliran", 0)
    if fb_count > 0:
        keterbatasan_parts.append(f"{fb_count} dari {total_giliran} giliran memakai nilai cadangan.")

    # perubahan_tanpa_alasan count
    tanpa_alasan = sum(
        1 for rd in runde_detail for a in rd.get("agen", [])
        if a.get("perubahan_tanpa_alasan")
    )
    if tanpa_alasan > 0:
        keterbatasan_parts.append(
            f"{tanpa_alasan} giliran berubah stance tanpa alasan pemicu yang terisi."
        )

    keterbatasan = " ".join(keterbatasan_parts)

    # ── Situasi ────────────────────────────────────────────────────────────
    pemicu_angka = "72,8%"
    pemicu_teks = (
        "masyarakat disebut puas dengan program Makan Bergizi Gratis. "
        "Tapi muncul pertanyaan lain: apakah bantuan itu sampai ke yang paling membutuhkan?"
    )
    bahan = [
        "Isu keracunan makanan berulang",
        "Keluarga miskin yang disebut belum terjangkau",
        "Kepuasan tinggi belum tentu berarti masalah kesehatan berkurang",
    ]
    sumber_teks = f"Sumber: {n_sumber} artikel RSS."
    if n_sumber <= 1:
        sumber_teks += " Briefing terbatas."

    situasi = {
        "pemicu": {"angka": pemicu_angka, "teks": pemicu_teks},
        "bahan": bahan,
        "sumber": sumber_teks,
    }

    # ── Vonis (sederhana) ─────────────────────────────────────────────────
    if distribusi_akhir["menolak"] > distribusi_akhir["netral"] + distribusi_akhir["mendukung"]:
        vonis = "Mayoritas peserta menolak anggapan bahwa MBG sudah tepat sasaran."
    elif distribusi_akhir["mendukung"] > distribusi_akhir["menolak"] + distribusi_akhir["netral"]:
        vonis = "Mayoritas peserta mendukung anggapan bahwa MBG sudah tepat sasaran."
    else:
        vonis = "Pendapat peserta tercampur, tidak ada mayoritas jelas."

    # ── Alasan (3 poin utama dari ronde terakhir non-fallback, |score| terbesar) ────
    kandidat_alasan = []
    for a in runde_detail[-1].get("agen", []):
        if a.get("fallback"):
            continue
        kandidat_alasan.append((abs(a.get("score", 0.0)), a.get("alasan", "")))
    kandidat_alasan.sort(key=lambda x: x[0], reverse=True)
    alasan_top = [a for _, a in kandidat_alasan[:3]]

    # ── Skenario & WhatIf (placeholder, narator isi nanti) ────────────────
    skenario = [
        {"jika": "Pemerintah membuka data distribusi secara transparan", "maka": "Oposisi Kritis bisa lebih moderat."},
        {"jika": "Hasil audit menunjukkan keracunan makanan menurun", "maka": "Pengusaha/UMKM mungkin beralih ke netral."},
        {"jika": "Data baru menunjukkan perbaikan nyata di lapangan", "maka": "Jurnalis/Media bisa mengubah sikap."},
        {"jika": "Anak-anak di daerah terpencil tetap terpinggirkan", "maka": "Aksi protes dari kubu kritis cenderung meningkat."},
    ]
    whatif = {
        "judul": "Bagaimana kalau pemerintah merilis data distribusi per kecamatan?",
        "deskripsi": "Simulasi dijalankan ulang dengan satu intervensi, lalu hasilnya dibandingkan dengan simulasi awal.",
        "sebelum": distribusi_akhir,
        "sesudah": None,
    }

    return {
        "meta": {"peserta": n_agen, "ronde": n_ronde, "sumber": n_sumber, "tanggal": tanggal},
        "keterbatasan": keterbatasan,
        "hasil": {
            "vonis": vonis,
            "distribusi": distribusi_akhir,
            "alasan": alasan_top,
            "kepercayaan": kepercayaan,
        },
        "situasi": situasi,
        "kubu": kubu,
        "ronde": ronde_out,
        "titikBalik": titik_balik,
        "buktiDiperdebatkan": bukti,
        "skenario": skenario,
        "whatif": whatif,
    }