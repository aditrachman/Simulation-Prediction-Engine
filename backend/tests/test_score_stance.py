"""Test konsistensi stance vs score (FASE 3b). Stance menang."""

import json

import pytest

from backend import simulation
from backend.services.agent_turn import execute_turn, sesuaikan_score


@pytest.mark.parametrize(
    "stance, score, harapan",
    [
        ("netral", 0.5, 0.2),
        ("netral", -0.9, -0.2),
        ("menolak", 0.3, -0.2),
        ("mendukung", -0.7, 0.2),
        ("menolak", -0.6, -0.6),
        ("netral", -0.1, -0.1),
        ("mendukung", 0.6, 0.6),
    ],
)
def test_clamp_ke_rentang_stance(stance, score, harapan):
    hasil, disesuaikan = sesuaikan_score(score, stance)
    assert hasil == harapan
    assert disesuaikan is (harapan != score)


def _llm(teks: str):
    def _call(system_p, user_p):
        return teks

    return _call


def _turn(**kw) -> str:
    data = {
        "stance": "netral",
        "score": 0.5,
        "alasan": "Datanya belum jelas arahnya.",
        "sesuai_topik": True,
        "berubah_karena": "",
    }
    data.update(kw)
    return json.dumps(data)


class TestIntegrasi:
    def test_netral_score_positif_disesuaikan(self):
        hasil = execute_turn(_llm(_turn()), "sistem", "pertanyaan")
        assert hasil["stance"] == "netral"
        assert hasil["score"] == 0.2
        assert hasil["score_disesuaikan"] is True
        assert hasil["score_asli"] == 0.5

    def test_dalam_rentang_tidak_ditandai(self):
        hasil = execute_turn(_llm(_turn(stance="menolak", score=-0.6)), "sistem", "pertanyaan")
        assert hasil["score"] == -0.6
        assert hasil["score_disesuaikan"] is False
        assert hasil["score_asli"] is None

    def test_fallback_tidak_ditandai(self):
        hasil = execute_turn(
            _llm("bukan json"), "sistem", "pertanyaan", prev_stance="menolak", prev_score=-0.4
        )
        assert hasil["fallback"] is True
        assert hasil["score"] == -0.4
        assert hasil["score_disesuaikan"] is False

    def test_ronde_detail_memuat_penyesuaian(self, monkeypatch):
        from backend.agents import get_agents

        monkeypatch.setattr(simulation, "call_llm", lambda s, u, **k: _turn())
        monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
        monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", False, raising=False)

        hasil = simulation.run_simulation(
            topik="Apakah program MBG tepat sasaran?", agents=get_agents("Politik")[:2],
            jumlah_ronde=1, tier="free",
        )
        entri = hasil["ronde_detail"][0]["agen"][0]
        assert entri["score"] == 0.2
        assert entri["score_asli"] == 0.5
        assert entri["score_disesuaikan"] is True
