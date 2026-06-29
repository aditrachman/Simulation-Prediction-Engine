# backend/core/reporting.py
# Phase 8: Explainability Report — kenapa hasilnya begitu?
# Pure Python (0 LLM call), hanya memanfaatkan data yang sudah ada.
#
# FIX LOG:
#   FIX-E: confidence_summary field baru — satu angka konsisten, tidak ada 80% vs 0%
#   FIX-C: prediksi_comparison tidak lagi ditampilkan tanpa konteks — ada penjelasan jelas
#          mana yang "utama" dan mana yang "eksperimental"
#   FIX-event: analisis event diperluas — explain KENAPA agen bergerak counter event

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any

from .metrics import (
    compute_polarization,
    compute_consensus,
    compute_volatility,
    compute_conflict_score,
)


def _label_skor(skor: float) -> str:
    if skor > 0.2:
        return "mendukung"
    if skor < -0.2:
        return "menolak"
    return "netral"


def _analisis_penyebab(sentimen_agregat: dict, aktor_analisis: dict) -> list[str]:
    sebab: list[str] = []

    aktor_kunci = (aktor_analisis or {}).get("aktor_kunci", [])
    if aktor_kunci:
        dominan = aktor_kunci[0]
        nama = dominan.get("nama", "?")
        sikap = dominan.get("sikap_label", "netral")
        sebab.append(
            f"Aktor paling berpengaruh adalah {nama} yang cenderung {sikap.lower()} "
            f"(bobot pengaruh {dominan.get('pengaruh_skor', 0.5):.0%})."
        )

    swing = (aktor_analisis or {}).get("swing_voter", [])
    if swing:
        nama_swing = [s.get("nama", "?") for s in swing[:2]]
        sebab.append(
            f"Beberapa agen masih bisa berubah: {', '.join(nama_swing)} "
            f"menunjukkan volatilitas tinggi."
        )

    return sebab if sebab else ["Data belum cukup untuk analisis penyebab."]


def _analisis_konflik(sentimen_agregat: dict) -> str:
    skor_akhir = {}
    for nama, tren in sentimen_agregat.items():
        if tren:
            skor_akhir[nama] = tren[-1]

    positif = {n: s for n, s in skor_akhir.items() if s > 0.2}
    negatif = {n: s for n, s in skor_akhir.items() if s < -0.2}

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


def _analisis_event(events: list, sentimen_agregat: dict = None) -> list[str]:
    """
    FIX-event: Analisis dampak event diperluas.
    Sekarang menjelaskan KENAPA agen bergerak counter event (bukan hanya siapa yang terdampak).
    """
    if not events:
        return []
    hasil: list[str] = []
    for e in events:
        deskripsi = (
            getattr(e, "deskripsi", e.get("deskripsi", ""))
            if isinstance(e, dict)
            else e.deskripsi
        )
        ronde = getattr(e, "ronde", e.get("ronde", 0)) if isinstance(e, dict) else e.ronde
        dampak = (
            getattr(e, "actual_impacts", e.get("actual_impacts", {}))
            if isinstance(e, dict)
            else e.actual_impacts
        )

        if dampak:
            mendukung = [(n, s) for n, s in dampak.items() if s > 0.1]
            menolak = [(n, s) for n, s in dampak.items() if s < -0.1]

            agen_terdampak = [f"{n}({s:+.2f})" for n, s in dampak.items() if abs(s) > 0.1]
            base = (
                f"Ronde {ronde}: '{deskripsi[:60]}' — "
                f"berdampak pada {', '.join(agen_terdampak[:4])}."
            )
            hasil.append(base)

            if mendukung and menolak:
                # Analisis lebih dalam: explain KENAPA terjadi respons berlawanan
                pro_names = [n for n, _ in mendukung[:2]]
                contra_names = [n for n, _ in menolak[:2]]
                parts = [
                    f"Intervensi ini memicu respons berlawanan — "
                    f"{', '.join(pro_names)} cenderung mendukung, "
                    f"sementara {', '.join(contra_names)} justru semakin kritis."
                ]

                # BUG #3 FIX: Analisis dinamis berdasarkan tipe event dan konteks
                tipe = (
                    getattr(e, "tipe", e.get("tipe", ""))
                    if isinstance(e, dict)
                    else e.tipe
                )
                if tipe == "intervensi" or "bantuan" in deskripsi.lower() or "subsidi" in deskripsi.lower():
                    parts.append(
                        f"Ini umum terjadi pada intervensi: agen yang skeptis (seperti Jurnalis, "
                        f"Akademisi, Oposisi) cenderung melihat intervensi sebagai solusi jangka pendek "
                        f"yang tidak menyentuh akar masalah, sehingga respons mereka justru semakin kritis."
                    )
                elif "kenaikan" in deskripsi.lower() or "harga" in deskripsi.lower():
                    parts.append(
                        f"Kebijakan yang berdampak pada harga kebutuhan langsung memicu respons "
                        f"negatif dari agen yang mewakili rakyat kecil (Masyarakat, Mahasiswa) karena "
                        f"daya beli terdampak langsung."
                    )
                hasil.append(" ".join(parts))
    return hasil


