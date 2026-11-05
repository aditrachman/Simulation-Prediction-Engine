# backend/services/casestudy_builder.py
# Builder CaseStudy: build_computed(run) -> dict parsial CaseStudy.
# Hanya logika yang DIHITUNG dari run, tanpa LLM.

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any

STANCE_LABELS = ("menolak", "netral", "mendukung")
STANCE_TO_TIPE = {"menolak": "tolak", "netral": "netral", "mendukung": "dukung"}
TIPE_TO_NAMA_KUBU = {"tolak": "Kritikus", "netral": "Penengah", "dukung": "Pendukung"}

_BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def normalisasi_judul(teks: str) -> str:
    """Rapikan spasi dan tanda baca judul tanpa mengubah kata."""
    judul = " ".join((teks or "").split())
    judul = re.sub(r"\s+([?!])", r"\1", judul)
    return judul[:1].upper() + judul[1:]


def _tanggal_dari_run(run: dict) -> str:
    """Satu sumber tanggal: field run, lalu waktu simpan, lalu hari ini."""
    eksplisit = run.get("tanggal")
    if eksplisit:
        return eksplisit
    saved_at = (run.get("_meta") or {}).get("saved_at")
    if saved_at:
        dt = datetime.fromtimestamp(saved_at)
        return f"{dt.day} {_BULAN[dt.month - 1]} {dt.year}"
    # fallback hari ini -> string kosong supaya chip frontend tidak tampil
    return ""


_POLA_PERSEN = re.compile(r"\d+(?:[.,]\d+)?\s?%")


def _teks_sumber(run: dict) -> str:
    """Gabungkan briefing dan sumber run menjadi satu teks."""
    bagian = [str(run.get("briefing") or "")]
    for s in run.get("sumber") or []:
        if isinstance(s, dict):
            bagian.extend(str(v) for v in s.values() if isinstance(v, (str, int, float)))
        else:
            bagian.append(str(s))
    return " ".join(bagian)


def _bersihkan_awalan(teks: str) -> str:
    """Buang awalan 'Jika ' atau 'Maka ' (case-insensitive) yang terduplikasi."""
    t = teks.strip()
    while True:
        t_lower = t.lower()
        if t_lower.startswith("jika "):
            t = t[5:].strip()
        elif t_lower.startswith("maka "):
            t = t[5:].strip()
        else:
            break
    return t


_POLA_PERSEN = re.compile(r"\d+(?:[.,]\d+)?\s?%")


def _teks_sumber(run: dict) -> str:
    """Gabungkan briefing dan sumber run menjadi satu teks."""
    bagian = [str(run.get("briefing") or "")]
    for s in run.get("sumber") or []:
        if isinstance(s, dict):
            bagian.extend(str(v) for v in s.values() if isinstance(v, (str, int, float)))
        else:
            bagian.append(str(s))
    return " ".join(bagian)


def _angka_pemicu(run: dict) -> str | None:
    """Angka persen pertama yang tertulis verbatim di briefing/sumber run."""
    cocok = _POLA_PERSEN.search(_teks_sumber(run))
    return cocok.group(0) if cocok else None


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
    return f"{val:.2f}".replace(".", ",")


def _kata_naik_turun(teks: str) -> str | None:
    t = teks.lower()
    if any(k in t for k in ("naik", "meningkat", "menguat", "bertambah", "peningkatan")):
        return "naik"
    if any(k in t for k in ("turun", "menurun", "berkurang", "melemah", "mengecil", "penurunan")):
        return "turun"
    return None


