# backend/core/scenario.py
# Sumber kebenaran tunggal untuk skenario, kepercayaan, dan ringkasan polarisasi.
# Tidak mengubah perilaku lama: heuristic_predict, compute_confidence,
# compute_polarization tetap utuh untuk kompatibilitas tes.

from __future__ import annotations

from typing import Optional
from .prediction import heuristic_predict, compute_confidence
from .metrics import compute_polarization, compute_consensus


def resolve_scenario(
    sentimen_agregat: dict[str, list[float]],
    n_agents: int,
    n_rounds: int,
    quality_score: float,
    events: Optional[list] = None,
    crowd_data: Optional[dict] = None,
    n_samples_history: int = 0,
    n_feedback_labels: int = 0,
) -> dict:
    """
    Sumber kebenaran tunggal untuk menentukan arah skenario, kekuatan,
    hitungan kubu, dan skor aturan konstan.

    Memanggil heuristic_predict yang sudah ada, lalu memperkaya output
    dengan struktur yang bisa diverifikasi dan dibandingkan.

    Returns:
        {
            "arah": "Konsensus|Polarisasi|Status Quo",
            "aturan": "teks singkat aturan yang terpenuhi",
            "kekuatan": "Kuat|Sedang|Lemah",
            "hitungan": {"mendukung": n, "netral": n, "menolak": n},
            "skor_aturan": {
                "pct_pos": float,
                "pct_neg": float,
                "pct_net": float,
                "variance": float,
                "threshold_pos": 0.6,
                "threshold_neg": 0.5,
                "threshold_net": 0.6,
            }
        }
    """
    # Panggil heuristic_predict yang sudah ada (tidak diubah)
    hp = heuristic_predict(
        sentimen_agregat=sentimen_agregat,
        n_agents=n_agents,
        n_rounds=n_rounds,
        quality_score=quality_score,
        events=events,
        crowd_data=crowd_data,
        n_samples_history=n_samples_history,
        n_feedback_labels=n_feedback_labels,
    )

    prediksi = hp.get("prediksi", {})
    # Tentukan arah dari kunci prediksi tertinggi
    if not prediksi:
        arah = "Status Quo"
        aturan = "tidak ada prediksi heuristic"
    else:
        arah = max(prediksi, key=prediksi.get)
        aturan = _aturan_dari_arah(arah, hp.get("reasoning", ""))

    # Hitung hitungan kubu dari sentimen_agregat (sebelum crowd blend)
    total = 0
    n_pos = n_neg = n_net = 0
    for nama, tren in sentimen_agregat.items():
        if not tren:
            continue
        total += 1
        skor = tren[-1]
        if skor > 0.2:
            n_pos += 1
        elif skor < -0.2:
            n_neg += 1
        else:
            n_net += 1

    pct_pos = n_pos / total if total else 0.0
    pct_neg = n_neg / total if total else 0.0
    pct_net = n_net / total if total else 0.0

    # Variance untuk skor_aturan
    all_scores = [tren[-1] for tren in sentimen_agregat.values() if tren]
    variance = 0.0
    if len(all_scores) > 1:
        import statistics
        variance = statistics.variance(all_scores)

    # Kekuatan = selisih kubu pemicu terhadap ambangnya, dalam poin persentase.
    margin_pp = _margin_pemicu(arah, pct_pos, pct_neg, pct_net, variance)
    kekuatan = _kekuatan_dari_margin(margin_pp)

    return {
        "arah": arah,
        "aturan": aturan,
        "kekuatan": kekuatan,
        "hitungan": {
            "mendukung": n_pos,
            "netral": n_net,
            "menolak": n_neg,
        },
        "skor_aturan": {
            "pct_pos": pct_pos,
            "pct_neg": pct_neg,
            "pct_net": pct_net,
            "variance": round(variance, 3),
            "threshold_pos": 0.6,
            "threshold_neg": 0.5,
            "threshold_net": 0.6,
            "margin_pp": round(margin_pp, 2),
        },
    }


def _margin_pemicu(
    arah: str,
    pct_pos: float,
    pct_neg: float,
    pct_net: float,
    variance: float,
) -> float:
    """Selisih kubu pemicu terhadap ambangnya, dalam poin persentase."""
    if arah == "Konsensus":
        return (pct_pos - 0.6) * 100
    if arah == "Polarisasi":
        margins = []
        if pct_neg >= 0.5:
            margins.append((pct_neg - 0.5) * 100)
        if variance > 0.3:
            margins.append((variance - 0.3) * 100)
        return max(margins) if margins else 0.0
    if arah == "Status Quo" and pct_net >= 0.6:
        return (pct_net - 0.6) * 100
    return 0.0


def _kekuatan_dari_margin(margin_pp: float) -> str:
    if margin_pp >= 15:
        return "Kuat"
    if margin_pp >= 5:
        return "Sedang"
    return "Lemah"


