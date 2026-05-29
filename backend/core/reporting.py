# backend/core/reporting.py
# Phase 8: Explainability Report — kenapa hasilnya begitu?
# Pure Python (0 LLM call), hanya memanfaatkan data yang sudah ada.

from __future__ import annotations

from .metrics import compute_polarization, compute_volatility, compute_conflict_score


def _label_skor(skor: float) -> str:
    if skor > 0.2:
        return "mendukung"
    if skor < -0.2:
        return "menolak"
    return "netral"


def _skenario_tertinggi(prediksi: dict) -> str:
    if not prediksi:
        return "tidak dapat ditentukan"
    return max(prediksi, key=prediksi.get)


def _analisis_penyebab(sentimen_agregat: dict, aktor_analisis: dict) -> list[str]:
    """Analisis penyebab hasil diskusi berdasarkan data."""
    sebab: list[str] = []

    # Analisis siapa yang dominan
    aktor_kunci = (aktor_analisis or {}).get("aktor_kunci", [])
    if aktor_kunci:
        dominan = aktor_kunci[0]
        nama = dominan.get("nama", "?")
        sikap = dominan.get("sikap_label", "netral")
        sebab.append(
            f"Aktor paling berpengaruh adalah {nama} yang cenderung {sikap.lower()} "
            f"(bobot pengaruh {dominan.get('pengaruh_skor', 0.5):.0%})."
        )

    # Analisis swing voter
    swing = (aktor_analisis or {}).get("swing_voter", [])
    if swing:
        nama_swing = [s.get("nama", "?") for s in swing[:2]]
        sebab.append(
            f"Beberapa agen masih bisa berubah: {', '.join(nama_swing)} "
            f"menunjukkan volatilitas tinggi."
        )

    return sebab if sebab else ["Data belum cukup untuk analisis penyebab."]


def _analisis_konflik(sentimen_agregat: dict) -> str:
    """Analisis konflik antar agen."""
    skor_akhir = {}
    for nama, tren in sentimen_agregat.items():
        if tren:
            skor_akhir[nama] = tren[-1]

    positif = {n: s for n, s in skor_akhir.items() if s > 0.2}
    negatif = {n: s for n, s in skor_akhir.items() if s < -0.2}
    netral_len = len(skor_akhir) - len(positif) - len(negatif)

    if positif and negatif:
        return (
            f"Terjadi polarisasi: {len(positif)} agen mendukung "
            f"({', '.join(positif.keys())}) vs {len(negatif)} agen menolak "
            f"({', '.join(negatif.keys())})."
        )
    if positif:
        return f"Mayoritas mendukung: {len(positif)} agen ({', '.join(positif.keys())})."
    if negatif:
        return f"Mayoritas menolak: {len(negatif)} agen ({', '.join(negatif.keys())})."
    return "Semua agen cenderung netral — belum ada pergerakan berarti."


def _analisis_event(events: list) -> list[str]:
    """Analisis dampak event/intervensi."""
    if not events:
        return []
    hasil: list[str] = []
    for e in events:
        deskripsi = getattr(e, "deskripsi", e.get("deskripsi", "")) if isinstance(e, dict) else e.deskripsi
        ronde = getattr(e, "ronde", e.get("ronde", 0)) if isinstance(e, dict) else e.ronde
        dampak = getattr(e, "actual_impacts", e.get("actual_impacts", {})) if isinstance(e, dict) else e.actual_impacts
        if dampak:
            agen_terdampak = [f"{n}({s:+.2f})" for n, s in dampak.items() if abs(s) > 0.1]
            if agen_terdampak:
                hasil.append(
                    f"Intervensi ronde {ronde}: '{deskripsi[:60]}' — "
                    f"berdampak pada {', '.join(agen_terdampak[:4])}."
                )
    return hasil


def generate_report(hasil: dict) -> dict:
    """
    Generate laporan explainability dari hasil simulasi.

    Args:
        hasil: Dict return dari run_simulation().

    Returns:
        Dict dengan field:
        - ringkasan: str — paragraf pendek
        - penyebab: list[str] — analisis sebab-akibat
        - konflik: str — analisis konflik
        - aktor: list[str] — analisis aktor
        - events: list[str] — dampak event
        - keyakinan: str — confidence note
        - disclaimer: str
    """
    sentimen_agregat = hasil.get("sentimen_agregat", {})
    aktor_analisis = hasil.get("aktor_analisis", {})
    prediksi = hasil.get("prediksi", {})
    events = hasil.get("events", [])
    confidence = hasil.get("prediction_confidence", 0.0)
    reasoning = hasil.get("prediction_reasoning", "")

    # Metrics
    polarization = compute_polarization(sentimen_agregat)
    conflict = compute_conflict_score(sentimen_agregat)
    volatility = compute_volatility(sentimen_agregat)

    # Ringkasan
    skenario = _skenario_tertinggi(prediksi)
    ringkasan = (
        f"Simulasi ini menghasilkan skenario '{skenario}' "
        f"(polarisasi {polarization:.0%}, konflik {conflict:.0%}). "
    )

    if polarization > 0.5:
        ringkasan += "Pendapat agen sangat terpecah — tidak ada titik temu yang jelas."
    elif polarization > 0.2:
        ringkasan += "Ada perbedaan pendapat, tapi masih ada ruang untuk dialog."
    else:
        ringkasan += "Sebagian besar agen sepakat — diskusi cenderung homogen."

    # Penyebab
    penyebab = _analisis_penyebab(sentimen_agregat, aktor_analisis)

    # Analisis konflik
    konflik = _analisis_konflik(sentimen_agregat)

    # Analisis aktor
    aktor_list: list[str] = []
    penggerak = (aktor_analisis or {}).get("aktor_penggerak")
    rekomendasi = (aktor_analisis or {}).get("rekomendasi")
    if penggerak:
        aktor_list.append(f"Aktor penggerak: {penggerak}.")
    if rekomendasi:
        aktor_list.append(f"Rekomendasi: {rekomendasi}")

    swing = (aktor_analisis or {}).get("swing_voter", [])
    if swing:
        volatile_names = [
            f"{s['nama']} (volatilitas {volatility.get(s['nama'], 0):.2f})"
            for s in swing if s.get("nama") in volatility
        ]
        if volatile_names:
            aktor_list.append(f"Agen dengan perubahan tertinggi: {', '.join(volatile_names[:3])}.")

    # Dampak event
    event_list = _analisis_event(events)

    # Keyakinan
    keyakinan = (
        f"Keyakinan sistem: {confidence:.0%}. "
        f"{reasoning[:200] if reasoning else 'Prediksi berdasarkan distribusi sentimen akhir agen.'}"
    )

    return {
        "ringkasan": ringkasan,
        "penyebab": penyebab,
        "konflik": konflik,
        "aktor": aktor_list,
        "events": event_list,
        "keyakinan": keyakinan,
        "disclaimer": (
            "Ini adalah simulasi eksploratif, bukan prediksi faktual. "
            "Hasil sangat bergantung pada konfigurasi agen dan topik yang diberikan. "
            "Gunakan sebagai bahan pertimbangan, bukan keputusan final."
        ),
    }
