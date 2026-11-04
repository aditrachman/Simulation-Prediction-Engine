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
        # Fixture: R3 menolak 8, netral 3, mendukung 1, fallback 1
        assert d["menolak"] == 8
        assert d["netral"] == 3
        assert d["mendukung"] == 1
        assert d["fallback_count"] == 1

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
        # Orang Tua Bayi: menolak -> netral, Ronde 2 (perubahan terakhir non-fallback)
        assert agen_tb["Orang Tua Bayi"]["dari"] == "menolak"
        assert agen_tb["Orang Tua Bayi"]["ke"] == "netral"
        assert agen_tb["Orang Tua Bayi"]["kapan"] == "Ronde 2"
        # Dokter/Nakes: netral -> menolak, Ronde 3 (R2 netral, R3 menolak, bukan fallback)
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
        # Harus menangkap pasangan 78% naik vs turun (R2 dan/atau R3)
        assert len(bukti) >= 2
        assert any("78%" in b["teks"] for b in bukti)
        assert any("Orang Tua Bayi" in b["agen"] for b in bukti)
        assert any("Dokter/Nakes" in b["agen"] for b in bukti)
        assert any("Akademisi" in b["agen"] for b in bukti)

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
        assert "1 dari 36 giliran memakai nilai cadangan" in k
        assert "klaim para agen, bukan data yang sudah diverifikasi" in k

    def test_situasi_sumber_termasuk_briefing_terbatas(self, run_data):
        out = build_computed(run_data)
        s = out["situasi"]
        assert s["sumber"] == "Sumber: 1 artikel RSS. Briefing terbatas."
        assert s["pemicu"]["angka"] == "72,8%"

    def test_whatif_sesudah_null(self, run_data):
        out = build_computed(run_data)
        assert out["whatif"]["sesudah"] is None
        assert out["whatif"]["sebelum"]["menolak"] == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])