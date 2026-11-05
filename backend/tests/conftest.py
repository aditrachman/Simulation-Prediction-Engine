"""Global test configuration."""

from pathlib import Path

import pytest

from backend import feedback, llm, llm_guard, ml_pipeline
from backend.services import casestudy_assemble, run_store


class _GroqDiblokir:
    """Klien LLM palsu: gagal keras kalau ada tes yang mencoba panggilan nyata."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("Panggilan LLM nyata diblokir di tes")


# Patch time.sleep for slow tests
@pytest.fixture(autouse=True)
def patch_time_sleep(monkeypatch):
    """Auto-patch time.sleep to avoid real waits in tests."""
    monkeypatch.setattr('time.sleep', lambda *_: None)
    monkeypatch.setattr('backend.simulation.time.sleep', lambda *_: None)
    monkeypatch.setattr('backend.llm_guard.time.sleep', lambda *_: None)


@pytest.fixture(autouse=True)
def isolasi_data_dan_llm(tmp_path, monkeypatch):
    """Arahkan semua file data ke tmp_path dan blokir LLM nyata."""
    run_dir = tmp_path / "runs"
    case_dir = tmp_path / "case_studies"
    run_dir.mkdir()
    case_dir.mkdir()
    monkeypatch.setattr(run_store, "DATA_DIR", run_dir)
    monkeypatch.setattr(casestudy_assemble, "DATA_DIR", case_dir)

    monkeypatch.setattr(ml_pipeline, "DATA_DIR", tmp_path)
    for nama in ("HISTORY_FILE", "FEEDBACK_FILE", "MODEL_FILE", "ENCODER_FILE"):
        lama = getattr(ml_pipeline, nama, None)
        if lama is not None:
            monkeypatch.setattr(ml_pipeline, nama, tmp_path / Path(lama).name)
    monkeypatch.setattr(feedback, "FEEDBACK_FILE", tmp_path / "feedback.jsonl")

    llm.clear_llm_cache()
    monkeypatch.setattr(llm, "Groq", _GroqDiblokir)
    monkeypatch.setattr(llm_guard, "Groq", _GroqDiblokir)