def build_computed(run: dict) -> dict:
    runde_detail = run.get("ronde_detail", [])
    if not runde_detail:
        return {}

    # ── Meta ────────────────────────────────────────────────────────────────
    n_agen = len(run.get("agen", [])) or len(runde_detail[0].get("agen", []))
    n_ronde = len(runde_detail)
    n_sumber = len(run.get("sumber", []))
    tanggal = _tanggal_dari_run(run)
    relevansi_vals = [s.get("relevansi") for s in run.get("sumber", []) if s.get("relevansi") is not None]
    relevansi_rata = sum(relevansi_vals) / len(relevansi_vals) if relevansi_vals else None

    # ── Stance per agen per ronde ──────────────────────────────────────────
    agen_stance_per_ronde: dict[str, list[str]] = {}
    agen_berubah_karena: dict[str, list[str]] = {}
    agen_alasan_per_ronde: dict[str, list[str]] = {}
    agen_fallback_per_ronde: dict[str, list[bool]] = {}
    agen_klaim_per_ronde: dict[str, list[dict]] = {}
    agen_score_per_ronde: dict[str, list[float]] = {}

    for rd in runde_detail:
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

    # ── Hasil.distribusi: stance ronde terakhir (tanpa fallback_count) ──────
    stance_terakhir = [agen_stance_per_ronde[n][-1] for n in agen_stance_per_ronde]
    distribusi_akhir = _distribusi(stance_terakhir)

    # Distribusi per ronde (tanpa fallback_count)
    distribusi_per_ronde = []
    for rd in runde_detail:
        stances_r = [a.get("stance") or _stance_from_score(a.get("score")) for a in rd.get("agen", [])]
        distribusi_per_ronde.append(_distribusi(stances_r))

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
        n_anggota = len(kubu_map[tipe])
        label = {"tolak": "menolak", "netral": "netral", "dukung": "mendukung"}[tipe]
        kubu.append({
            "nama": nama_kubu,
            "tipe": tipe,
            "catatan": f"{n_anggota} peserta {label}.",
            "agen": kubu_map[tipe],
        })

    # ── Titik Balik: satu entri per agen, perubahan TERAKHIR non-fallback ──
    titik_balik = []
    for nama, stances in agen_stance_per_ronde.items():
        perubahan_idx = None
        for i in range(1, len(stances)):
            if stances[i] != stances[i - 1] and not agen_fallback_per_ronde[nama][i]:
                perubahan_idx = i
        if perubahan_idx is not None:
            dari = stances[perubahan_idx - 1]
            ke = stances[perubahan_idx]
            kapan = f"Ronde {perubahan_idx + 1}"
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

        # Kutipan: prioritas agen berubah stance di ronde ini (non-fallback), lalu |score| terbesar
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

        judul = f"Sikap peserta di ronde {rno}"
        ringkas = (
            f"{dist['menolak']} menolak, {dist['netral']} netral, "
            f"{dist['mendukung']} mendukung."
        )
        # Tambah info pergeseran bila ada agen berubah stance di ronde ini
        if rno > 1:
            bergeser = []
            for nama, stances in agen_stance_per_ronde.items():
                if len(stances) >= rno:
                    dari = stances[rno - 2]
                    ke = stances[rno - 1]
                    if dari != ke and not agen_fallback_per_ronde[nama][rno - 1]:
                        bergeser.append(f"{nama} bergeser dari {dari} ke {ke}")
            if bergeser:
                ringkas += " " + "; ".join(bergeser) + "."

        runde_dict = {
            "no": rno,
            "judul": judul,
            "ringkas": ringkas,
            "distribusi": dist,
        }
        if kutipan:
            runde_dict["kutipan"] = kutipan
        ronde_out.append(runde_dict)

    # ── Bukti Diperdebatkan: max 3 entri, 1 per agen (ronde terbaru), berpasangan ──
    # Kumpulkan klaim per agen (ambil ronde TERBARU untuk setiap agen-angka)
    klaim_per_agen: dict[str, dict[str, dict]] = {}  # agen -> norm_angka -> {teks, arah, ronde}
    for rd in runde_detail:
        rno = rd["ronde"]
        for a in rd.get("agen", []):
            nama = a["nama"]
            for angka in a.get("angka_klaim", []):
                norm = angka.replace(" ", "").replace("%", "").replace(",", ".")
                if nama not in klaim_per_agen:
                    klaim_per_agen[nama] = {}
                klaim_per_agen[nama][norm] = {
                    "teks": a.get("alasan", ""),
                    "arah": _kata_naik_turun(a.get("alasan", "")),
                    "ronde": rno,
                }

    # Cari pasangan agen yang klaim angka sama tapi arah berlawanan
    bukti_pairs = []
    angka_terpakai = set()
    for agen1, data1 in klaim_per_agen.items():
        for norm1, info1 in data1.items():
            if norm1 in angka_terpakai:
                continue
            if not info1["arah"]:
                continue
            for agen2, data2 in klaim_per_agen.items():
                if agen2 == agen1:
                    continue
                if norm1 in data2:
                    info2 = data2[norm1]
                    if info2["arah"] and info1["arah"] != info2["arah"]:
                        # Pasangan ditemukan
                        # Urutkan: yang "naik" dulu, lalu "turun"
                        if info1["arah"] == "naik":
                            first, second = (agen1, info1), (agen2, info2)
                        else:
                            first, second = (agen2, info2), (agen1, info1)
                        bukti_pairs.append({
                            "angka": norm1,
                            "agens": [
                                {"agen": f"{first[0]} · Ronde {first[1]['ronde']}", "teks": first[1]["teks"]},
                                {"agen": f"{second[0]} · Ronde {second[1]['ronde']}", "teks": second[1]["teks"]},
                            ],
                        })
                        angka_terpakai.add(norm1)
                        break

    # Flatten ke list bukti (max 3 entri = 1 pasangan + 1 tambahan, atau 1 pasangan penuh = 2 entri)
    bukti = []
    for pair in bukti_pairs:
        for e in pair["agens"]:
            if len(bukti) >= 3:
                break
            bukti.append(e)
        if len(bukti) >= 3:
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
    if n_sumber == 0:
        keterbatasan_parts.append(
            "Simulasi ini tidak memakai artikel sumber, dan angka yang "
            "muncul di debat adalah klaim para agen, bukan data yang sudah diverifikasi."
        )
    elif n_sumber == 1:
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

    tanpa_alasan = sum(
        1 for rd in runde_detail for a in rd.get("agen", [])
        if a.get("perubahan_tanpa_alasan")
    )
    if tanpa_alasan > 0:
        keterbatasan_parts.append(
            f"{tanpa_alasan} giliran berubah stance tanpa alasan pemicu yang terisi."
        )

    keterbatasan = " ".join(keterbatasan_parts)

    # ── Situasi: dari topik dan briefing run, tanpa naskah tertanam ────────
    topik = (run.get("topik") or "").strip()
    pemicu_teks = (
        f"Topik simulasi ini: {topik}" if topik else "Topik simulasi ini tidak disebutkan."
    )
    pemicu_angka = _angka_pemicu(run)
    bahan: list[str] = []
    sumber_teks = f"Sumber: {n_sumber} artikel RSS."
    if n_sumber <= 1:
        sumber_teks += " Briefing terbatas."

    situasi = {
        "pemicu": {"angka": pemicu_angka, "teks": pemicu_teks},
        "bahan": bahan,
        "sumber": sumber_teks,
    }

    # ── Vonis ──────────────────────────────────────────────────────────────
    total = sum(distribusi_akhir.values())
    if distribusi_akhir["menolak"] > distribusi_akhir["netral"] + distribusi_akhir["mendukung"]:
        vonis = f"Sikap akhir: {distribusi_akhir['menolak']} dari {total} peserta menolak. Pertanyaan: {run.get('topik', 'topik ini')}"
    elif distribusi_akhir["mendukung"] > distribusi_akhir["menolak"] + distribusi_akhir["netral"]:
        vonis = f"Sikap akhir: {distribusi_akhir['mendukung']} dari {total} peserta mendukung. Pertanyaan: {run.get('topik', 'topik ini')}"
    else:
        vonis = f"Sikap akhir: pendapat tercampur ({distribusi_akhir['menolak']} menolak, {distribusi_akhir['netral']} netral, {distribusi_akhir['mendukung']} mendukung). Pertanyaan: {run.get('topik', 'topik ini')}"

    # ── Alasan (3 poin utama dari ronde terakhir non-fallback, |score| terbesar) ──
    # Filter: non-fallback, sesuai_topik=true, stance = mayoritas ronde terakhir
    stance_terakhir_list = [s[-1] for s in agen_stance_per_ronde.values()]
    mayoritas = max(set(stance_terakhir_list), key=stance_terakhir_list.count)
    kandidat_alasan = []
    for a in runde_detail[-1].get("agen", []):
        if a.get("fallback"):
            continue
        if not a.get("sesuai_topik", True):
            continue
        stance_a = a.get("stance") or _stance_from_score(a.get("score"))
        if stance_a != mayoritas:
            continue
        kandidat_alasan.append((abs(a.get("score", 0.0)), a.get("alasan", "")))
    kandidat_alasan.sort(key=lambda x: x[0], reverse=True)
    alasan_top = [f'"{a}"' for _, a in kandidat_alasan[:3]]

    # ── Skenario: hanya dari kubu yang benar-benar ada di run ─────────────
    akibat = {
        "tolak": "{n} peserta Kritikus bisa bergeser ke netral.",
        "netral": "{n} peserta Penengah bisa memilih salah satu sisi.",
        "dukung": "{n} peserta Pendukung bisa melemah.",
    }
    skenario = [
        {
            "jika": _bersihkan_awalan(f"muncul bukti baru yang menantang kubu {k['nama']}"),
            "maka": _bersihkan_awalan(akibat[k["tipe"]].format(n=len(k["agen"]))),
            "dasar_agen": k["agen"][0],
        }
        for k in kubu
    ]

    kualitas = run.get("kualitas")
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
        **({"kualitas": kualitas} if kualitas else {}),
    }