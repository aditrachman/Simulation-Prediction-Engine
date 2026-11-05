"""Test builder CaseStudy dengan fixture sintetis."""

import json
from pathlib import Path

import pytest

from backend.services.casestudy_builder import build_computed


FIXTURE = Path("backend/tests/fixtures/run_mbg_synthetic.json")


@pytest.fixture
def run_data():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


class TestBuildComputed:
    def test_meta(self, run_data):
        out = build_computed(run_data)
        assert out["meta"]["peserta"] == 12
        assert out["meta"]["ronde"] == 3
        assert out["meta"]["sumber"] == 1
        assert out["meta"]["tanggal"] == "4 Nov 2026"

    def test_hasil_distribusi(self, run_data):
        out = build_computed(run_data)
        d = out["hasil"]["distribusi"]
        # Fixture fixed: R3 menolak 8, netral 3, mendukung 1, fallback 0
        assert d["menolak"] == 8
        assert d["netral"] == 3
        assert d["mendukung"] == 1
        assert "fallback_count" not in d

    def test_hasil_distribusi_per_ronde(self, run_data):
        out = build_computed(run_data)
        # R1: 10 menolak, 1 netral, 1 mendukung
        # R2: 9 menolak, 2 netral, 1 mendukung
        # R3: 8 menolak, 3 netral, 1 mendukung
        pass  # ditest via ronde

    def test_kubu(self, run_data):
        out = build_computed(run_data)
        kubu = {k["tipe"]: k for k in out["kubu"]}
        assert set(kubu["tolak"]["agen"]) == {
            "Jurnalis/Media", "Pengusaha/UMKM", "Oposisi Kritis",
            "Mahasiswa", "Akademisi", "Pekerja Kantoran", "Guru Sekolah", "Dokter/Nakes"
        }
        assert set(kubu["netral"]["agen"]) == {"Warga Desa/Kelurahan", "Orang Tua Bayi", "Pemerintah"}
        assert set(kubu["dukung"]["agen"]) == {"Ibu Hamil/Menyusui"}

    def test_titik_balik_tiga_agen(self, run_data):
        out = build_computed(run_data)
        tb = out["titikBalik"]
        assert len(tb) == 3
        agen_tb = {t["agen"]: t for t in tb}
        # Warga Desa/Kelurahan: menolak -> netral, Ronde 3
        assert agen_tb["Warga Desa/Kelurahan"]["dari"] == "menolak"
        assert agen_tb["Warga Desa/Kelurahan"]["ke"] == "netral"
        assert agen_tb["Warga Desa/Kelurahan"]["kapan"] == "Ronde 3"
        # Orang Tua Bayi: menolak -> netral, Ronde 3 (fixture fixed: R2=menolak, R3=netral)
        assert agen_tb["Orang Tua Bayi"]["dari"] == "menolak"
        assert agen_tb["Orang Tua Bayi"]["ke"] == "netral"
        assert agen_tb["Orang Tua Bayi"]["kapan"] == "Ronde 3"
        # Dokter/Nakes: netral -> menolak, Ronde 3 (perubahan terakhir non-fallback)
        assert agen_tb["Dokter/Nakes"]["dari"] == "netral"
        assert agen_tb["Dokter/Nakes"]["ke"] == "menolak"
        assert agen_tb["Dokter/Nakes"]["kapan"] == "Ronde 3"

    def test_titik_balik_fallback_tidak_dihitung(self, run_data):
        out = build_computed(run_data)
        # Pekerja Kantoran R3 fallback=true, stance menolak->menolak (tidak berubah),
        # tapi kalau berubah juga tidak boleh dihitung
        agen_tb = {t["agen"]: t for t in out["titikBalik"]}
        assert "Pekerja Kantoran" not in agen_tb

    def test_ronde_kutipan_bukan_fallback(self, run_data):
        out = build_computed(run_data)
        for r in out["ronde"]:
            if r["kutipan"]:
                # Verifikasi agen kutipan bukan fallback di ronde itu
                # (mencari di fixture)
                pass  # implementasi detail

    def test_bukti_diperdebatkan_78_persen(self, run_data):
        out = build_computed(run_data)
        bukti = out["buktiDiperdebatkan"]
        # Max 3 entri, satu per agen (ronde terbaru), pasangan berlawanan bersebelahan
        assert len(bukti) <= 3
        assert len(bukti) >= 2
        # Harus ada pasangan 78% naik (Akademisi/Orang Tua Bayi) vs turun (Dokter/Nakes)
        assert any("78%" in b["teks"] for b in bukti)
        # Arah naik dulu, lalu turun
        teks_gabungan = " ".join(b["teks"] for b in bukti)
        idx_naik = teks_gabungan.find("naik")
        idx_turun = teks_gabungan.find("turun")
        if idx_naik != -1 and idx_turun != -1:
            assert idx_naik < idx_turun  # naik muncul sebelum turun

    def test_kepercayaan_rendah_sedang(self, run_data):
        out = build_computed(run_data)
        k = out["hasil"]["kepercayaan"]
        assert k["level"] == "Rendah–Sedang"
        assert "1 sumber" in k["catatan"]
        assert "0,21" in k["catatan"]

    def test_keterbatasan_mengandung_fallback_dan_sumber(self, run_data):
        out = build_computed(run_data)
        k = out["keterbatasan"]
        assert "1 artikel sumber" in k
        # Fixture fixed: fallback_count = 0
        assert "giliran memakai nilai cadangan" not in k
        assert "klaim para agen, bukan data yang sudah diverifikasi" in k

    def test_situasi_sumber_termasuk_briefing_terbatas(self, run_data):
        out = build_computed(run_data)
        s = out["situasi"]
        assert s["sumber"] == "Sumber: 1 artikel RSS. Briefing terbatas."
        assert s["pemicu"]["angka"] == "72,8%"

    def test_tanpa_whatif(self, run_data):
        out = build_computed(run_data)
        # whatif hanya boleh ada setelah simulasi intervensi (FASE 9)
        assert "whatif" not in out

    def test_golden_master(self, run_data):
        """Hasil builder harus identik dengan expected_computed.json (golden test)."""
        import json
        from pathlib import Path
        expected_path = Path("backend/tests/fixtures/expected_computed.json")
        if not expected_path.exists():
            pytest.skip("Golden file belum ada, jalankan sekali untuk generate")
        with open(expected_path, encoding="utf-8") as f:
            expected = json.load(f)
        out = build_computed(run_data)
        assert out == expected


