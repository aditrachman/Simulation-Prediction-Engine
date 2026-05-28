# backend/core/swarm.py
# Phase 8: Swarm-lite — rule-based crowd agents yang reaktif terhadap LLM agents.
# Murah (0 LLM call), scalable (50-200 agents).

from __future__ import annotations

import math
import random
import statistics
from typing import Optional


# ---------------------------------------------------------------------------
# CrowdAgent — satu agen rule-based
# ---------------------------------------------------------------------------

class CrowdAgent:
    """Satu agen dalam crowd. Stance dihitung dari aturan, bukan LLM."""

    def __init__(
        self,
        nama: str,
        group: str,
        initial_stance: float,
        susceptibility: float,
    ):
        self.nama = nama
        self.group = group
        self.initial_stance = initial_stance
        self.current_stance = initial_stance
        self.susceptibility = susceptibility
        self.history: list[float] = [initial_stance]

    @property
    def stance_label(self) -> str:
        if self.current_stance > 0.2:
            return "mendukung"
        if self.current_stance < -0.2:
            return "menolak"
        return "netral"

    def to_dict(self) -> dict:
        return {
            "nama": self.nama,
            "group": self.group,
            "initial_stance": round(self.initial_stance, 2),
            "current_stance": round(self.current_stance, 2),
            "stance_label": self.stance_label,
            "susceptibility": round(self.susceptibility, 2),
            "history": [round(s, 2) for s in self.history],
        }


# ---------------------------------------------------------------------------
# CrowdPool — kumpulan crowd agents dengan logika propagasi
# ---------------------------------------------------------------------------

# Distribusi grup untuk crowd, mirip proporsi demografi Indonesia
GROUP_WEIGHTS: dict[str, float] = {
    "mahasiswa":     0.15,
    "pekerja":       0.30,
    "umkm":          0.12,
    "masyarakat":    0.25,
    "akademisi":     0.05,
    "media":         0.03,
    "oposisi":       0.10,
}

# Mapping dari grup crowd ke LLM agent yang paling relevan
GROUP_LLM_AFFINITY: dict[str, str] = {
    "mahasiswa":  "Mahasiswa",
    "pekerja":    "Pekerja Kantoran",
    "umkm":       "Pengusaha/UMKM",
    "masyarakat": "Masyarakat Umum",
    "akademisi":  "Akademisi",
    "media":      "Jurnalis/Media",
    "oposisi":    "Oposisi Kritis",
}


def _generate_stance(group: str, rng: random.Random) -> float:
    """Generate initial stance based on group tendency."""
    tendencies = {
        "mahasiswa":  random.gauss(0.0, 0.3),
        "pekerja":    random.gauss(-0.1, 0.25),
        "umkm":       random.gauss(-0.05, 0.25),
        "masyarakat": random.gauss(0.0, 0.2),
        "akademisi":  random.gauss(0.0, 0.15),
        "media":      random.gauss(0.0, 0.2),
        "oposisi":    random.gauss(-0.3, 0.3),
    }
    s = tendencies.get(group, random.gauss(0.0, 0.3))
    return max(-1.0, min(1.0, s))


def _generate_susceptibility(group: str, rng: random.Random) -> float:
    """Generate susceptibility based on group traits."""
    base = {
        "mahasiswa":  0.6,
        "pekerja":    0.4,
        "umkm":       0.5,
        "masyarakat": 0.7,
        "akademisi":  0.2,
        "media":      0.3,
        "oposisi":    0.3,
    }
    b = base.get(group, 0.5)
    return max(0.0, min(1.0, b + random.gauss(0, 0.15)))


