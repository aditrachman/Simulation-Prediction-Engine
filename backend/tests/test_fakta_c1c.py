"""Tes FAKTA C1c: seleksi deterministik, rewrite LLM, validasi berbasis judul."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.simulation import (
    _pilih_judul_fakta,
    _susun_fakta_terkini_rewrite,
    _validasi_klaim_berbasis_judul,
    _label_sentimen,
    _susun_fakta_terkini,
)

TOPIK = (
    "Apakah keputusan BGN mengeluarkan biaya kendaraan distribusi dari biaya "
    "operasional Rp3.000 per penerima manfaat sudah tepat?"
)

JUDUL_BGN = [
    "BGN: Kendaraan Distribusi MBG Tak Masuk Biaya Operasional Rp3.000",
    "Alasan Kendaraan Dicoret dari Biaya Operasional MBG",
    "Biaya Operasional MBG Rp3.000, Mobil SPPG Tak Lagi Ditanggung",
    "Aturan Baru Biaya Operasional MBG, BGN Ungkap Nasib Gaji Pengawas Gizi dan Keuangan",
    "Aturan Baru MBG, Kendaraan Distribusi Tak Lagi Ditanggung Operasional Dapur, Insentif Harian Juga Dipangkas",
    "BGN Hapus Biaya Kendaraan MBG, Mitra SPPG Kini Wajib Siapkan Armada Sendiri",
    "BGN Hapus Biaya Distribusi MBG Rp3.000 Per Penerima: Kami Kembalikan Kebijakan Semestinya",
    "BGN sebut Kendaraan Distribusi MBG Tak Masuk Biaya Operasional Rp3.000: Karena Wajib Dipenuhi SPPG",
]


# 1. Seleksi deterministik: greedy set cover
def test_pilih_judul_fakta_greedy_set_cover():
    terpilih = _pilih_judul_fakta(JUDUL_BGN, TOPIK, 5)
    assert len(terpilih) == 5
    gabung = " ".join(terpilih).lower()
    assert "insentif" in gabung
    assert "armada" in gabung
    assert "mitra" in gabung
    assert "kembalikan" in gabung
    assert "sppg" in gabung
    assert "wajib" in gabung
    terpilih2 = _pilih_judul_fakta(JUDUL_BGN, TOPIK, 5)
    assert terpilih == terpilih2


def test_pilih_judul_fakta_tie_break_urutan_awal():
    judul_sama = [
        "BGN hapus biaya kendaraan armada",
        "BGN hapus biaya kendaraan distribusi",
        "BGN hapus biaya kendaraan operasional",
    ]
    terpilih = _pilih_judul_fakta(judul_sama, "topik uji", 2)
    assert len(terpilih) == 2
    assert terpilih[0] == "BGN hapus biaya kendaraan armada"
    assert terpilih[1] == "BGN hapus biaya kendaraan distribusi"


@patch("backend.simulation.call_llm")
def test_susun_fakta_terkini_rewrite_output_struktur(mock_call_llm):
    mock_call_llm.return_value = (
        "[1] BGN menegaskan kendaraan tidak masuk biaya operasional.\n"
        "[2] Mitra SPPG wajib siapkan armada sendiri.\n"
        "[3] Insentif harian dipangkas."
    )
    judul = [
        "BGN menegaskan kendaraan tidak masuk biaya operasional MBG",
        "BGN Hapus Biaya Kendaraan MBG, Mitra SPPG Kini Wajib Siapkan Armada Sendiri",
        "Aturan Baru MBG, Insentif Harian Juga Dipangkas",
    ]
    hasil = _susun_fakta_terkini_rewrite(judul, "topik uji", 3)
    assert hasil is not None
    assert len(hasil) == 3
    for k in hasil:
        assert "nomor" in k
        assert "klaim" in k
        assert "sumber_idx" in k
        assert 0 <= k["sumber_idx"] < 3
        assert len(k["klaim"].split()) <= 20


def test_validasi_klaim_wajib_punya_kata_pembeda_dari_judul_sumber():
    from backend.simulation import _validasi_klaim_berbasis_judul
    judul = [
        "BGN menegaskan kendaraan tidak masuk biaya operasional MBG",
        "Mitra SPPG wajib siapkan armada sendiri",
    ]
    klaim = [
        {"nomor": 1, "klaim": "BGN menegaskan kendaraan tidak masuk biaya operasional.", "sumber_idx": 0},
        {"nomor": 2, "klaim": "Kebijakan ini bagus untuk ekonomi.", "sumber_idx": 1},
    ]
    valid = _validasi_klaim_berbasis_judul(klaim, judul, "topik uji")
    assert len(valid) == 2
    assert "Mitra SPPG wajib siapkan armada sendiri" in valid[1]["klaim"]


def test_validasi_tolak_pola_biaya_jadi_rp():
    from backend.simulation import _validasi_klaim_berbasis_judul
    judul = ["BGN hapus biaya kendaraan"]
    klaim = [{"nomor": 1, "klaim": "Biaya kendaraan jadi Rp3.000 per penerima.", "sumber_idx": 0}]
    valid = _validasi_klaim_berbasis_judul(klaim, judul, "topik")
    assert "BGN hapus biaya kendaraan" in valid[0]["klaim"]


@patch("backend.simulation.call_llm")
def test_susun_fakta_terkini_pipeline_deterministik(mock_call_llm):
    mock_call_llm.return_value = (
        "[1] BGN menegaskan kendaraan tidak masuk biaya operasional.\n"
        "[2] Mitra SPPG wajib siapkan armada sendiri.\n"
        "[3] Insentif harian dipangkas.\n"
        "[4] Gaji pengawas dikaji.\n"
        "[5] Kebijakan dikembalikan."
    )
    judul = [
        "BGN menegaskan kendaraan tidak masuk biaya operasional MBG",
        "BGN Hapus Biaya Kendaraan MBG, Mitra SPPG Kini Wajib Siapkan Armada Sendiri",
        "Aturan Baru MBG, Insentif Harian Juga Dipangkas",
        "BGN Ungkap Nasib Gaji Pengawas Gizi dan Keuangan",
        "BGN Hapus Biaya Distribusi MBG Rp3.000 Per Penerima: Kami Kembalikan Kebijakan Semestinya",
    ]
    hasil1 = _susun_fakta_terkini(judul, "topik uji", 5)
    hasil2 = _susun_fakta_terkini(judul, "topik uji", 5)
    assert hasil1 is not None and hasil2 is not None
    assert len(hasil1) == len(hasil2) == 5
    for k1, k2 in zip(hasil1, hasil2):
        assert k1["klaim"] == k2["klaim"]
        assert k1["sumber_idx"] == k2["sumber_idx"]


def test_susun_fakta_terkini_fallback_llm_gagal():
    with patch("backend.simulation.call_llm", side_effect=RuntimeError("LLM down")):
        judul = ["BGN hapus biaya kendaraan", "BGN hapus biaya armada"]
        hasil = _susun_fakta_terkini(judul, "topik", 2)
        assert hasil is not None
        assert len(hasil) == 2
        assert "BGN hapus biaya kendaraan" in hasil[0]["klaim"]
        assert "BGN hapus biaya armada" in hasil[1]["klaim"]


def test_susun_fakta_terkini_awal_kata_maks_2():
    with patch("backend.simulation.call_llm") as mock_call_llm:
        mock_call_llm.return_value = (
            "[1] BGN hapus biaya kendaraan.\n"
            "[2] BGN hapus biaya operasional.\n"
            "[3] BGN hapus biaya distribusi.\n"
            "[4] Mitra SPPG siapkan armada."
        )
        judul = [
            "BGN hapus biaya kendaraan",
            "BGN hapus biaya armada",
            "BGN hapus biaya operasional",
            "BGN hapus biaya distribusi",
            "Mitra SPPG siapkan armada",
        ]
        hasil = _susun_fakta_terkini(judul, "topik", 5)
        awalan = [k["klaim"].split()[0] for k in hasil]
        assert awalan.count("BGN") <= 3
        klaim_gabung = " ".join(k["klaim"] for k in hasil)
        assert "Mitra SPPG siapkan armada" in klaim_gabung


def test_judul_agregator_tidak_pernah_terpilih():
    judul = JUDUL_BGN + [
        "Berita Seputar BGN hapus biaya kendaraan MBG Terbaru dan Terkini Hari Ini",
        "Kumpulan Berita BGN Hari Ini",
        "Foto: Kendaraan Distribusi MBG",
    ]
    terpilih = _pilih_judul_fakta(judul, TOPIK, 8)
    assert len(terpilih) == 8
    gabung = " ".join(terpilih).lower()
    assert "berita seputar" not in gabung
    assert "kumpulan berita" not in gabung
    assert "foto:" not in gabung


def test_klaim_berakhir_di_tengah_kata_diganti_judul():
    judul = ["BGN Hapus Biaya Kendaraan MBG, Mitra SPPG Kini Wajib Siapkan Armada Sendiri"]
    klaim = [{
        "nomor": 1,
        "klaim": "BGN Hapus Biaya Kendaraan MBG Mitra SPPG Kini Wajib Siapkan Armad",
        "sumber_idx": 0,
    }]
    valid = _validasi_klaim_berbasis_judul(klaim, judul, "topik")
    assert valid[0]["klaim"] == judul[0]


def test_kata_berita_umum_tidak_dihitung_pembeda():
    judul = ["BGN Hapus Biaya Kendaraan MBG, Mitra SPPG Kini Wajib Siapkan Armada Sendiri"]
    klaim = [{
        "nomor": 1,
        "klaim": "Berita terbaru terkini hari ini update live seputar.",
        "sumber_idx": 0,
    }]
    valid = _validasi_klaim_berbasis_judul(klaim, judul, "topik")
    assert valid[0]["klaim"] == judul[0]


def test_label_sentimen_round_2_desimal():
    from backend.simulation import _label_sentimen
    assert _label_sentimen(-0.2000000001) == "netral"
    assert _label_sentimen(-0.2) == "netral"
    assert _label_sentimen(-0.21) == "negatif"
    assert _label_sentimen(0.2000000001) == "netral"
    assert _label_sentimen(0.2) == "netral"
    assert _label_sentimen(0.21) == "positif"


def test_tidak_ada_kata_kunci_sudut_di_source():
    import backend.simulation as sim
    source = sim.__file__
    with open(source, "r") as f:
        source_code = f.read()
    code_lines = [line for line in source_code.split("\n") if not line.strip().startswith("#")]
    code_only = "\n".join(code_lines)
    assert "kata_kunci_sudut" not in code_only
    assert "punya_sudut" not in code_only
    assert "punya_sudut_f" not in code_only


@patch("backend.simulation.call_llm")
def test_stabilitas_5x_fakta(mock_call_llm):
    mock_call_llm.return_value = (
        "[1] Biaya operasional Rp3.000 tidak lagi mencakup mobil SPPG.\n"
        "[2] Insentif harian dipangkas dan kendaraan distribusi dikecualikan.\n"
        "[3] Mitra SPPG wajib siapkan armada sendiri.\n"
        "[4] Kebijakan dikembalikan ke bentuk semestinya.\n"
        "[5] BGN sebut kendaraan distribusi wajib dipenuhi SPPG."
    )
    JUDUL_BGN = [
        "BGN: Kendaraan Distribusi MBG Tak Masuk Biaya Operasional Rp3.000",
        "Alasan Kendaraan Dicoret dari Biaya Operasional MBG",
        "Biaya Operasional MBG Rp3.000, Mobil SPPG Tak Lagi Ditanggung",
        "Aturan Baru Biaya Operasional MBG, BGN Ungkap Nasib Gaji Pengawas Gizi dan Keuangan",
        "Aturan Baru MBG, Kendaraan Distribusi Tak Lagi Ditanggung Operasional Dapur, Insentif Harian Juga Dipangkas",
        "BGN Hapus Biaya Kendaraan MBG, Mitra SPPG Kini Wajib Siapkan Armada Sendiri",
        "BGN Hapus Biaya Distribusi MBG Rp3.000 Per Penerima: Kami Kembalikan Kebijakan Semestinya",
        "BGN sebut Kendaraan Distribusi MBG Tak Masuk Biaya Operasional Rp3.000: Karena Wajib Dipenuhi SPPG",
    ]
    hasil_set = []
    for _ in range(5):
        hasil = _susun_fakta_terkini(JUDUL_BGN, "topik uji", 5)
        klaim_str = tuple(k["klaim"] for k in hasil)
        hasil_set.append(klaim_str)
    assert all(h == hasil_set[0] for h in hasil_set)
    klaim_gabung = " ".join(hasil_set[0]).lower()
    assert "armada" in klaim_gabung
    assert "mitra" in klaim_gabung
    assert "insentif" in klaim_gabung
    assert "kembalikan" in klaim_gabung or "dikembalikan" in klaim_gabung
    assert "wajib" in klaim_gabung
    assert "sppg" in klaim_gabung


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
