"""Tes untuk backend/core/scenario.py — sumber kebenaran tunggal skenario."""

from __future__ import annotations

import pytest

from backend.core.scenario import (
    kepercayaan_sumber,
    resolve_scenario,
    swing_voter_terfilter,
    teks_polarisasi,
)


def _sentimen(n_pos: int, n_neg: int, n_net: int) -> dict[str, list[float]]:
    data = {}
    for i in range(n_pos):
        data[f"pos{i}"] = [0.8]
    for i in range(n_neg):
        data[f"neg{i}"] = [-0.8]
    for i in range(n_net):
        data[f"net{i}"] = [0.0]
    return data


class TestResolveScenario:
    def test_cabang_konsensus(self):
        hasil = resolve_scenario(
            sentimen_agregat=_sentimen(8, 0, 2),
            n_agents=10,
            n_rounds=3,
            quality_score=1.0,
        )
        assert hasil["arah"] == "Konsensus"
        assert hasil["kekuatan"] == "Kuat"
        assert hasil["hitungan"] == {"mendukung": 8, "netral": 2, "menolak": 0}

    def test_cabang_polarisasi(self):
        hasil = resolve_scenario(
            sentimen_agregat=_sentimen(4, 6, 0),
            n_agents=10,
            n_rounds=3,
            quality_score=1.0,
        )
        assert hasil["arah"] == "Polarisasi"
        assert hasil["hitungan"]["menolak"] == 6

    def test_cabang_status_quo(self):
        hasil = resolve_scenario(
            sentimen_agregat=_sentimen(0, 0, 10),
            n_agents=10,
            n_rounds=3,
            quality_score=1.0,
        )
        assert hasil["arah"] == "Status Quo"
        assert hasil["hitungan"]["netral"] == 10

    def test_cabang_mixed_condong_status_quo(self):
        # Skor dekat ambang supaya variance < 0.3 dan tidak memicu cabang polarisasi.
        sentimen = {f"pos{i}": [0.3] for i in range(4)}
        sentimen.update({f"neg{i}": [-0.3] for i in range(3)})
        sentimen.update({f"net{i}": [0.0] for i in range(3)})
        hasil = resolve_scenario(
            sentimen_agregat=sentimen,
            n_agents=10,
            n_rounds=3,
            quality_score=1.0,
        )
        assert hasil["arah"] == "Status Quo"
        assert hasil["aturan"] == ">=60% netral ATAU tidak memenuhi ambang lain"


class TestKepercayaanSumber:
    def test_ok_relevan_cukup(self):
        hasil = kepercayaan_sumber("ok", 5, False, 10, 3)
        assert hasil["level"] == "Sedang"
        assert hasil["fakta"]["sumber_relevan"] == 5
        assert "hanya judul berita yang dibaca" in hasil["alasan"]

    def test_ok_relevan_kurang(self):
        hasil = kepercayaan_sumber("ok", 2, False, 10, 3)
        assert hasil["level"] == "Rendah"

    def test_kosong(self):
        hasil = kepercayaan_sumber("kosong", 0, False, 10, 3)
        assert hasil["level"] == "Rendah"
        assert "tidak ada artikel" in hasil["alasan"].lower()

    def test_gagal(self):
        hasil = kepercayaan_sumber("gagal", 0, False, 10, 3)
        assert hasil["level"] == "Rendah"
        assert "gagal" in hasil["alasan"].lower()

    def test_sedikit(self):
        hasil = kepercayaan_sumber("sedikit", 2, False, 10, 3)
        assert hasil["level"] == "Rendah"
        assert "2 artikel" in hasil["alasan"]


class TestTeksPolarisasi:
    def test_10_vs_2_bukan_polarisasi(self):
        skor = {f"pos{i}": 0.8 for i in range(10)}
        skor.update({f"neg{i}": -0.8 for i in range(2)})
        teks = teks_polarisasi(skor, total_peserta=12)
        assert "polarisasi" not in teks.lower()
        assert "Mayoritas mendukung" in teks

    def test_6_vs_6_polarisasi(self):
        skor = {f"pos{i}": 0.8 for i in range(6)}
        skor.update({f"neg{i}": -0.8 for i in range(6)})
        teks = teks_polarisasi(skor, total_peserta=12)
        assert "polarisasi" in teks.lower()
        assert "kubu terkecil: 6 orang (50%)" in teks


