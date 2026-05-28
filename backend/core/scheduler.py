# backend/core/scheduler.py
# Phase 4: Scheduler — urutan bicara agen dan pemilihan target respons.
# Memisahkan logika scheduling dari simulation.py agar bisa di-test dan dikembangin terpisah.

from __future__ import annotations

import random
from typing import Optional


def get_speaking_order(
    agents: list[dict],
    ronde_ke: int,
    strategy: str = "influence_aware",
) -> list[int]:
    """
    Tentukan urutan bicara agen berdasarkan strategy.

    Args:
        agents: List dict agen (wajib punya field "pengaruh")
        ronde_ke: Nomor ronde saat ini (1-indexed)
        strategy:
            - "sequential":  Peringkat tetap berdasarkan influence (tertinggi duluan)
            - "randomized":  Acak dengan seed = ronde_ke (perilaku lama)
            - "influence_aware": Influence tinggi duluan, sisanya diacak

    Returns:
        List of index ke agents, dalam urutan bicara.
    """
    n = len(agents)
    if n <= 1:
        return list(range(n))

    if strategy == "sequential":
        # Urutkan berdasarkan influence descending
        indexed = sorted(
            enumerate(agents),
            key=lambda x: -float(x[1].get("pengaruh", 0.5)),
        )
        return [i for i, _ in indexed]

    if strategy == "randomized":
        indices = list(range(n))
        rng = random.Random(ronde_ke)
        rng.shuffle(indices)
        return indices

    # influence_aware (default)
    # Round 1: influence tinggi duluan -> biar framing topik ditentukan
    # Round 2+: acak dalam blok influence (cegah monoton)
    indexed = list(enumerate(agents))
    indexed.sort(key=lambda x: -float(x[1].get("pengaruh", 0.5)))

    threshold_high = max(1, n // 3)
    high_influence = [i for i, _ in indexed[:threshold_high]]
    low_influence = [i for i, _ in indexed[threshold_high:]]

    if ronde_ke == 1:
        # Round 1: high influence speaks first, then shuffle low
        rng = random.Random(ronde_ke)
        rng.shuffle(low_influence)
        return high_influence + low_influence

    # Round 2+: shuffle dalam blok
    rng = random.Random(ronde_ke)
    rng.shuffle(high_influence)
    rng.shuffle(low_influence)
    return high_influence + low_influence


def select_response_target(
    current_nama: str,
    agents: list[dict],
    ronde_ke: int,
    pendapat_dalam_ronde_ini: list[dict],
    pendapat_ronde_sebelumnya: list[dict],
    strategy: str = "influence_aware",
) -> Optional[str]:
    """
    Pilih agen yang harus di-respons oleh current_nama.

    Args:
        current_nama: Nama agen yang akan bicara
        agents: List semua agen (wajib punya "nama" dan "pengaruh")
        ronde_ke: Nomor ronde saat ini
        pendapat_dalam_ronde_ini: Agen yg sudah bicara di ronde ini
        pendapat_ronde_sebelumnya: Semua pendapat ronde lalu
        strategy:
            - "random": Acak dari yang sudah bicara
            - "influence_aware": Prioritaskan influence tinggi
            - "adversarial": Target agen dengan stance berlawanan

    Returns:
        Nama agen target, atau None jika tidak ada.
    """
    # Cari kandidat: agen yang sudah bicara selain current_nama
    candidates = []
    seen = set()

    # Prioritaskan yang baru bicara di ronde ini
    for entry in pendapat_dalam_ronde_ini:
        nama = entry.get("nama", "")
        if nama != current_nama and nama not in seen:
            candidates.append(nama)
            seen.add(nama)

    # Fallback ke ronde sebelumnya
    for entry in pendapat_ronde_sebelumnya:
        nama = entry.get("nama", "")
        if nama != current_nama and nama not in seen:
            candidates.append(nama)
            seen.add(nama)

    if not candidates:
        return None

    if strategy == "random":
        return candidates[0]  # Yang paling baru

    if strategy == "adversarial":
        # Cari sentimen berlawanan (jika ada data sentimen)
        current_sentimen = None
        for entry in pendapat_dalam_ronde_ini + pendapat_ronde_sebelumnya:
            if entry.get("nama") == current_nama:
                current_sentimen = entry.get("sentimen", {})
                break

        if current_sentimen:
            current_skor = current_sentimen.get("skor", 0.0)
            # Cari yang sentimennya paling berlawanan
            best_match = None
            best_diff = -1
            for entry in pendapat_dalam_ronde_ini + pendapat_ronde_sebelumnya:
                nama = entry.get("nama", "")
                if nama == current_nama:
                    continue
                other_skor = entry.get("sentimen", {}).get("skor", 0.0)
                diff = abs(current_skor - other_skor)
                if diff > best_diff:
                    best_diff = diff
                    best_match = nama
            if best_match:
                return best_match

        return candidates[0]

    # influence_aware (default): pilih yang influence paling tinggi
    nama_to_pengaruh = {a["nama"]: float(a.get("pengaruh", 0.5)) for a in agents}
    candidates.sort(key=lambda n: -nama_to_pengaruh.get(n, 0.5))
    return candidates[0]


def get_strategy_display(strategy: str) -> str:
    """Return human-readable label for a scheduler strategy."""
    labels = {
        "sequential": "Urutan tetap (influence)",
        "randomized": "Acak per ronde",
        "influence_aware": "Influence tinggi duluan",
    }
    return labels.get(strategy, strategy)
