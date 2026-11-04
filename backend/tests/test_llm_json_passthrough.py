"""Regresi: JSON agen tidak boleh dirusak post-processing call_llm.

Mock dipasang di llm_guard.chat (satu lapisan di BAWAH call_llm) supaya jalur
yang diuji adalah call_llm + execute_turn + run_simulation yang sebenarnya.
"""

import json

import pytest

from backend import llm, llm_guard, simulation
from backend.agents import get_agents
from backend.services.agent_turn import TURN_RESPONSE_FORMAT, parse_turn

JSON_UTUH = json.dumps(
    {
        "stance": "menolak",
        "score": -0.6,
        "alasan": "Data distribusi belum jelas, jadi klaim tepat sasaran belum terbukti.",
        "sesuai_topik": True,
        "berubah_karena": "",
    },
    ensure_ascii=False,
)


def _mock_guard(monkeypatch, teks: str, tercatat: list):
    def fake_chat(messages, max_tokens, **kwargs):
        tercatat.append({"messages": messages, "max_tokens": max_tokens, **kwargs})
        return teks, "dummy-model"

    monkeypatch.setattr(llm_guard, "chat", fake_chat)


class TestJsonTidakDipotong:
    def test_call_llm_mengembalikan_json_utuh(self, monkeypatch):
        tercatat: list = []
        _mock_guard(monkeypatch, JSON_UTUH, tercatat)

        keluar = llm.call_llm(
            "sistem", "user", max_tokens=220, model="dummy", use_cache=False,
            auto_complete=False, response_format=TURN_RESPONSE_FORMAT,
        )

        assert keluar == JSON_UTUH
        assert parse_turn(keluar) is not None

    def test_response_format_diteruskan_ke_guard(self, monkeypatch):
        tercatat: list = []
        _mock_guard(monkeypatch, JSON_UTUH, tercatat)

        llm.call_llm(
            "sistem", "user", max_tokens=220, model="dummy", use_cache=False,
            auto_complete=False, response_format=TURN_RESPONSE_FORMAT,
        )

        assert tercatat[0]["response_format"] == TURN_RESPONSE_FORMAT

    def test_legacy_prosa_tetap_dipotong(self, monkeypatch):
        """Perilaku default call_llm untuk teks prosa tidak berubah."""
        tercatat: list = []
        _mock_guard(
            monkeypatch,
            "Ini kalimat pertama yang cukup panjang untuk lolos ambang. Ini kalimat kedua.",
            tercatat,
        )
        keluar = llm.call_llm("sistem", "user", max_tokens=100, model="dummy", use_cache=False)
        assert keluar.endswith(".")
        assert keluar == "Ini kalimat pertama yang cukup panjang untuk lolos ambang. Ini kalimat kedua."

    def test_prosa_tanpa_penutup_dipotong_seperti_dulu(self, monkeypatch):
        tercatat: list = []
        _mock_guard(
            monkeypatch,
            "Kalimat pembuka yang panjang sekali supaya melewati ambang separuh teks. Potongan tanpa titik",
            tercatat,
        )
        keluar = llm.call_llm("sistem", "user", max_tokens=100, model="dummy", use_cache=False)
        assert keluar == "Kalimat pembuka yang panjang sekali supaya melewati ambang separuh teks."


class TestJalurSimulasi:
    def test_run_simulation_tanpa_fallback(self, monkeypatch):
        tercatat: list = []
        _mock_guard(monkeypatch, JSON_UTUH, tercatat)
        monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
        monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", False, raising=False)

        agen = get_agents("Politik")[:2]
        hasil = simulation.run_simulation(
            topik="Apakah program MBG tepat sasaran?",
            agents=agen,
            jumlah_ronde=1,
            tier="free",
        )

        entri = hasil["ronde_detail"][0]["agen"][0]
        assert entri["fallback"] is False
        assert entri["stance"] == "menolak"
        assert entri["score"] == -0.6
        assert hasil["kualitas"]["fallback_count"] == 0
        assert hasil["kualitas"]["status"] == "ok"
        # jalur JSON harus lewat response_format + max_tokens 220
        assert tercatat[0]["response_format"] == TURN_RESPONSE_FORMAT
        assert tercatat[0]["max_tokens"] == simulation.TURN_MAX_TOKENS
