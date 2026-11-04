"""Test post-check klaim angka agen (FASE 2)."""

import json

import pytest

from backend.services.agent_turn import angka_klaim, bersihkan_alasan, parse_turn

BRIEFING = (
    "Pemerintah menargetkan 82,9 juta penerima dengan anggaran Rp335 triliun. "
    "Sebanyak 3.200 sekolah sudah menerima layanan. Evaluasi: 72,8% siswa sesuai standar gizi."
)
TOPIK = "Apakah program MBG tepat sasaran?"


def _turn(alasan: str) -> str:
    return json.dumps(
        {
            "stance": "menolak",
            "score": -0.5,
            "alasan": alasan,
            "sesuai_topik": True,
            "berubah_karena": "",
        }
    )


class TestKlaimAngka:
    def test_angka_ada_di_briefing_tidak_ditandai(self):
        assert angka_klaim("Targetnya 82,9 juta penerima, dananya Rp335 triliun.", BRIEFING) == []

    def test_angka_asing_ditandai(self):
        asing = angka_klaim("Katanya 78% sekolah gagal, padahal baru 10% yang dicek.", BRIEFING + TOPIK)
        assert asing == ["78%", "10%"]

    def test_format_berbeda_dianggap_sama(self):
        # briefing menulis 72,8% dan 3.200; alasan menulis 72.8 % dan 3200
        assert angka_klaim("Baru 72.8 % siswa yang sesuai, dari 3200 sekolah.", BRIEFING) == []

    def test_teks_tanpa_angka_tidak_ditandai(self):
        assert angka_klaim("Distribusinya belum jelas dan perlu data.", BRIEFING) == []

    def test_angka_dari_topik_dianggap_sah(self):
        assert angka_klaim("Program 2026 ini belum jelas dasarnya.", "Program 2026") == []

    def test_angka_satu_digit_diabaikan(self):
        assert angka_klaim("Ada 3 masalah dan 2 catatan.", BRIEFING) == []

    def test_angka_diulang_hanya_dicatat_sekali(self):
        assert angka_klaim("78% ini, 78% itu, 78% lagi.", BRIEFING) == ["78%"]

    def test_briefing_kosong_semua_angka_ditandai(self):
        assert angka_klaim("Angkanya 72,8% dari 3.200 sekolah.", "") == ["72,8%", "3.200"]


class TestBersihkanAlasan:
    @pytest.mark.parametrize(
        "kotor, bersih",
        [
            ("Gue setuju, distribusi belum jelas.", "Distribusi belum jelas."),
            ("Kamu benar, data target masih kabur.", "Data target masih kabur."),
            ("Saya sepakat dengan data itu, tapi anggaran belum jelas.", "Tapi anggaran belum jelas."),
            ("Realistis sih, tapi uangnya dari mana.", "Realistis sih, tapi uangnya dari mana."),
        ],
    )
    def test_pembuka_terlarang_dihapus(self, kotor, bersih):
        assert bersihkan_alasan(kotor) == bersih

    def test_artefak_akhir_dibersihkan(self):
        assert bersihkan_alasan("Anggarannya belum jelas ;.") == "Anggarannya belum jelas."
        assert bersihkan_alasan("Datanya masih kabur, Gua.") == "Datanya masih kabur."

    def test_parse_turn_menerapkan_pembersihan(self):
        hasil = parse_turn(_turn("Lu bener, targetnya masih kabur ;."))
        assert hasil["alasan"] == "Targetnya masih kabur."
        assert json.loads(json.dumps(hasil))["fallback"] is False


class TestKlaimMasukHasilRun:
    def test_ronde_detail_memuat_klaim(self, monkeypatch):
        from backend import simulation
        from backend.agents import get_agents

        teks = _turn("Katanya 78% sekolah gagal distribusi.")
        monkeypatch.setattr(simulation, "call_llm", lambda s, u, **k: teks)
        monkeypatch.setattr(simulation.time, "sleep", lambda *_: None)
        monkeypatch.setattr(simulation, "USE_LEGACY_PIPELINE", False, raising=False)

        hasil = simulation.run_simulation(
            topik=TOPIK, agents=get_agents("Politik")[:2], jumlah_ronde=1,
            briefing_real=BRIEFING, tier="free",
        )
        entri = hasil["ronde_detail"][0]["agen"][0]
        assert entri["klaim_agen"] is True
        assert entri["angka_klaim"] == ["78%"]
        assert hasil["klaim_angka"]["giliran_klaim"] == 2
        assert hasil["klaim_angka"]["angka"] == ["78%"]