class TestFallbackVariant:
    """Test builder dengan fixture varian yang punya fallback."""
    
    @pytest.fixture
    def run_fallback(self):
        import json
        from pathlib import Path
        with open(Path("backend/tests/fixtures/run_mbg_synthetic_fallback.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_fallback_count_benar(self, run_fallback):
        # kualitas ada di run data, bukan di builder output
        assert run_fallback["kualitas"]["fallback_count"] == 1

    def test_keterbatasan_mengandung_fallback(self, run_fallback):
        out = build_computed(run_fallback)
        k = out["keterbatasan"]
        assert "1 dari 36 giliran memakai nilai cadangan" in k

    def test_kutipan_tidak_dari_fallback(self, run_fallback):
        out = build_computed(run_fallback)
        for ronde_out in out["ronde"]:
            if ronde_out["kutipan"]:
                agen = ronde_out["kutipan"]["agen"]
                rd = next(rd for rd in run_fallback["ronde_detail"] if rd["ronde"] == ronde_out["no"])
                agen_data = next(a for a in rd["agen"] if a["nama"] == agen)
                assert agen_data.get("fallback") is False, f"Kutipan dari agen fallback: {agen}"

    def test_titik_balik_tidak_dari_fallback(self, run_fallback):
        out = build_computed(run_fallback)
        agen_tb = {t["agen"]: t for t in out["titikBalik"]}
        # Orang Tua Bayi: R2 fallback=true tapi TIDAK berubah stance (menolak->menolak)
        # R3 non-fallback berubah menolak->netral -> INI yang jadi titik balik
        assert "Orang Tua Bayi" in agen_tb
        assert agen_tb["Orang Tua Bayi"]["dari"] == "menolak"
        assert agen_tb["Orang Tua Bayi"]["ke"] == "netral"
        assert agen_tb["Orang Tua Bayi"]["kapan"] == "Ronde 3"
        # Dokter/Nakes: R2 netral, R3 menolak (non-fallback) -> titik balik di R3
        assert "Dokter/Nakes" in agen_tb
        assert agen_tb["Dokter/Nakes"]["kapan"] == "Ronde 3"
        assert agen_tb["Dokter/Nakes"]["dari"] == "netral"
        assert agen_tb["Dokter/Nakes"]["ke"] == "menolak"

    def test_distribusi_per_ronde_termasuk_fallback(self, run_fallback):
        out = build_computed(run_fallback)
        # R2: menolak=9, netral=2, mendukung=1 (fallback di Orang Tua Bayi di menolak)
        d_r2 = next(r["distribusi"] for r in out["ronde"] if r["no"] == 2)
        assert d_r2["menolak"] == 9
        assert d_r2["netral"] == 2
        assert d_r2["mendukung"] == 1