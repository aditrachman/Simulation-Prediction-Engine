"""Test FASE 8d: whatif, catatan kubu, skenario, judul, dan sumber."""

import json
from pathlib import Path

from backend.services import casestudy_assemble, narrator
from backend.services.casestudy_builder import build_computed

FIXTURE = Path("backend/tests/fixtures/run_mbg_synthetic.json")


def _run(**ubah):
    run = json.loads(FIXTURE.read_text(encoding="utf-8"))
    run.update(ubah)
    return run


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