class CrowdPool:
    """Pool of rule-based crowd agents."""

    def __init__(self, seed: int = 42):
        self.agents: list[CrowdAgent] = []
        self._rng = random.Random(seed)

    def generate(self, n: int = 100) -> None:
        """Generate n crowd agents dengan distribusi grup demografis."""
        self.agents = []
        groups = list(GROUP_WEIGHTS.keys())
        weights = [GROUP_WEIGHTS[g] for g in groups]

        for i in range(n):
            group = self._rng.choices(groups, weights=weights, k=1)[0]
            agent = CrowdAgent(
                nama=f"Crowd-{i+1}",
                group=group,
                initial_stance=_generate_stance(group, self._rng),
                susceptibility=_generate_susceptibility(group, self._rng),
            )
            self.agents.append(agent)

    def update_from_llm_agents(
        self,
        llm_agents: list[dict],
        round_number: int,
    ) -> None:
        """
        Update stance semua crowd agent berdasarkan LLM agents.

        Rumus propagasi (sederhana):
        - Tiap crowd agent punya affinity ke 1 LLM agent (berdasarkan grup)
        - Stance baru = stance_lama + susceptibility * (stance_affinity - stance_lama) * 0.3

        Args:
            llm_agents: List dict agen LLM (harus punya "nama", "sentimen.skor")
            round_number: Ronde saat ini (untuk history tracking)
        """
        # Build influence map: {nama_llm: skor_sentimen}
        llm_map: dict[str, float] = {}
        for a in llm_agents:
            skor = a.get("sentimen", {}).get("skor", 0.0) or 0.0
            llm_map[a["nama"]] = skor

        for crowd in self.agents:
            # Temukan LLM agent yang paling relevan untuk grup ini
            affinity_name = GROUP_LLM_AFFINITY.get(crowd.group)
            affinity_stance = llm_map.get(affinity_name, 0.0)

            # Jika tidak ada affinity, pakai rata-rata semua LLM agents
            if affinity_stance == 0.0 and llm_map:
                affinity_stance = statistics.mean(llm_map.values())

            # Propagasi: crowd bergerak menuju affinity LLM
            delta = crowd.susceptibility * (affinity_stance - crowd.current_stance) * 0.3
            crowd.current_stance = max(-1.0, min(1.0, crowd.current_stance + delta))
            crowd.history.append(crowd.current_stance)

    def get_distribution(self) -> dict[str, float]:
        """Distribusi stance crowd saat ini: proporsi mendukung/menolak/netral."""
        if not self.agents:
            return {"mendukung": 0, "netral": 0, "menolak": 0}
        n = len(self.agents)
        pos = sum(1 for a in self.agents if a.current_stance > 0.2)
        neg = sum(1 for a in self.agents if a.current_stance < -0.2)
        net = n - pos - neg
        return {
            "mendukung": round(pos / n * 100, 1),
            "netral":    round(net / n * 100, 1),
            "menolak":   round(neg / n * 100, 1),
        }

    def get_clusters(self, n_clusters: int = 3) -> list[dict]:
        """
        Klasterisasi sederhana crowd agents berdasarkan stance.
        Bagi menjadi n_clusters grup (pro, netral, kontra).
        """
        if not self.agents:
            return []

        sorted_agents = sorted(self.agents, key=lambda a: a.current_stance)
        chunk_size = max(1, len(sorted_agents) // n_clusters)
        clusters = []

        for i in range(n_clusters):
            chunk = sorted_agents[i * chunk_size:(i + 1) * chunk_size]
            if not chunk:
                continue
            mean_stance = statistics.mean(a.current_stance for a in chunk)
            clusters.append({
                "label": "mendukung" if mean_stance > 0.2 else "menolak" if mean_stance < -0.2 else "netral",
                "size": len(chunk),
                "mean_stance": round(mean_stance, 2),
                "top_groups": self._top_groups(chunk),
            })

        return clusters

    def get_propagation_graph(self) -> list[dict]:
        """
        Graf propagasi sederhana: LLM agents → grup crowd.
        Returns list of edges: {from: nama_llm, to: group, weight: influence_strength}
        """
        if not self.agents:
            return []

        # Hitung rata-rata stance per grup crowd
        group_stances: dict[str, list[float]] = {}
        for a in self.agents:
            if a.group not in group_stances:
                group_stances[a.group] = []
            group_stances[a.group].append(a.current_stance)

        edges = []
        for group, stances in group_stances.items():
            affinity_name = GROUP_LLM_AFFINITY.get(group, "-")
            mean_s = statistics.mean(stances)
            edges.append({
                "from": affinity_name,
                "to": group,
                "weight": round(abs(mean_s), 2),
                "crowd_size": len(stances),
                "mean_stance": round(mean_s, 2),
            })

        return edges

    def to_dict(self) -> dict:
        """Full serialization untuk response API."""
        return {
            "total": len(self.agents),
            "distribution": self.get_distribution(),
            "clusters": self.get_clusters(),
            "propagation_graph": self.get_propagation_graph(),
            "agents": [a.to_dict() for a in self.agents],
        }

    @staticmethod
    def _top_groups(agents: list[CrowdAgent], top_n: int = 3) -> list[dict]:
        """Top N grup dalam satu cluster."""
        group_count: dict[str, int] = {}
        for a in agents:
            group_count[a.group] = group_count.get(a.group, 0) + 1
        sorted_groups = sorted(group_count.items(), key=lambda x: -x[1])
        return [
            {"group": g, "count": c}
            for g, c in sorted_groups[:top_n]
        ]
