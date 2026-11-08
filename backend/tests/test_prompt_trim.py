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
    """Jalankan simulasi dengan mock LLM yang mengembalikan respons valid."""
    agen = agen or get_agents("Politik")[:2]
    
    # Mock call_llm untuk mengembalikan respons agen yang valid
    def fake_llm(system_p, user_p, **kwargs):
        # Respons agen: stance menolak dengan alasan_r1
        return json.dumps({
            "stance": "menolak",
            "score": -0.5,
            "alasan": alasan_r1,
            "sesuai_topik": True,
            "berubah_karena": "",
        })
    
    # Mock narrator LLM call
    monkeypatch.setattr("backend.services.narrator.llm_chat",
                        lambda *a, **k: ('{"vonis":"test","alasan":["a","b","c"],"situasi":{"pemicu":{"angka":"","teks":""},"bahan":[]},"kubu_catatan":{"tolak":"","netral":"","dukung":""},"ronde":[{"no":1,"judul":"j","ringkas":"r"}],"skenario":[{"jika":"j","maka":"m","dasar_agen":"d"}]}', "test-model"))
    
    monkeypatch.setattr(simulation, "call_llm", fake_llm)
    monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
    monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", False, raising=False)

    hasil = simulation.run_simulation(
        topik=TOPIK, agents=agen, jumlah_ronde=2,
        briefing_real=briefing, tier="free", konteks_real=konteks_real,
    )
    return hasil


class TestPromptRonde2:
    def test_briefing_dipakai_struktur_fakta_terkini(self, monkeypatch):
        """Test bahwa briefing dari berita dikonversi ke FAKTA TERKINI."""
        agen = get_agents("Politik")[:2]
        berita = [
            {
                "judul": f"Peristiwa kebijakan nomor {i} yang judulnya panjang sekali - Media{i}",
                "sumber": "google_news_search",
                "source_url": f"https://media{i}.com",
                "tanggal_iso": f"2026-11-{i + 1:02d}T00:00:00+00:00",
            }
            for i in range(12)
        ]
        hasil = _jalankan(monkeypatch, "", "argumen uji", agen,
                         konteks_real={"berita": berita, "sumber_status": "ok"})

        info = hasil["briefing_dipakai"]
        assert "fakta_terkini" in info
        fakta = info["fakta_terkini"]
        assert "klaim" in fakta
        assert len(fakta["klaim"]) <= 5
        # Cek blok FAKTA TERKINI terstruktur
        fakta_teks = fakta["teks"]
        assert "FAKTA TERKINI:" in fakta_teks
        assert "Pilih SATU fakta" in fakta_teks

    def test_briefing_sangat_panjang_dipotong_per_baris(self, monkeypatch):
        """Briefing panjang dari berita tidak memotong di tengah kalimat."""
        agen = get_agents("Politik")[:2]
        # 12 berita dengan judul panjang
        berita = [
            {
                "judul": "A" * 200,
                "sumber": "google_news_search",
                "source_url": f"https://media{i}.com",
                "tanggal_iso": f"2026-11-{i + 1:02d}T00:00:00+00:00",
            }
            for i in range(12)
        ]
        hasil = _jalankan(monkeypatch, "", "argumen uji", agen,
                         konteks_real={"berita": berita, "sumber_status": "ok"})

        info = hasil["briefing_dipakai"]
        fakta = info["fakta_terkini"]
        # Harus dibatasi 5 klaim, tidak memotong di tengah
        assert len(fakta["klaim"]) <= 5
        for k in fakta["klaim"]:
            assert len(k["klaim"]) <= 20  # maks 20 kata per klaim