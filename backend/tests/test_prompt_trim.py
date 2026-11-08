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


def _jalankan(monkeypatch, briefing: str, alasan_r1: str, agen=None, konteks_real=None):
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
        briefing_real=briefing, tier="free", konteks_real=konteks_real,
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

    def test_briefing_dari_berita_utuh_per_baris(self, monkeypatch):
        agen = get_agents("Politik")[:2]
        alasan = " ".join(f"kata{i}" for i in range(35))
        berita = [
            {
                "judul": f"Peristiwa kebijakan nomor {i} yang judulnya panjang sekali - Media{i}",
                "sumber": "google_news_search",
                "source_url": f"https://media{i}.com",
                "tanggal_iso": f"2026-11-{i + 1:02d}T00:00:00+00:00",
            }
            for i in range(12)
        ]
        prompt, hasil = _jalankan(
            monkeypatch, "", alasan, agen,
            konteks_real={"berita": berita, "sumber_status": "ok"},
        )

        info = hasil["briefing_dipakai"]
        assert len(info["teks"]) <= 900
        assert info["baris"][0] == "Sumber: hanya judul berita, isi artikel belum dibaca."
        for baris in info["baris"][1:]:
            assert baris.endswith(")")
            assert "dilaporkan" in baris
        # Briefing yang sama masuk prompt agen tanpa potongan karakter.
        assert info["teks"] in prompt[0]["user"]
        assert alasan.lower() in prompt[len(agen)]["user"].lower()