def _aturan_dari_arah(arah: str, reasoning: str) -> str:
    """Ringkas aturan singkat dari reasoning heuristic."""
    if arah == "Konsensus":
        return ">=60% peserta bersikap mendukung"
    elif arah == "Polarisasi":
        return ">=50% menolak ATAU variansi sentimen > 0.3"
    elif arah == "Status Quo":
        return ">=60% netral ATAU tidak memenuhi ambang lain"
    return reasoning[:120] if reasoning else "tidak ditentukan"


def kepercayaan_sumber(
    sumber_status: str,
    sumber_relevan: int,
    isi_dibaca: bool,
    n_agen: int,
    n_ronde: int,
) -> dict:
    """
    Tentukan level kepercayaan berdasarkan status sumber dan relevansi.

    Level:
      - Sedang: sumber_status == "ok" DAN sumber_relevan >= 3
      - Rendah: selain itu (kosong, gagal, sedikit, atau < 3)
    Isi artikel tidak pernah dibaca, jadi tidak pernah Tinggi.
    """
    if sumber_status == "ok" and sumber_relevan >= 3:
        level = "Sedang"
        if isi_dibaca:
            alasan = f"{sumber_relevan} sumber relevan lolos filter; briefing tersedia."
        else:
            alasan = f"{sumber_relevan} sumber relevan lolos filter; hanya judul berita yang dibaca."
    else:
        level = "Rendah"
        if sumber_status == "kosong":
            alasan = "Pencarian berhasil tapi tidak ada artikel yang cocok."
        elif sumber_status == "gagal":
            alasan = "Pengambilan berita gagal; simulasi berjalan tanpa konteks real."
        elif sumber_status == "sedikit":
            alasan = f"Hanya {sumber_relevan} artikel lolos filter (< 3)."
        else:
            alasan = "Status sumber tidak dikenali atau tidak memenuhi syarat."

    return {
        "level": level,
        "alasan": alasan,
        "fakta": {
            "sumber_relevan": sumber_relevan,
            "isi_dibaca": isi_dibaca,  # selalu False — hanya judul/ringkasan
            "agen": n_agen,
            "ronde": n_ronde,
        },
    }


def teks_polarisasi(
    skor_akhir: dict[str, float],
    total_peserta: int,
) -> str:
    """
    Hasilkan teks polarisasi untuk laporan.

    Kata "polarisasi" hanya dipakai bila kubu terkecil >= 30%
    dari peserta yang BERSIKAP (|skor| > 0.2).
    Selain itu: "Mayoritas mendukung/menolak (n dari m); minoritas ..."
    """
    n_pos = sum(1 for s in skor_akhir.values() if s > 0.2)
    n_neg = sum(1 for s in skor_akhir.values() if s < -0.2)
    n_net = sum(1 for s in skor_akhir.values() if -0.2 <= s <= 0.2)

    bersikap = n_pos + n_neg
    if bersikap == 0:
        return f"Semua {total_peserta} peserta netral; tidak ada polarisasi terdeteksi."

    # Cek apakah kubu terkecil >= 30% dari yang bersikap
    kecil = min(n_pos, n_neg)
    if kecil >= 0.3 * bersikap:
        pct_kecil = round(kecil / bersikap * 100)
        return (
            f"Terjadi polarisasi: {n_pos} mendukung vs {n_neg} menolak "
            f"({bersikap} dari {total_peserta} bersikap; kubu terkecil: {kecil} orang ({pct_kecil}%))."
        )

    # Bukan polarisasi: mayoritas vs minoritas
    if n_pos > n_neg:
        return f"Mayoritas mendukung ({n_pos} dari {total_peserta}); minoritas menolak ({n_neg})."
    elif n_neg > n_pos:
        return f"Mayoritas menolak ({n_neg} dari {total_peserta}); minoritas mendukung ({n_pos})."
    else:
        return f"Terbagi rata: {n_pos} mendukung, {n_neg} menolak, {n_net} netral."


def swing_voter_terfilter(
    sentimen_agregat: dict[str, list[float]],
    ambang: float = 0.15,
) -> dict:
    """
    Kembalikan swing voter dengan volatilitas >= ambang.

    Jika kosong: daftar kosong dengan flag "tidak_ada": true.
    """
    import statistics
    volatilitas = {}
    for nama, tren in sentimen_agregat.items():
        if len(tren) < 2:
            volatilitas[nama] = 0.0
        else:
            volatilitas[nama] = round(
                sum(abs(tren[i] - tren[i - 1]) for i in range(1, len(tren))) / (len(tren) - 1),
                3,
            )

    terpilih = [
        {
            "nama": nama,
            "volatilitas": v,
            "sikap_awal": sentimen_agregat[nama][0],
            "sikap_akhir": sentimen_agregat[nama][-1],
            "potensi_arah": "positif" if sentimen_agregat[nama][-1] > 0 else "negatif",
        }
        for nama, v in volatilitas.items()
        if v >= ambang
    ]

    if not terpilih:
        return {"daftar": [], "tidak_ada": True, "ambang": ambang}

    terpilih.sort(key=lambda x: -x["volatilitas"])
    return {"daftar": terpilih, "tidak_ada": False, "ambang": ambang}