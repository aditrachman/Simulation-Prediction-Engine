# backend/core/prediction.py
# Phase 6: Prediction Cleanup — heuristic prediction + confidence score.
# Pure Python, no LLM calls. Separated from ml_pipeline.py for clarity.

from __future__ import annotations

import statistics
from typing import Optional


def compute_confidence(
    n_agents: int,
    n_rounds: int,
    n_samples_history: int,
    n_feedback_labels: int,
    sentiment_variance: float,
    quality_score: float,
) -> dict:
    """
    Hitung confidence score untuk prediksi (0.0–1.0).

    Faktor yang memengaruhi:
    - Jumlah agen (>=5 = lebih percaya diri)
    - Jumlah ronde (>=3 = lebih percaya diri)
    - Data historis (>= 20 sampel ML)
    - Feedback labels (>= 3 feedback)
    - Variance sentimen (variance tinggi = kurang percaya diri)
    - Quality score dari simulation_quality

    Returns:
        {"score": float, "label": "rendah"|"sedang"|"tinggi", "alasan": [str]}
    """
    reasons: list[str] = []
    score = 0.5  # baseline

    # Agen
    if n_agents >= 5:
        score += 0.12
    elif n_agents >= 3:
        score += 0.06
    else:
        reasons.append("Jumlah agen sedikit, dinamika opini terbatas.")

    # Ronde
    if n_rounds >= 3:
        score += 0.1
    elif n_rounds >= 2:
        score += 0.05
    else:
        reasons.append("Jumlah ronde terlalu pendek untuk menangkap perubahan opini.")

    # Data historis ML
    if n_samples_history >= 20:
        score += 0.1
    elif n_samples_history >= 10:
        score += 0.05
    elif n_samples_history >= 5:
        score += 0.02
    else:
        reasons.append("Data historis masih sedikit, prediksi berbasis aturan umum.")

    # Feedback labels
    if n_feedback_labels >= 5:
        score += 0.1
    elif n_feedback_labels >= 3:
        score += 0.05
    elif n_feedback_labels >= 1:
        score += 0.02

    # Sentiment variance — variance tinggi = opini terbelah = prediksi kurang pasti
    if sentiment_variance > 0.3:
        score -= 0.08
        reasons.append("Variansi sentimen tinggi, opini agen terbelah.")
    elif sentiment_variance < 0.05:
        score += 0.05
        reasons.append("Sentimen agen relatif seragam.")

    # Quality score
    score += (quality_score - 0.5) * 0.2

    score = max(0.0, min(1.0, round(score, 2)))

    if score >= 0.7:
        label = "tinggi"
    elif score >= 0.4:
        label = "sedang"
    else:
        label = "rendah"

    return {
        "score": score,
        "label": label,
        "alasan": reasons,
    }