class TestSwingVoterTerfilter:
    def test_volatilitas_007_tidak_lolos(self):
        hasil = swing_voter_terfilter({"A": [0.0, 0.07]}, ambang=0.15)
        assert hasil["tidak_ada"] is True
        assert hasil["daftar"] == []

    def test_volatilitas_040_lolos(self):
        hasil = swing_voter_terfilter({"A": [0.0, 0.40]}, ambang=0.15)
        assert hasil["tidak_ada"] is False
        assert hasil["daftar"][0]["nama"] == "A"
        assert hasil["daftar"][0]["volatilitas"] == 0.4


def test_run_simulation_tanpa_konteks_real_tidak_fetch(monkeypatch):
    """run_simulation dengan konteks_real=None tidak boleh memanggil scraper."""
    import backend.scraper as scraper
    import backend.simulation as simulation

    def _boom(*args, **kwargs):
        raise AssertionError("run_simulation tidak boleh memanggil ambil_konteks_real")

    monkeypatch.setattr(scraper, "ambil_konteks_real", _boom, raising=False)
    monkeypatch.setattr(
        simulation,
        "call_llm",
        lambda *a, **kw: (
            '{"pendapat": "netral", "sentimen": {"label": "netral", "skor": 0.0}, '
            '"berubah_karena": "tes"}'
        ),
    )

    hasil = simulation.run_simulation(
        topik="Tes tanpa konteks",
        agents=[
            {"nama": "A", "role": "Tes", "pengaruh": 0.5, "initial_stance": 0.0, "kepribadian": {}, "memori": []},
            {"nama": "B", "role": "Tes", "pengaruh": 0.5, "initial_stance": 0.0, "kepribadian": {}, "memori": []},
        ],
        jumlah_ronde=1,
        tier="free",
    )
    assert "skenario_resolved" in hasil
    assert hasil["kepercayaan_sumber"]["level"] == "Rendah"


def _sentimen_skor(n_pos: int, n_neg: int, n_net: int, pos: float = 0.8, neg: float = -0.8) -> dict:
    data = {}
    for i in range(n_pos):
        data[f"pos{i}"] = [pos]
    for i in range(n_neg):
        data[f"neg{i}"] = [neg]
    for i in range(n_net):
        data[f"net{i}"] = [0.0]
    return data


@pytest.mark.parametrize(
    "n_pos,n_neg,n_net,expected",
    [
        (6, 0, 4, "Lemah"),   # tepat di ambang 0.6
        (7, 0, 3, "Sedang"),  # +10 pp
        (8, 0, 2, "Kuat"),    # +20 pp
    ],
)
def test_kekuatan_konsensus_batas(n_pos, n_neg, n_net, expected):
    hasil = resolve_scenario(_sentimen_skor(n_pos, n_neg, n_net), 10, 3, 1.0)
    assert hasil["arah"] == "Konsensus"
    assert hasil["kekuatan"] == expected


@pytest.mark.parametrize(
    "n_pos,n_neg,expected",
    [
        (5, 5, "Lemah"),   # pct_neg tepat 0.5
        (4, 6, "Sedang"),  # +10 pp
        (3, 7, "Kuat"),    # +20 pp
    ],
)
def test_kekuatan_polarisasi_batas(n_pos, n_neg, expected):
    # skor dekat ambang supaya variance tidak ikut memicu cabang polarisasi
    hasil = resolve_scenario(_sentimen_skor(n_pos, n_neg, 0, pos=0.3, neg=-0.3), 10, 3, 1.0)
    assert hasil["arah"] == "Polarisasi"
    assert hasil["kekuatan"] == expected


@pytest.mark.parametrize(
    "n_net,n_pos,expected",
    [
        (6, 4, "Lemah"),   # pct_net tepat 0.6
        (7, 3, "Sedang"),  # +10 pp
        (8, 2, "Kuat"),    # +20 pp
    ],
)
def test_kekuatan_status_quo_batas(n_net, n_pos, expected):
    hasil = resolve_scenario(_sentimen_skor(n_pos, 0, n_net, pos=0.3), 10, 3, 1.0)
    assert hasil["arah"] == "Status Quo"
    assert hasil["kekuatan"] == expected
