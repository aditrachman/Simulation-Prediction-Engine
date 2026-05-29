# backend/core/state_engine.py
# Formal state management untuk simulasi multi-agen.
# Melacak state tiap agen per ronde, transisi state, dan timeline.
# Pure Python — 0 LLM call.

from __future__ import annotations

from typing import Optional

from .models import AgentState, SimulationState


class StateEngine:
    """
    State engine untuk simulasi multi-agen.

    Mengelola lifecycle state agen: inisialisasi → update per ronde → snapshot.
    Semua state disimpan sebagai AgentState, compat dengan SimulationState.

    Usage:
        engine = StateEngine(agents, topik, jumlah_ronde)
        engine.init_state()
        for ronde in range(jumlah_ronde):
            for agen in agents:
                engine.update_agent_state(agen["nama"], skor, pendapat, ronde)
        snapshot = engine.get_snapshot()
    """

    def __init__(self, agents: list[dict], topik: str = "", jumlah_ronde: int = 3):
        self.agent_states: dict[str, AgentState] = {}
        self.timeline: list[dict] = []
        self.topik = topik
        self.jumlah_ronde = jumlah_ronde

        for a in agents:
            nama = a.get("nama", "?")
            self.agent_states[nama] = AgentState(
                agent_nama=nama,
                role=a.get("role", ""),
                influence=a.get("pengaruh", 0.5),
                initial_stance=a.get("initial_stance", 0.0),
                sentiment_trajectory=[],
                stance_history=[],
            )

    def init_state(self):
        """Reset semua state ke awal."""
        for nama, state in self.agent_states.items():
            state.sentiment_trajectory = []
            state.stance_history = []
        self.timeline = []

    def update_agent_state(
        self,
        nama: str,
        skor: float,
        pendapat: str,
        ronde: int,
        label: str = "",
    ) -> Optional[AgentState]:
        """Update state satu agen setelah satu ronde."""
        state = self.agent_states.get(nama)
        if state is None:
            return None

        state.sentiment_trajectory.append(round(skor, 2))
        state.stance_history.append({
            "ronde": ronde,
            "skor": round(skor, 2),
            "label": label or ("positif" if skor > 0.2 else "negatif" if skor < -0.2 else "netral"),
            "pendapat": pendapat[:80],
        })
        state.current_stance = round(skor, 2)
        return state

    def get_agent_state(self, nama: str) -> Optional[AgentState]:
        return self.agent_states.get(nama)

    def get_snapshot(self) -> SimulationState:
        """Ambil snapshot state terkini sebagai SimulationState."""
        agent_states_list = list(self.agent_states.values())
        skor_akhir = [s.current_stance for s in agent_states_list if s.current_stance is not None]

        if len(skor_akhir) >= 2:
            mean = sum(skor_akhir) / len(skor_akhir)
            variance = sum((x - mean) ** 2 for x in skor_akhir) / len(skor_akhir)
            polarization = round(min(variance, 1.0), 3)
        else:
            polarization = 0.0

        return SimulationState(
            topik=self.topik,
            ronde_ke=len(self.timeline),
            agent_states=agent_states_list,
            polarization_score=polarization,
            consensus_score=round(1.0 - polarization, 3),
            events=[],
        )

    def get_timeline(self) -> list[dict]:
        """Dapatkan timeline perubahan state per ronde."""
        return self.timeline

    def compute_stance_shift(self, nama: str) -> float:
        """Hitung seberapa besar perubahan stance agen (akhir - awal)."""
        state = self.agent_states.get(nama)
        if not state or len(state.sentiment_trajectory) < 2:
            return 0.0
        return round(state.sentiment_trajectory[-1] - state.sentiment_trajectory[0], 2)

    def get_polarization_trend(self) -> list[float]:
        """Hitung tren polarisasi per ronde."""
        if not self.timeline:
            return []
        return [t.get("polarization", 0.0) for t in self.timeline]