def heuristic_predict(
    sentimen_agregat: dict[str, list[float]],
    n_agents: int,
    n_rounds: int,
    quality_score: float,
    events: Optional[list] = None,
    crowd_data: Optional[dict] = None,
) -> dict:
    """
    Prediksi skenario berbasis aturan (heuristic), tanpa ML.

    Strategi:
    1. Hitung proporsi agen berdasarkan posisi akhir (positif/negatif/netral)
    2. Deteksi polarisasi: jika ada split kuat antara positif dan negatif
    3. Deteksi konsensus: jika mayoritas (>60%) sepakat
    4. Default: Status Quo

    Returns:
        {
            "prediksi": {"Konsensus": int, "Polarisasi": int, "Status Quo": int},
            "reasoning": str,
            "source": "heuristic",
        }
    """
    if not sentimen_agregat:
        return {
            "prediksi": {"Konsensus": 33, "Polarisasi": 34, "Status Quo": 33},
            "confidence": {"score": 0.0, "label": "rendah", "alasan": ["Tidak ada data sentimen."]},
            "reasoning": "Tidak ada data sentimen — asumsi default.",
            "source": "heuristic",
            "crowd_integrated": bool(crowd_data),
        }

    # Ambil skor akhir tiap agen
    final_scores = {}
    for nama, tren in sentimen_agregat.items():
        if tren:
            final_scores[nama] = tren[-1]
        else:
            final_scores[nama] = 0.0

    if not final_scores:
        return {
            "prediksi": {"Konsensus": 33, "Polarisasi": 34, "Status Quo": 33},
            "confidence": {"score": 0.0, "label": "rendah", "alasan": ["Tidak ada data sentimen agen."]},
            "reasoning": "Semua agen tidak memiliki data sentimen.",
            "source": "heuristic",
            "crowd_integrated": bool(crowd_data),
        }

    total = len(final_scores)
    n_pos = sum(1 for s in final_scores.values() if s > 0.2)
    n_neg = sum(1 for s in final_scores.values() if s < -0.2)
    n_net = total - n_pos - n_neg

    pct_pos = n_pos / total if total else 0
    pct_neg = n_neg / total if total else 0
    pct_net = n_net / total if total else 0

    reasoning_parts: list[str] = []

    # ── Phase 3: Crowd integration (bobot 30%) ──
    if crowd_data:
        crowd_dist = crowd_data.get("distribution", {})
        crowd_mendukung = crowd_dist.get("mendukung", 0) or 0
        crowd_menolak = crowd_dist.get("menolak", 0) or 0
        crowd_netral = crowd_dist.get("netral", 0) or 0
        total_crowd = crowd_mendukung + crowd_menolak + crowd_netral
        if total_crowd > 0:
            crowd_pct_pos = crowd_mendukung / total_crowd
            crowd_pct_neg = crowd_menolak / total_crowd
            crowd_pct_net = crowd_netral / total_crowd
            # Blend: 70% LLM agents, 30% crowd
            pct_pos = round(pct_pos * 0.7 + crowd_pct_pos * 0.3, 4)
            pct_neg = round(pct_neg * 0.7 + crowd_pct_neg * 0.3, 4)
            pct_net = round(pct_net * 0.7 + crowd_pct_net * 0.3, 4)
            # Recount for reasoning
            blended_total = 100  # normalize to percentage scale
            n_pos = int(pct_pos * blended_total)
            n_neg = int(pct_neg * blended_total)
            n_net = int(pct_net * blended_total)
            total = blended_total
            reasoning_parts.append(f"Data crowd diintegrasikan (30% bobot).")

    # Hitung variance sentimen
    all_scores = list(final_scores.values())
    variance = statistics.variance(all_scores) if len(all_scores) > 1 else 0.0

    # Heuristic rules
    prediksi: dict[str, int] = {}

    if n_events := len(events or []):
        reasoning_parts.append(f"Terdapat {n_events} event selama simulasi.")

    if pct_pos >= 0.6:
        # Konsensus positif
        prediksi = {"Konsensus": 65, "Polarisasi": 15, "Status Quo": 20}
        reasoning_parts.append(
            f"Mayoritas agen ({n_pos}/{total}) mendukung topik — "
            f"konsensus terdeteksi."
        )
    elif pct_neg >= 0.5 or variance > 0.3:
        # Polarisasi
        prediksi = {"Konsensus": 15, "Polarisasi": 65, "Status Quo": 20}
        if pct_neg >= 0.5:
            reasoning_parts.append(
                f"Mayoritas agen ({n_neg}/{total}) menolak topik."
            )
        if variance > 0.3:
            reasoning_parts.append(
                f"Variansi sentimen tinggi ({variance:.2f}) — "
                f"opini agen sangat terbelah."
            )
    elif pct_net >= 0.6:
        # Status Quo
        prediksi = {"Konsensus": 20, "Polarisasi": 15, "Status Quo": 65}
        reasoning_parts.append(
            f"Mayoritas agen ({n_net}/{total}) netral — "
            f"belum ada pergerakan opini yang signifikan."
        )
    else:
        # Mixed — condong ke Status Quo
        prediksi = {"Konsensus": 25, "Polarisasi": 25, "Status Quo": 50}
        reasoning_parts.append(
            f"Posisi agen terbagi: {n_pos} mendukung, {n_neg} menolak, "
            f"{n_net} netral — skenario paling mungkin adalah status quo."
        )

    # Confidence
    confidence = compute_confidence(
        n_agents=n_agents,
        n_rounds=n_rounds,
        n_samples_history=0,
        n_feedback_labels=0,
        sentiment_variance=variance,
        quality_score=quality_score,
    )

    return {
        "prediksi": prediksi,
        "confidence": confidence,
        "reasoning": " ".join(reasoning_parts) if reasoning_parts else "Prediksi berbasis distribusi sentimen akhir.",
        "source": "heuristic",
        "crowd_integrated": bool(crowd_data),
    }
