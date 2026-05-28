# backend/core/event_system.py
# Phase 3: Event System — intervensi sebagai object proper dengan impact scoring.

from __future__ import annotations

from typing import Optional
from .models import SimulationEvent


# Default impact per event type, based on agent archetypes.
# Positive = push toward mendukung, negative = push toward menolak.
_DEFAULT_IMPACTS: dict[str, dict[str, float]] = {
    "intervensi": {
        "Pemerintah": 0.25,
        "Mahasiswa": -0.15,
        "Oposisi Kritis": -0.25,
        "Jurnalis": -0.1,
        "Masyarakat": -0.1,
    },
    "berita_baru": {
        "Jurnalis": 0.25,
        "Akademisi": 0.2,
        "Mahasiswa": 0.15,
    },
    "pernyataan_pemerintah": {
        "Pemerintah": 0.2,
        "Oposisi Kritis": -0.2,
        "Jurnalis": -0.1,
    },
    "protes": {
        "Mahasiswa": 0.25,
        "Oposisi Kritis": 0.3,
        "Pemerintah": -0.2,
        "Masyarakat": 0.1,
    },
    "eksternal": {},
}


def compute_event_impact(
    event: SimulationEvent,
    agent_names: list[str],
) -> dict[str, float]:
    """
    Hitung impact event terhadap setiap agen.

    Strategy (sederhana):
      1. Start dari dampak_hint (jika disediakan user)
      2. Fallback ke default impact per tipe event
      3. Agen tanpa impact explicit mendapat 0.0

    Returns {nama_agen: impact_score}
    """
    impacts: dict[str, float] = {}

    # Prioritaskan hint dari user
    if event.dampak_hint:
        for name, val in event.dampak_hint.items():
            if name in agent_names:
                impacts[name] = val

    # Fallback ke default untuk agen yang belum punya impact
    defaults = _DEFAULT_IMPACTS.get(event.tipe, {})
    for name in agent_names:
        if name not in impacts:
            impacts[name] = defaults.get(name, 0.0)

    return impacts


def build_event_narrative(
    event: SimulationEvent,
    impacts: dict[str, float],
) -> str:
    """
    Bangun teks narasi event untuk dimasukkan ke prompt agen.

    Returns string siap append ke system_prompt atau user_prompt.
    """
    lines = [f"INTERVENSI: {event.deskripsi}"]

    affected = [(n, s) for n, s in impacts.items() if abs(s) >= 0.1]
    if affected:
        affected.sort(key=lambda x: -abs(x[1]))
        detail = "; ".join(
            f"{n} cenderung {'mendukung' if s > 0 else 'menolak'} ({s:+.1f})"
            for n, s in affected
        )
        lines.append(f"Dampak: {detail}.")

    return "\n".join(lines)


def get_agent_impact_note(
    agent_name: str,
    impacts: dict[str, float],
) -> str:
    """
    Dapatkan catatan impact spesifik untuk satu agen.

    Returns string seperti:
      "Perhatikan: intervensi ini mendorongmu ke arah menolak (impact -0.25)."
    Atau string kosong jika impact = 0.
    """
    impact = impacts.get(agent_name, 0.0)
    if abs(impact) < 0.05:
        return ""

    arah = "mendukung" if impact > 0 else "menolak"
    return (
        f"Perhatikan dampak intervensi pada posisimu: "
        f"kamu cenderung {arah} (impact {impact:+.2f}). "
        f"Pertahankan atau sesuaikan argumenmu berdasarkan data, "
        f"bukan hanya karena intervensi."
    )


def generate_event_explanation(
    events: list[SimulationEvent],
    agent_names: list[str],
) -> list[dict]:
    """
    Generate explanation untuk semua event dalam simulasi.

    Returns list of dict:
      {
        "ronde": int,
        "deskripsi": str,
        "tipe": str,
        "terdampak": [{"nama": str, "impact": float, "arah": str}, ...],
      }
    """
    explanations = []
    for ev in events:
        impacts = ev.actual_impacts or compute_event_impact(ev, agent_names)
        terdampak = [
            {
                "nama": name,
                "impact": round(score, 2),
                "arah": "mendukung" if score > 0 else "menolak",
            }
            for name, score in sorted(impacts.items(), key=lambda x: -abs(x[1]))
            if abs(score) >= 0.1
        ]
        explanations.append({
            "ronde": ev.ronde,
            "deskripsi": ev.deskripsi,
            "tipe": ev.tipe,
            "terdampak": terdampak,
        })
    return explanations