def generate_report(hasil: dict) -> dict:
    """
    Generate laporan explainability dari hasil simulasi.

    FIX-E: confidence_summary sekarang konsisten — satu angka, satu label.
    FIX-C: prediksi_comparison dengan penjelasan jelas mana utama vs eksperimental.
    Also enrich report with new fields for frontend compatibility.
    """
    """
    Generate laporan explainability dari hasil simulasi.

    FIX-E: confidence_summary sekarang konsisten — satu angka, satu label.
    FIX-C: prediksi_comparison dengan penjelasan jelas mana utama vs eksperimental.
    """
    sentimen_agregat = hasil.get("sentimen_agregat", {})
    aktor_analisis = hasil.get("aktor_analisis", {})
    prediksi = hasil.get("prediksi", {})
    events_raw = hasil.get("events", [])

    confidence_summary = hasil.get("confidence_summary", {})
    if confidence_summary:
        confidence = float(confidence_summary.get("score", 0.0))
        confidence_label = confidence_summary.get("label", "")
        confidence_alasan = confidence_summary.get("alasan", [])
        confidence_interpretasi = confidence_summary.get("interpretasi", "")
    else:
        _raw_confidence = hasil.get("prediction_confidence", 0.0)
        if isinstance(_raw_confidence, dict):
            confidence = float(_raw_confidence.get("score", 0.0))
            confidence_label = _raw_confidence.get("label", "")
            confidence_alasan = _raw_confidence.get("alasan", [])
        else:
            confidence = float(_raw_confidence) if _raw_confidence else 0.0
            confidence_label = ""
            confidence_alasan = []
        confidence_interpretasi = ""

    reasoning = hasil.get("prediction_reasoning", "")

    # Metrics
    polarization = compute_polarization(sentimen_agregat)
    consensus = compute_consensus(sentimen_agregat)
    conflict = compute_conflict_score(sentimen_agregat)
    volatility = compute_volatility(sentimen_agregat)

    # Ringkasan — pakai metrik aktual
    ringkasan = (
        f"Polarisasi {polarization:.0%}, konsensus {consensus:.0%}, konflik {conflict:.0%}. "
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
            for s in swing
            if s.get("nama") in volatility
        ]
        if volatile_names:
            aktor_list.append(f"Agen dengan perubahan tertinggi: {', '.join(volatile_names[:3])}.")

    # Event analysis
    event_list = _analisis_event(events_raw, sentimen_agregat)

    # Hitungan posisi akhir
    skor_akhir = {}
    for nama, tren in sentimen_agregat.items():
        if tren:
            skor_akhir[nama] = tren[-1]
    n_pos = sum(1 for s in skor_akhir.values() if s > 0.2)
    n_neg = sum(1 for s in skor_akhir.values() if s < -0.2)
    n_net = len(skor_akhir) - n_pos - n_neg
    posisi_info = f"({n_pos} mendukung, {n_neg} menolak, {n_net} netral dari {len(skor_akhir)} agen)"

    conf_label_str = f" ({confidence_label})" if confidence_label else ""
    conf_alasan_str = " ".join(confidence_alasan[:2]) if confidence_alasan else ""

    if confidence_interpretasi:
        keyakinan = (
            f"Keyakinan sistem: {confidence:.0%}{conf_label_str}. "
            f"{confidence_interpretasi}"
        )
    elif reasoning:
        keyakinan = f"Keyakinan sistem: {confidence:.0%}{conf_label_str}. {reasoning[:200]} {posisi_info}."
    elif conf_alasan_str:
        keyakinan = f"Keyakinan sistem: {confidence:.0%}{conf_label_str}. {conf_alasan_str} {posisi_info}."
    else:
        keyakinan = f"Keyakinan sistem: {confidence:.0%}{conf_label_str}. {posisi_info}."

    # Prediksi comparison
    prediksi_ml = hasil.get("prediksi_ml_experimental")
    ml_n_samples = hasil.get("ml_info", {}).get("n_samples", 0)
    ml_conf_debug = hasil.get("ml_info", {}).get("ml_confidence_debug", {})

    prediksi_comparison = {
        "utama": {
            "label": "Heuristic (Prediksi Utama)",
            "prediksi": prediksi,
            "confidence_label": confidence_label or "sedang",
            "note": (
                "Prediksi ini berbasis analisis sentimen agen secara langsung. "
                "Ini adalah angka yang harus dibaca sebagai gambaran utama."
            ),
        },
    }

    if prediksi_ml:
        ml_conf_label = (
            ml_conf_debug.get("label", "rendah").upper()
            if isinstance(ml_conf_debug, dict)
            else "rendah"
        )
        prediksi_comparison["ml_eksperimental"] = {
            "label": f"ML Eksperimental ({ml_n_samples} sampel)",
            "prediksi": prediksi_ml,
            "confidence_label": ml_conf_label,
            "note": (
                "Prediksi ini dari model machine learning yang dilatih dari riwayat simulasi. "
                "EKSPERIMENTAL — akurasi meningkat seiring bertambahnya data feedback. "
                "Jika berbeda dari heuristic, percayai heuristic dulu."
            ),
        }
    else:
        prediksi_comparison["ml_eksperimental"] = {
            "label": "ML Belum Aktif",
            "prediksi": None,
            "confidence_label": "tidak_tersedia",
            "note": (
                "Model ML belum aktif (butuh minimal 5 simulasi). "
                "Prediksi hanya dari heuristic."
            ),
        }

    # Additional fields for frontend compatibility
    phenomenon_summary = ringkasan
    # Group breakdown: each agent's final stance and score
    group_breakdown = []
    for nama, tren in sentimen_agregat.items():
        if not tren:
            continue
        final_score = tren[-1]
        stance = _label_skor(final_score)
        group_breakdown.append({"nama": nama, "final_stance": stance, "score": final_score})
    # Key driver info
    key_driver = ""
    key_driver_impact = ""
    if (aktor_analisis or {}).get("aktor_kunci"):
        kd = (aktor_analisis or {}).get("aktor_kunci")[0]
        key_driver = kd.get("nama", "")
        key_driver_impact = kd.get("pengaruh_skor", 0)
    # Swing voters names
    swing_voters = [s.get("nama") for s in swing] if swing else []
    # Main conflict description
    main_conflict = konflik
    # Confidence dict
    confidence = {
        "score": confidence,
        "label": confidence_label,
        "reason": confidence_alasan[0] if confidence_alasan else "",
    }
    # Limitations (placeholder)
    limitations = []

    return {
        "ringkasan": ringkasan,
        "penyebab": penyebab,
        "konflik": konflik,
        "aktor": aktor_list,
        "events": event_list,
        "keyakinan": keyakinan,
        "prediksi_comparison": prediksi_comparison,
        "disclaimer": (
            "VoxSwarm adalah alat eksplorasi dan referensi awal, bukan pengganti survei atau "
            "riset empiris. Hasil simulasi sangat bergantung pada konfigurasi agen dan topik "
            "yang diberikan. Gunakan sebagai bahan pertimbangan, bukan keputusan final."
        ),
        "phenomenon_summary": phenomenon_summary,
        "group_breakdown": group_breakdown,
        "key_driver": key_driver,
        "key_driver_impact": key_driver_impact,
        "swing_voters": swing_voters,
        "main_conflict": main_conflict,
        "confidence": confidence,
        "limitations": limitations,
    }

