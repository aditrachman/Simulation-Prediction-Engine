"""Test integrasi jalur JSON di run_simulation (FASE 1)."""

import json

import pytest

from backend import simulation
from backend.agents import get_agents

TURN_JSON = json.dumps(
    {
        "stance": "menolak",
        "score": -0.6,
        "alasan": "Distribusi bantuan belum jelas, jadi klaim tepat sasaran belum terbukti.",
        "sesuai_topik": True,
        "berubah_karena": None,
    }
)


@pytest.fixture
def dua_agen():
    return get_agents("Politik")[:2]


def _jalankan(monkeypatch, agen, legacy: bool):
    calls = []

    def fake_call_llm(system_p, user_p, **kwargs):
        calls.append({"system": system_p, "user": user_p, **kwargs})
        return "Jawaban lama yang bukan JSON."

    monkeypatch.setattr(simulation, "call_llm", fake_call_llm)
    monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
    monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", legacy, raising=False)
    if legacy:
        monkeypatch.setattr(
            simulation,
            "score_sentiment",
            lambda teks, **kwargs: {"label": "netral", "skor": 0.0},
        )
    else:
        # call_llm palsu harus balas JSON valid untuk jalur baru
        monkeypatch.setattr(
            simulation,
            "call_llm",
            lambda system_p, user_p, **kwargs: (
                calls.append({"system": system_p, "user": user_p, **kwargs}) or TURN_JSON
            ),
        )
    hasil = simulation.run_simulation(
        topik="Apakah program MBG tepat sasaran?",
        agents=agen,
        jumlah_ronde=1,
        tier="free",
    )
    return hasil, calls


class TestJalurJson:
    def test_satu_call_per_giliran(self, monkeypatch, dua_agen):
        hasil, calls = _jalankan(monkeypatch, dua_agen, legacy=False)
        assert len(calls) == len(dua_agen)
        assert all(c["max_tokens"] == simulation.TURN_MAX_TOKENS for c in calls)
        assert hasil["runtime_mode"]["pipeline"] == "json"

    def test_ronde_detail_memuat_field_baru(self, monkeypatch, dua_agen):
        hasil, _ = _jalankan(monkeypatch, dua_agen, legacy=False)
        entri = hasil["ronde_detail"][0]["agen"][0]
        assert entri["stance"] == "menolak"
        assert entri["score"] == -0.6
        assert entri["alasan"].startswith("Distribusi bantuan")
        assert entri["berubah_karena"] is None
        assert entri["sesuai_topik"] is True
        assert entri["fallback"] is False
        assert entri["sentimen"] == {"label": "negatif", "skor": -0.6}

    def test_delta_cap_tetap_berlaku(self, monkeypatch, dua_agen):
        # Ronde 1 menolak kuat, ronde 2 mendukung kuat: delta 1.8 -> di-clamp 0.7
        teks = [
            json.dumps({"stance": "menolak", "score": -0.8, "alasan": "Awal.",
                        "sesuai_topik": True, "berubah_karena": None}),
            json.dumps({"stance": "menolak", "score": -0.8, "alasan": "Awal.",
                        "sesuai_topik": True, "berubah_karena": None}),
            json.dumps({"stance": "mendukung", "score": 1.0, "alasan": "Berubah.",
                        "sesuai_topik": True, "berubah_karena": "Ada data baru."}),
            json.dumps({"stance": "mendukung", "score": 1.0, "alasan": "Berubah.",
                        "sesuai_topik": True, "berubah_karena": "Ada data baru."}),
        ]
        monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
        monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", False, raising=False)
        monkeypatch.setattr(simulation, "call_llm", lambda s, u, **k: teks.pop(0))
        hasil = simulation.run_simulation(
            topik="Apakah program MBG tepat sasaran?",
            agents=dua_agen,
            jumlah_ronde=2,
            tier="free",
        )
        scores = [
            a["score"]
            for ronde in hasil["ronde_detail"]
            for a in ronde["agen"]
            if a["nama"] == dua_agen[0]["nama"]
        ]
        assert scores == [-0.8, -0.1]


class TestJalurLegacy:
    def test_flag_legacy_masih_qa_dan_sentimen(self, monkeypatch, dua_agen):
        hasil, calls = _jalankan(monkeypatch, dua_agen, legacy=True)
        # per giliran: 1 call agen + 1 call QA
        assert len(calls) == 2 * len(dua_agen)
        assert hasil["runtime_mode"]["pipeline"] == "legacy"
        entri = hasil["ronde_detail"][0]["agen"][0]
        assert entri["stance"] is None
