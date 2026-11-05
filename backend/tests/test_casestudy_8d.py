"""Test FASE 8d: whatif, catatan kubu, skenario, judul, dan sumber."""

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from backend.services import casestudy_assemble, narrator
from backend.services.casestudy_builder import build_computed, normalisasi_judul

FIXTURE = Path("backend/tests/fixtures/run_mbg_synthetic.json")


def _run(**ubah):
    run = json.loads(FIXTURE.read_text(encoding="utf-8"))
    run.update(ubah)
    return run


def _run_empat_agen():
    agen = ["Mahasiswa", "Pengusaha/UMKM", "Pekerja Kantoran", "Pemerintah"]
    stance = ["menolak", "menolak", "menolak", "netral"]
    return {
        "topik": "Apakah program MBG tepat sasaran?",
        "tanggal": "4 Nov 2026",
        "sumber": [],
        "agen": [{"nama": n} for n in agen],
        "ronde_detail": [
            {
                "ronde": 1,
                "agen": [
                    {"nama": n, "stance": s, "alasan": "Alasan uji.", "score": 0.0}
                    for n, s in zip(agen, stance)
                ],
            }
        ],
    }


def _assemble(run, monkeypatch):
    monkeypatch.setattr(casestudy_assemble, "load_run", lambda _id: run)
    monkeypatch.setattr(
        casestudy_assemble,
        "generate_narrative",
        lambda r, c=None: {
            **narrator._fallback_narrative(c),
            "narator_fallback": True,
            "narator_fallback_reason": "test",
        },
    )
    return casestudy_assemble.assemble_case_study("uji")


def test_case_study_run_biasa_tanpa_whatif(monkeypatch):
    case = _assemble(_run(), monkeypatch)
    assert "whatif" not in case


def test_catatan_kubu_generik():
    out = build_computed(_run_empat_agen())
    catatan = {k["tipe"]: k["catatan"] for k in out["kubu"]}
    assert catatan == {"tolak": "3 peserta menolak.", "netral": "1 peserta netral."}
    assert all("posyandu" not in c for c in catatan.values())


def test_skenario_tanpa_nama_agen_dan_cocok_dengan_kubu():
    run = _run_empat_agen()
    out = build_computed(run)
    kubu = {k["nama"]: k for k in out["kubu"]}
    nama_agen = {a["nama"] for a in run["agen"]}

    assert out["skenario"]
    for s in out["skenario"]:
        teks = f"{s['jika']} {s['maka']}"
        kubu_disebut = [n for n in kubu if n in teks]
        assert len(kubu_disebut) == 1
        k = kubu[kubu_disebut[0]]
        assert int(re.match(r"\d+", s["maka"]).group()) == len(k["agen"])
        assert s["dasar_agen"] in k["agen"]
        # tidak menyebut peserta yang tidak ada di run
        assert not any(nama in teks for nama in nama_agen)


@pytest.mark.parametrize(
    "masukan, harapan",
    [
        ("  apakah   program  MBG tepat sasaran ? ", "Apakah program MBG tepat sasaran?"),
        ("sudah tepat!", "Sudah tepat!"),
        ("dua  spasi", "Dua spasi"),
        ("", ""),
    ],
)
def test_normalisasi_judul(masukan, harapan):
    assert normalisasi_judul(masukan) == harapan


def test_judul_dinormalisasi_dan_judul_asli_disimpan(monkeypatch):
    asli = "  apakah   program  MBG tepat sasaran ? "
    case = _assemble(_run(topik=asli), monkeypatch)
    assert case["judul"] == "Apakah program MBG tepat sasaran?"
    assert case["judul_asli"] == asli


def test_judul_bersih_tanpa_judul_asli(monkeypatch):
    case = _assemble(_run(topik="Apakah program MBG tepat sasaran?"), monkeypatch)
    assert "judul_asli" not in case


def test_tanpa_sumber_konsisten():
    out = build_computed(_run(sumber=[]))
    assert out["meta"]["sumber"] == 0
    assert "tidak memakai artikel sumber" in out["keterbatasan"]
    assert out["situasi"]["sumber"] == "Sumber: 0 artikel RSS. Briefing terbatas."


def test_tanggal_dari_meta_saved_at():
    run = _run()
    run.pop("tanggal")
    run["_meta"] = {"saved_at": datetime(2026, 11, 4, 10, 0).timestamp()}
    assert build_computed(run)["meta"]["tanggal"] == "4 Nov 2026"
