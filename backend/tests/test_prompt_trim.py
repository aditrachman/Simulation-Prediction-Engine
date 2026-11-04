"""Test guard pemangkasan prompt jalur JSON (FASE 3b).

Yang wajib utuh di Ronde 2+: posisi agen sendiri di ronde sebelumnya, aturan
berubah_karena, dan ringkasan "Pihak lain berpendapat".
"""

import json

import pytest

from backend import simulation
from backend.agents import get_agents

TOPIK = "Apakah program MBG tepat sasaran?"


def _turn(stance: str, alasan: str) -> str:
    return json.dumps(
        {
            "stance": stance,
            "score": -0.5 if stance == "menolak" else 0.5,
            "alasan": alasan,
            "sesuai_topik": True,
            "berubah_karena": "",
        }
    )


def _jalankan(monkeypatch, briefing: str, alasan_r1: str, agen=None):
    agen = agen or get_agents("Politik")[:2]
    prompt: list[dict] = []

    def fake(system_p, user_p, **kwargs):
        prompt.append({"system": system_p, "user": user_p})
        if len(prompt) <= len(agen):
            return _turn("menolak", alasan_r1)
        return _turn("netral", "Pandangan ronde kedua soal distribusi.")

    monkeypatch.setattr(simulation, "call_llm", fake)
    monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
    monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", False, raising=False)
    # Mock narrator LLM call to avoid real API calls
    monkeypatch.setattr("backend.services.narrator.llm_chat",
                        lambda *a, **k: ('{"vonis":"test","alasan":["a","b","c"],"situasi":{"pemicu":{"angka":"","teks":""},"bahan":[]},"kubu_catatan":{"tolak":"","netral":"","dukung":""},"ronde":[{"no":1,"judul":"j","ringkas":"r"}],"skenario":[{"jika":"j","maka":"m","dasar_agen":"d"}]}', "test-model"))

    hasil = simulation.run_simulation(
        topik=TOPIK, agents=agen, jumlah_ronde=2,
        briefing_real=briefing, tier="free",
    )
    return prompt, hasil


class TestPromptRonde2:
    def test_memuat_posisi_dan_alasan_sendiri(self, monkeypatch):
        agen = get_agents("Politik")[:2]
        alasan = f"Data distribusi {agen[0]['nama']} masih belum terbuka."
        prompt, _ = _jalankan(monkeypatch, "Anggaran Rp335 triliun.", alasan, agen)

        r2 = prompt[len(agen)]["user"]
        assert alasan.lower() in r2.lower()
        assert "MENOLAK" in r2

    def test_memuat_aturan_berubah_karena(self, monkeypatch):
        agen = get_agents("Politik")[:2]
        prompt, _ = _jalankan(monkeypatch, "Anggaran Rp335 triliun.", "Data belum terbuka.", agen)

        r2 = prompt[len(agen)]["user"]
        assert "berubah_karena" in r2
        assert "kalau sama, kosongkan" in r2

    def test_briefing_sangat_panjang_tidak_menghapus_konteks_wajib(self, monkeypatch):
        agen = get_agents("Politik")[:2]
        briefing = "Data resmi: " + ("angka 72,8% dan 3.200 sekolah. " * 200)
        alasan = " ".join(f"argumen{i}" for i in range(35))
        prompt, _ = _jalankan(monkeypatch, briefing, alasan, agen)

        r2 = prompt[len(agen)]["user"]
        assert alasan.lower() in r2.lower()   # posisi agen sendiri utuh
        assert "berubah_karena" in r2  # aturan perubahan utuh
        assert "Pihak lain berpendapat" in r2  # ringkasan utuh

    def test_pemangkasan_hanya_memotong_briefing(self, monkeypatch):
        agen = get_agents("Politik")[:2]
        briefing = "X" * 3000
        alasan = " ".join(f"kata{i}" for i in range(35))
        prompt, _ = _jalankan(monkeypatch, briefing, alasan, agen)

        # Ronde 1 dipangkas, tapi tidak boleh menyisakan briefing 3000 karakter.
        assert len(prompt[0]["user"]) < len(briefing)
        assert alasan.lower() in prompt[len(agen)]["user"].lower()
