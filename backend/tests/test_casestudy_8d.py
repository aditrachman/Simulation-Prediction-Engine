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


def test_load_case_study_membuang_whatif_lama(tmp_path, monkeypatch):
    monkeypatch.setattr(casestudy_assemble, "DATA_DIR", tmp_path)
    lama = {
        "judul": "Uji",
        "whatif": {"judul": "x", "deskripsi": "y", "sebelum": {"menolak": 1, "netral": 0, "mendukung": 0}, "sesudah": None},
    }
    (tmp_path / "lama.json").write_text(json.dumps(lama), encoding="utf-8")

    assert "whatif" not in casestudy_assemble.load_case_study("lama")


def test_load_case_study_mempertahankan_whatif_berjalan(tmp_path, monkeypatch):
    monkeypatch.setattr(casestudy_assemble, "DATA_DIR", tmp_path)
    baru = {
        "judul": "Uji",
        "whatif": {"judul": "x", "deskripsi": "y", "sebelum": {"menolak": 1, "netral": 0, "mendukung": 0}, "sesudah": {"menolak": 0, "netral": 1, "mendukung": 0}},
    }
    (tmp_path / "baru.json").write_text(json.dumps(baru), encoding="utf-8")

    assert casestudy_assemble.load_case_study("baru")["whatif"]["sesudah"]["netral"] == 1


def test_validator_memakai_agen_dari_ronde_detail():
    run = _run_empat_agen()
    run.pop("agen")
    computed = build_computed(run)
    nar = narrator._fallback_narrative(computed)
    assert narrator._validate_narrative(nar, computed, run) == []


def _run_non_mbg():
    agen = ["Mahasiswa", "Pemerintah"]
    return {
        "topik": "Apakah kenaikan tarif angkutan umum perlu ditinjau?",
        "tanggal": "4 Nov 2026",
        "agen": [{"nama": n} for n in agen],
        "ronde_detail": [
            {
                "ronde": 1,
                "agen": [
                    {
                        "nama": "Mahasiswa",
                        "stance": "menolak",
                        "alasan": "Tarif naik tanpa perbaikan layanan.",
                        "score": -0.6,
                    },
                    {
                        "nama": "Pemerintah",
                        "stance": "mendukung",
                        "alasan": "Kenaikan mengikuti biaya operasional.",
                        "score": 0.6,
                    },
                ],
            }
        ],
    }


def test_situasi_non_mbg_tanpa_naskah_tertanam(monkeypatch):
    run = _run_non_mbg()
    out = build_computed(run)
    assert out["situasi"]["pemicu"]["angka"] is None
    assert out["situasi"]["bahan"] == []
    assert "tarif angkutan umum" in out["situasi"]["pemicu"]["teks"]

    dump = json.dumps(_assemble(run, monkeypatch), ensure_ascii=False)
    for kata in ("72,8", "keracunan", "Desa X", "posyandu"):
        assert kata not in dump


def test_pemicu_angka_hanya_dari_briefing():
    out = build_computed(_run(briefing="Evaluasi: 55,5% responden puas.", sumber=[]))
    assert out["situasi"]["pemicu"]["angka"] == "55,5%"


def test_pemicu_angka_tanpa_persen_adalah_null():
    out = build_computed(_run(briefing="Tidak ada angka persen di sini.", sumber=[]))
    assert out["situasi"]["pemicu"]["angka"] is None


def test_kondisi_skenario_generik_tanpa_kata_mbg():
    out = build_computed(_run_non_mbg())
    assert out["skenario"]
    for s in out["skenario"]:
        kondisi = s["jika"].lower()
        assert "kubu" in kondisi
        for kata in ("mbg", "bantuan", "posyandu", "keracunan", "distribusi"):
            assert kata not in kondisi


def test_bersihkan_awalan_jika_maka():
    from backend.services.casestudy_builder import _bersihkan_awalan
    assert _bersihkan_awalan("Jika cuaca bagus") == "cuaca bagus"
    assert _bersihkan_awalan("Maka hasilnya baik") == "hasilnya baik"
    assert _bersihkan_awalan("Jika Jika bersarang") == "bersarang"
    assert _bersihkan_awalan("tidak ada awalan") == "tidak ada awalan"
    assert _bersihkan_awalan("  Jika  spasi  ") == "spasi"


def _run_sintetis(topik: str, agen_stances: list[tuple[str, str]], ronde: int = 1) -> dict:
    """Bangun run sintetis dengan topik non-MBG dan stance eksplisit."""
    agen = [{"nama": n} for n, _ in agen_stances]
    agen_runde = []
    for n, s in agen_stances:
        score = {"menolak": -0.6, "netral": 0.0, "mendukung": 0.6}[s]
        agen_runde.append({
            "nama": n, "stance": s, "score": score,
            "alasan": f"Alasan {n} untuk {s}.",
            "sesuai_topik": True,
        })
    return {
        "topik": topik,
        "tanggal": "5 Nov 2026",
        "agen": agen,
        "ronde_detail": [{"ronde": 1, "agen": agen_runde} for _ in range(ronde)],
    }


def test_kanari_empat_topik_non_mbg(monkeypatch):
    """4 run sintetis: semua mendukung, semua menolak, campuran, tanpa menolak."""
    topik_data = [
        ("Apakah ijazah presiden asli?", [("A", "mendukung"), ("B", "mendukung")]),
        ("Apakah kenaikan UKT adil?", [("X", "menolak"), ("Y", "menolak")]),
        ("Apakah motor listrik layak disubsidi?", [("P", "menolak"), ("Q", "netral"), ("R", "mendukung")]),
        ("Apakah program kerja sama fair?", [("M", "netral"), ("N", "mendukung")]),  # tanpa menolak
    ]
    
    leksikon_larang = [
        "mbg", "gizi", "makan", "keracunan", "72,8", "72.8", "kepuasan",
        "posyandu", "desa x", "miskin", "oposisi kritis", "tepat sasaran",
        "survei", "mempertanyakan", "apa arti angka", "isu bergeser"
    ]
    
    for topik, stances in topik_data:
        run = _run_sintetis(topik, stances)
        out = build_computed(run)
        dump = json.dumps(out, ensure_ascii=False).lower()
        
        # Assert leksikon MBG = 0
        for kata in leksikon_larang:
            assert kata not in dump, f"Kata larang '{kata}' ditemukan di {topik}: {dump[:500]}"
        
        # Assert kubu disebut = kubu yang ada
        kubu_nama = {k["nama"] for k in out["kubu"]}
        for s in out["skenario"]:
            teks = f"{s['jika']} {s['maka']}".lower()
            kubu_disebut = [n for n in kubu_nama if n.lower() in teks]
            assert len(kubu_disebut) <= 1, f"Terlalu banyak kubu disebut: {kubu_disebut}"
        
        # Assert angka di ringkas ronde = distribusi
        for r in out["ronde"]:
            dist = r["distribusi"]
            ringkas = r["ringkas"]
            for k in ("menolak", "netral", "mendukung"):
                assert str(dist[k]) in ringkas, f"Angka {k} tidak di ringkas: {ringkas}"