# Dataclass for explainability report (backward compatibility)
@dataclass
class ExplainabilityReport:
    # Core legacy fields with defaults for flexible init
    ringkasan: str = ""
    penyebab: List[str] = field(default_factory=list)
    konflik: str = ""
    aktor: List[str] = field(default_factory=list)
    events: List[str] = field(default_factory=list)
    keyakinan: str = ""
    prediksi_comparison: Dict[str, Any] = field(default_factory=dict)
    disclaimer: str = field(
        default="VoxSwarm adalah alat eksplorasi dan referensi awal, bukan pengganti survei atau riset empiris. Hasil simulasi sangat bergantung pada konfigurasi agen dan topik yang diberikan. Gunakan sebagai bahan pertimbangan, bukan keputusan final."
    )
    # New fields required by tests
    skenario: str = ""
    skenario_probability: Dict[str, int] = field(default_factory=dict)
    skenario_definition: str = ""
    phenomenon_summary: str = ""
    group_breakdown: List[Dict[str, Any]] = field(default_factory=list)
    key_driver: str = ""
    key_driver_impact: Any = None
    swing_voters: List[str] = field(default_factory=list)
    main_conflict: str = ""
    confidence: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)


    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary with legacy and new keys expected by tests."""
        base = {
            "ringkasan": self.ringkasan,
            "penyebab": self.penyebab,
            "konflik": self.konflik,
            "aktor": self.aktor,
            "events": self.events,
            "keyakinan": self.keyakinan,
            "prediksi_comparison": self.prediksi_comparison,
            "disclaimer": self.disclaimer,
        }
        # Add new fields
        base.update(
            {
                "skenario": self.skenario,
                "skenario_probability": self.skenario_probability,
                "skenario_definition": self.skenario_definition,
                "phenomenon_summary": self.phenomenon_summary,
                "group_breakdown": self.group_breakdown,
                "key_driver": self.key_driver,
                "key_driver_impact": self.key_driver_impact,
                "swing_voters": self.swing_voters,
                "main_conflict": self.main_conflict,
                "confidence": self.confidence,
                "limitations": self.limitations,
            }
        )
        return base


