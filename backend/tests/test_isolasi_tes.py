"""Tes isolasi: folder data dan LLM tidak boleh menyentuh lingkungan nyata."""

import pytest

from backend import llm_guard
from backend.services import casestudy_assemble, run_store


def test_folder_data_mengarah_ke_tmp(tmp_path):
    assert run_store.DATA_DIR == tmp_path / "runs"
    assert casestudy_assemble.DATA_DIR == tmp_path / "case_studies"


def test_llm_nyata_diblokir():
    llm_guard._restore_real_client()
    with pytest.raises(RuntimeError, match="diblokir"):
        llm_guard._get_client()
