# backend/services/casestudy_assemble.py
# Assemble CaseStudy: build_computed + generate_narrative -> CaseStudy object.
# Validasi Pydantic, simpan ke file (atomik + lock).

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from backend.core.case_study_schema import CaseStudy
from backend.services.casestudy_builder import build_computed
from backend.services.narrator import generate_narrative
from backend.services.run_store import load_run

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "case_studies"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def _atomic_write(path: Path, data: dict) -> None:
    """Tulis ke file sementara lalu rename (atomik di POSIX)."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)  # atomik


def assemble_case_study(run_id: str) -> dict:
    """
    Bangun CaseStudy lengkap dari run_id.

    Args:
        run_id: ID run (dari save_run atau preset alias).

    Returns:
        Dict CaseStudy (sudah divalidasi model Pydantic).

    Raises:
        FileNotFoundError: Jika run_id tidak ditemukan.
        ValueError: Jika validasi CaseStudy gagal.
    """
    run = load_run(run_id)
    if run is None:
        raise FileNotFoundError(f"Run {run_id} tidak ditemukan")

    # 1. Computed fields (tanpa LLM)
    computed = build_computed(run)

    # 2. Narasi dari LLM (satu panggilan)
    narrative = generate_narrative(run, computed)

    # 3. Gabung jadi CaseStudy dict
    case_dict = {
        **computed,
        **narrative,
        "judul": run.get("topik", ""),
        "kategori": run.get("kategori", "Umum"),
    }

    # 4. Validasi dengan Pydantic (by_alias=True untuk output)
    try:
        case_obj = CaseStudy.model_validate(case_dict)
    except Exception as e:
        raise ValueError(f"Validasi CaseStudy gagal: {e}")

    return case_obj.model_dump(by_alias=True, exclude_none=True)


def save_case_study(case_id: str, case_dict: dict) -> None:
    """Simpan CaseStudy ke file (atomik + lock)."""
    path = DATA_DIR / f"{case_id}.json"
    with _lock:
        _atomic_write(path, case_dict)


def load_case_study(case_id: str) -> dict | None:
    """Baca CaseStudy dari file."""
    path = DATA_DIR / f"{case_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_case_studies(limit: int = 100, offset: int = 0) -> list[dict]:
    """Daftar CaseStudy tersimpan, terbaru dulu."""
    files = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    hasil = []
    for f in files[offset : offset + limit]:
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            kualitas = data.get("kualitas", {})
            hasil.append({
                "id": data.get("id") or f.stem,
                "judul": data.get("judul", ""),
                "tanggal": data.get("meta", {}).get("tanggal"),
                "kualitas_status": kualitas.get("status", "unknown"),
                "narator_fallback": data.get("narator_fallback"),
            })
        except Exception:
            continue
    return hasil