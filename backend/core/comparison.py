# backend/core/comparison.py
# Phase 7: Scenario Comparison — bandingkan hasil dua simulasi atau lebih.

from __future__ import annotations

import statistics
from typing import Optional


def _safe_get(d: dict, *keys, default=None):
    """Ambil nested key dari dict dengan fallback."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    return d if d is not None else default


def compare_prediction(
    pred_a: dict,
    pred_b: dict,
    label_a: str = "Skenario A",
    label_b: str = "Skenario B",
) -> dict:
    """
    Bandingkan dua prediksi skenario.

    Returns:
        {
            "a": {"label": ..., "Konsensus": ..., ...},
            "b": {"label": ..., "Konsensus": ..., ...},
            "diff": {"Konsensus": diff, "Polarisasi": diff, "Status Quo": diff},
            "kesimpulan": str,
        }
    """
    all_keys = list(set(pred_a.keys()) | set(pred_b.keys()))
    diff: dict[str, int] = {}
    for k in all_keys:
        va = pred_a.get(k, 0)
        vb = pred_b.get(k, 0)
        diff[k] = vb - va

    # Cari perubahan terbesar
    biggest_change = max(diff.values(), key=abs) if diff else 0
    biggest_key = max(diff, key=lambda k: abs(diff[k])) if diff else ""

    if biggest_change > 10:
        kesimpulan = (
            f"Perbedaan utama: {label_b} {biggest_key.lower()} "
            f"{'naik' if biggest_change > 0 else 'turun'} {abs(biggest_change)}% "
            f"dibanding {label_a}."
        )
    else:
        kesimpulan = (
            f"Tidak ada perbedaan signifikan antara {label_a} dan {label_b} "
            f"(semua selisih < 10%)."
        )

    return {
        "a":   {"label": label_a, **pred_a},
        "b":   {"label": label_b, **pred_b},
        "diff": diff,
        "kesimpulan": kesimpulan,
    }


def compare_sentiment_trends(
    sentimen_a: dict[str, list[float]],
    sentimen_b: dict[str, list[float]],
    label_a: str = "Skenario A",
    label_b: str = "Skenario B",
) -> dict:
    """
    Bandingkan tren sentimen antar dua simulasi.

    Returns:
        {
            "per_agent": {nama: {"a_akhir": float, "b_akhir": float, "perubahan": float}, ...},
            "rata_rata": {"a": float, "b": float, "perubahan": float},
        }
    """
    all_agents = list(set(sentimen_a.keys()) | set(sentimen_b.keys()))
    per_agent: dict = {}

    for nama in all_agents:
        tren_a = sentimen_a.get(nama, [])
        tren_b = sentimen_b.get(nama, [])
        akhir_a = tren_a[-1] if tren_a else 0.0
        akhir_b = tren_b[-1] if tren_b else 0.0
        per_agent[nama] = {
            "a_akhir":    round(akhir_a, 2),
            "b_akhir":    round(akhir_b, 2),
            "perubahan":  round(akhir_b - akhir_a, 2),
        }

    # Rata-rata semua agen
    all_akhir_a = [v["a_akhir"] for v in per_agent.values()]
    all_akhir_b = [v["b_akhir"] for v in per_agent.values()]
    mean_a = statistics.mean(all_akhir_a) if all_akhir_a else 0.0
    mean_b = statistics.mean(all_akhir_b) if all_akhir_b else 0.0

    return {
        "per_agent": per_agent,
        "rata_rata": {
            "a":         round(mean_a, 2),
            "b":         round(mean_b, 2),
            "perubahan": round(mean_b - mean_a, 2),
        },
    }


def compare_actors(
    aktor_a: dict,
    aktor_b: dict,
    label_a: str = "Skenario A",
    label_b: str = "Skenario B",
) -> dict:
    """
    Bandingkan aktor kunci antar dua simulasi.

    Returns:
        {
            "a": {"kunci": [...], "penggerak": str},
            "b": {"kunci": [...], "penggerak": str},
            "perbedaan_penggerak": str | None,
        }
    """
    def _safe_aktor(d: dict) -> dict:
        kunci = _safe_get(d, "aktor_kunci", default=[])
        penggerak = _safe_get(d, "aktor_penggerak", default="-")
        swing = _safe_get(d, "swing_voter", default=[])
        return {
            "kunci": [k.get("nama", "-") for k in kunci],
            "penggerak": penggerak,
            "swing": [s.get("nama", "-") for s in swing],
        }

    a = _safe_aktor(aktor_a)
    b = _safe_aktor(aktor_b)

    perbedaan_penggerak = None
    if a["penggerak"] != b["penggerak"]:
        perbedaan_penggerak = (
            f"Aktor penggerak berubah: {label_a} → {a['penggerak']}, "
            f"{label_b} → {b['penggerak']}."
        )

    return {
        "a": a,
        "b": b,
        "perbedaan_penggerak": perbedaan_penggerak,
    }


def generate_comparison_report(
    hasil_a: dict,
    hasil_b: dict,
    label_a: str = "Baseline",
    label_b: str = "Dengan Intervensi",
) -> dict:
    """
    Generate laporan perbandingan lengkap antara dua hasil simulasi.

    Args:
        hasil_a: Hasil dari run_simulation() skenario pertama
        hasil_b: Hasil dari run_simulation() skenario kedua
        label_a: Label untuk skenario pertama (default: "Baseline")
        label_b: Label untuk skenario kedua (default: "Dengan Intervensi")

    Returns:
        Dict dengan semua data perbandingan + ringkasan.
    """
    prediksi_a = hasil_a.get("prediksi", {})
    prediksi_b = hasil_b.get("prediksi", {})
    sentimen_a = hasil_a.get("sentimen_agregat", {})
    sentimen_b = hasil_b.get("sentimen_agregat", {})
    # BUG #6 FIX: ambil sub-dict aktor_analisis, bukan full hasil dict
    aktor_a = hasil_a.get("aktor_analisis", {})
    aktor_b = hasil_b.get("aktor_analisis", {})

    prediksi_comp = compare_prediction(prediksi_a, prediksi_b, label_a, label_b)
    sentimen_comp = compare_sentiment_trends(sentimen_a, sentimen_b, label_a, label_b)
    aktor_comp = compare_actors(aktor_a, aktor_b, label_a, label_b)

    # Ringkasan perubahan
    changes: list[str] = []
    if prediksi_comp.get("kesimpulan"):
        changes.append(prediksi_comp["kesimpulan"])

    for nama, data in sentimen_comp.get("per_agent", {}).items():
        p = data.get("perubahan", 0)
        if abs(p) >= 0.3:
            arah = "lebih mendukung" if p > 0 else "lebih menolak"
            changes.append(f"{nama} {arah} di {label_b} (perubahan {p:+.2f}).")

    if aktor_comp.get("perbedaan_penggerak"):
        changes.append(aktor_comp["perbedaan_penggerak"])

    return {
        "label_a":            label_a,
        "label_b":            label_b,
        "prediksi":           prediksi_comp,
        "sentimen":           sentimen_comp,
        "aktor":              aktor_comp,
        "ringkasan_perubahan": changes,
        "intervensi_a":       hasil_a.get("intervensi"),
        "intervensi_b":       hasil_b.get("intervensi"),
    }
