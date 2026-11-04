import time
"""Test FASE 4: paralel per ronde, deterministik, tanpa race, flag false = serial."""

import json
import threading

import pytest

from backend import simulation
from backend.agents import get_agents

TOPIK = "Apakah program MBG tepat sasaran?"


def _pabrik_llm(tunda: dict[str, float] | None = None):
    """Fake LLM deterministik: stance per agen per ronde, tanpa retry."""
    tunda = tunda or {}
    hits: dict[str, int] = {}
    lock = threading.Lock()

    def _call(system_p, user_p, **kwargs):
        nama = system_p.split("Kamu ", 1)[1].split(".", 1)[0]
        with lock:
            n = hits.get(nama, 0) + 1
            hits[nama] = n
        if tunda.get(nama):
            import time
            time.sleep(tunda[nama])
        stance = "menolak" if n % 2 else "mendukung"
        return json.dumps({
            "stance": stance,
            "score": -0.5 if stance == "menolak" else 0.5,
            "alasan": f"Poin ronde {n} soal distribusi dan target.",
            "sesuai_topik": True,
            "berubah_karena": "" if n == 1 else "Ringkasan pihak lain mengubah prioritas.",
        })

    return _call


def _jalankan(monkeypatch, *, parallel: bool, max_agents: int = 4, tunda=None):
    monkeypatch.setattr(simulation, "call_llm", _pabrik_llm(tunda))
    monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
    monkeypatch.setattr(time, "sleep", lambda *_: None)  # patch global time.sleep for tunda
    monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", False, raising=False)
    monkeypatch.setattr(simulation, "PARALLEL_AGENTS", parallel)
    monkeypatch.setattr(simulation, "PARALLEL_AGENTS_MAX", max_agents)
    # Mock narrator LLM call to avoid real API calls
    monkeypatch.setattr("backend.services.narrator.llm_chat",
                        lambda *a, **k: ('{"vonis":"test","alasan":["a","b","c"],"situasi":{"pemicu":{"angka":"","teks":""},"bahan":[]},"kubu_catatan":{"tolak":"","netral":"","dukung":""},"ronde":[{"no":1,"judul":"j","ringkas":"r"}],"skenario":[{"jika":"j","maka":"m","dasar_agen":"d"}]}', "test-model"))

    agen = get_agents("Politik")[:4]
    hasil = simulation.run_simulation(
        topik=TOPIK, agents=agen, jumlah_ronde=2,
        briefing_real="Anggaran Rp335 triliun untuk 82,9 juta penerima.", tier="free",
    )
    return agen, hasil


class TestParalelSamaDenganSerial:
    def test_ronde_detail_identik(self, monkeypatch):
        _, serial = _jalankan(monkeypatch, parallel=False)
        _, paralel = _jalankan(monkeypatch, parallel=True)

        assert serial["ronde_detail"] == paralel["ronde_detail"]
        assert serial["sentimen_agregat"] == paralel["sentimen_agregat"]

    def test_urutan_sesuai_urutan_bicara_walau_selesai_tidak_berurutan(self, monkeypatch):
        from backend.core.scheduler import get_speaking_order

        agen = get_agents("Politik")[:4]
        # Dua agen pertama paling lambat: hasil tetap urut sesuai speaking order.
        tunda = {agen[0]["nama"]: 0.2, agen[1]["nama"]: 0.1}
        _, hasil = _jalankan(monkeypatch, parallel=True, tunda=tunda)

        for ronde in hasil["ronde_detail"]:
            order = get_speaking_order(agen, ronde["ronde"])
            assert [a["nama"] for a in ronde["agen"]] == [agen[i]["nama"] for i in order]

    def test_tidak_ada_race_pada_memori_dan_stance(self, monkeypatch):
        agen, hasil = _jalankan(monkeypatch, parallel=True)

        for a in agen:
            assert len(a["memori"]) == 2  # satu entri per ronde
            assert [m["ronde"] for m in a["memori"]] == [1, 2]

        for ronde in hasil["ronde_detail"]:
            for entri in ronde["agen"]:
                if ronde["ronde"] == 1:
                    assert not entri["berubah_karena"]
                else:
                    assert entri["berubah_karena"] == "Ringkasan pihak lain mengubah prioritas."

    def test_flag_false_serial_dan_tanpa_thread(self, monkeypatch):
        dipakai = []

        class PoolPalsu:
            def __init__(self, *a, **k):
                dipakai.append("pool")

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def map(self, fn, data):
                return [fn(x) for x in data]

        monkeypatch.setattr(simulation, "ThreadPoolExecutor", PoolPalsu)
        _, hasil = _jalankan(monkeypatch, parallel=False)
        assert dipakai == []
        assert len(hasil["ronde_detail"]) == 2

    def test_parallel_flag_dicatat_di_statistik(self, monkeypatch):
        _, hasil = _jalankan(monkeypatch, parallel=True)
        stat = hasil["statistik_run"]
        assert stat["parallel"] is True
        assert stat["pipeline"] == "json"
        assert stat["durasi_detik"] >= 0.0
        for kunci in ("panggilan_llm", "token_prompt", "token_completion",
                      "token_total", "rate_limited_429",
                      "tunggu_token_budget_detik", "tunggu_rpm_detik"):
            assert kunci in stat
