# backend/core/metrics.py
# Phase 8: Metrics formal — kalkulasi polarization, volatility, consensus, conflict score
# Semua fungsi pure Python (0 LLM call)

from __future__ import annotations

import statistics


def compute_polarization(sentimen_agregat: dict[str, list[float]]) -> float:
    """
    Skor polarisasi dari distribusi sentimen akhir agen.

    0.0 = semua agen setuju (konsensus penuh)
    1.0 = agen terbelah dua kutub ekstrem (-1 dan +1)

    Rumus: variansi dari stance_score akhir, dinormalisasi ke 0-1.
    """
    skor_akhir = _ambil_skor_akhir(sentimen_agregat)
    if len(skor_akhir) < 2:
        return 0.0
    mean = sum(skor_akhir) / len(skor_akhir)
    variance = sum((x - mean) ** 2 for x in skor_akhir) / len(skor_akhir)
    return round(min(variance, 1.0), 3)


def compute_consensus(sentimen_agregat: dict[str, list[float]]) -> float:
    """
    Skor konsensus — kebalikan dari polarisasi.

    1.0 = konsensus penuh (semua sepakat)
    0.0 = sangat terpolarisasi
    """
    return round(1.0 - compute_polarization(sentimen_agregat), 3)


def compute_volatility(sentimen_agregat: dict[str, list[float]]) -> dict[str, float]:
    """
    Volatilitas per agen — rata-rata perubahan stance absolut antar ronde.

    Returns:
        {nama_agen: skor_volatilitas}
        0.0 = sangat stabil, >0.5 = sering berubah pendapat
    """
    hasil: dict[str, float] = {}
    for nama, tren in sentimen_agregat.items():
        if len(tren) < 2:
            hasil[nama] = 0.0
        else:
            hasil[nama] = round(
                sum(abs(tren[i] - tren[i-1]) for i in range(1, len(tren))) / (len(tren) - 1),
                3,
            )
    return hasil


def compute_conflict_score(sentimen_agregat: dict[str, list[float]]) -> float:
    """
    Skor konflik — seberapa besar pertentangan antar agen.

    0.0 = tidak ada konflik (semua netral atau sepakat)
    1.0 = konflik maksimal (terbelah keras)

    Rumus: proporsi agen yang berseberangan dikali intensitas rata-rata.
    """
    skor_akhir = _ambil_skor_akhir(sentimen_agregat)
    if not skor_akhir:
        return 0.0

    n = len(skor_akhir)
    if n < 2:
        return 0.0

    # Hitung ada berapa pasangan yang berseberangan (positif vs negatif)
    positif = sum(1 for s in skor_akhir if s > 0.2)
    negatif = sum(1 for s in skor_akhir if s < -0.2)

    if positif == 0 or negatif == 0:
        return 0.0

    # Proporsi pasangan berseberangan
    proporsi_konflik = (positif / n) * (negatif / n) * 2  # max 0.5

    # Intensitas rata-rata stance
    intensitas = sum(abs(s) for s in skor_akhir) / n

    conflict = proporsi_konflik * intensitas * 2  # skala ke 0-1
    return round(min(conflict, 1.0), 3)


def _ambil_skor_akhir(sentimen_agregat: dict[str, list[float]]) -> list[float]:
    """Ambil skor sentimen ronde terakhir tiap agen."""
    skor = []
    for tren in sentimen_agregat.values():
        if tren:
            skor.append(tren[-1])
    return skor
