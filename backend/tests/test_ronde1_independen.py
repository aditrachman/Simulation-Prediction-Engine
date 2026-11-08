"""Test Ronde 1 independen + ringkasan Ronde 2 (FASE 3)."""

import json

import pytest

from backend import simulation
from backend.agents import get_agents
from backend.memory import MAKS_KATA_RINGKASAN, build_round_summary

TOPIK = "Apakah program MBG tepat sasaran?"


def _turn(stance: str, alasan: str) -> str:
    return json.dumps(
        {
            "stance": stance,
            "score": -0.5 if stance == "menolak" else 0.0,
            "alasan": alasan,
            "sesuai_topik": True,
            "berubah_karena": "",
        }
    )


def _opini(nama: str, pendapat: str, skor: float) -> dict:
    return {
        "nama": nama,
        "pendapat": pendapat,
        "sentimen": {"label": "netral", "skor": skor},
        "pengaruh": 0.5,
    }


class TestRingkasanRonde:
    def test_memilih_tiga_skor_terbesar_tanpa_nama(self):
        data = [
            _opini("Mahasiswa", "Argumen lemah skor kecil.", 0.1),
            _opini("Pemerintah", "Anggaran belum jelas arahnya.", 0.9),
            _opini("Pengusaha/UMKM", "Biaya operasional naik terus.", -0.8),
            _opini("Akademisi", "Sampel evaluasinya terlalu kecil.", -0.5),
        ]
        hasil = build_round_summary(data)
        assert "- " in hasil
        for nama in ("Mahasiswa", "Pemerintah", "Pengusaha/UMKM", "Akademisi"):
            assert nama not in hasil
        assert "Anggaran belum jelas arahnya." in hasil
        assert "Biaya operasional naik terus." in hasil
        assert "Sampel evaluasinya terlalu kecil." in hasil
        assert "Argumen lemah skor kecil." not in hasil

    def test_agen_berbeda_dan_dipotong_25_kata(self):
        panjang = " ".join(f"kata{i}" for i in range(60))
        data = [
            _opini("A", panjang, -0.9),
            _opini("A", panjang, -0.9),  # duplikat agen: harus dilewati
            _opini("B", "Pendapat kedua yang singkat.", 0.5),
        ]
        hasil = build_round_summary(data)
        assert hasil.count("kata0") == 1
        assert len(hasil.splitlines()) == 3  # header + 2 baris
        isi = hasil.splitlines()[1].strip('- "').rstrip('"')
        assert len(isi.split()) == MAKS_KATA_RINGKASAN

    def test_placeholder_gagal_dilewati(self):
        data = [
            _opini("A", "(agen tidak memberikan output valid)", 0.0),
            _opini("B", "(gagal: timeout)", 0.0),
            _opini("C", "Data distribusi belum terbuka.", 0.0),
        ]
        hasil = build_round_summary(data)
        assert hasil == 'Pihak lain berpendapat:\n- "Data distribusi belum terbuka."'

    def test_pendapat_sendiri_tidak_masuk_ringkasan(self):
        data = [
            _opini("Mahasiswa", "Argumen sendiri yang tidak boleh muncul.", -0.9),
            _opini("Pemerintah", "Argumen pihak lain yang boleh muncul.", 0.5),
        ]
        hasil = build_round_summary(data, kecuali="Mahasiswa")
        assert "Argumen sendiri" not in hasil
        assert "Argumen pihak lain" in hasil

    def test_kosong(self):
        assert build_round_summary([]) == ""


class TestRonde1Independen:
    @pytest.fixture
    def dua_agen(self):
        return get_agents("Politik")[:2]

    def test_prompt_ronde1_tidak_memuat_agen_lain(self, monkeypatch, dua_agen):
        prompt: list[dict] = []

        def fake(system_p, user_p, **kwargs):
            prompt.append({"system": system_p, "user": user_p})
            return _turn("menolak", "Distribusi belum jelas.")

        monkeypatch.setattr(simulation, "call_llm", fake)
        monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
        monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", False, raising=False)

        simulation.run_simulation(
            topik=TOPIK, agents=dua_agen, jumlah_ronde=1,
            briefing_real="Anggaran Rp335 triliun untuk 82,9 juta penerima.", tier="free",
        )

        assert len(prompt) == len(dua_agen)
        for p in prompt:
            assert "Yang baru aja ngomong" not in p["user"]
            assert "Pihak lain berpendapat" not in p["user"]
            assert "menyangkal" not in p["user"]
            assert "Info konteks:" in p["user"]  # semua agen Ronde 1 dapat briefing

    def test_ronde2_memakai_ringkasan_tanpa_nama(self, monkeypatch, dua_agen):
        prompt: list[dict] = []
        putaran = {"i": 0}

        # Mock response untuk FAKTA TERKINI (panggilan pertama)
        _FAKTA_RESPONSE = (
            "[1] Pemerintah mengumumkan program MBG dengan anggaran Rp335 triliun.\n"
            "[2] Beberapa daerah melaporkan kesiapan distribusi belum merata.\n"
            "[3] Komisi pemantau menilai target pencapaian masih di atas rata-rata."
        )

        # Berita untuk memicu FAKTA TERKINI
        berita = [
            {
                "judul": f"Berita kebijakan nomor {i} tentang distribusi",
                "sumber": "google_news_search",
                "source_url": f"https://media{i}.com",
                "tanggal_iso": f"2026-11-{i + 1:02d}T00:00:00+00:00",
            }
            for i in range(5)
        ]

        def fake(system_p, user_p, **kwargs):
            putaran["i"] += 1
            prompt.append({"user": user_p})
            # Panggilan pertama = FAKTA TERKINI
            if putaran["i"] == 1:
                return _FAKTA_RESPONSE
            return _turn("menolak", f"Argumen nomor {putaran['i']} soal distribusi.")

        monkeypatch.setattr(simulation, "call_llm", fake)
        monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
        monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", False, raising=False)

        simulation.run_simulation(
            topik=TOPIK, agents=dua_agen, jumlah_ronde=2, tier="free",
            konteks_real={"berita": berita, "sumber_status": "ok"},
        )

        # FAKTA TERKINI call (1) + agen R1 (4) = 5, then agen R2 starts at index 5
        lanjutan = prompt[5:]
        assert lanjutan
        for p in lanjutan:
            assert "Pihak lain berpendapat" in p["user"]
            for agen in dua_agen:
                assert agen["nama"] not in p["user"]
