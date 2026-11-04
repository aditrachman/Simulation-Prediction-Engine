# backend/routers/case_study.py
# Router untuk endpoint Case Study (FASE 5c/5d + FASE 8).

from fastapi import APIRouter, HTTPException, Depends, Header
from pathlib import Path
import os
import hmac

from backend.services.run_store import list_runs, load_run
from backend.services.casestudy_assemble import (
    assemble_case_study,
    load_case_study,
    list_case_studies,
)
from backend.core.case_study_schema import CaseStudy

router = APIRouter(prefix="/case-study", tags=["case-study"])

# ── Admin token config ───────────────────────────────────────────────────────
CASE_STUDY_ADMIN_TOKEN = os.getenv("CASE_STUDY_ADMIN_TOKEN", "")


def _verify_admin_token(x_admin_token: str | None = Header(None)) -> bool:
    """Verify admin token using constant-time comparison."""
    if not CASE_STUDY_ADMIN_TOKEN:
        return False
    if not x_admin_token:
        return False
    return hmac.compare_digest(x_admin_token, CASE_STUDY_ADMIN_TOKEN)


def _require_admin(x_admin_token: str | None = Header(None)) -> None:
    """Dependency to require valid admin token."""
    if not _verify_admin_token(x_admin_token):
        raise HTTPException(
            status_code=403,
            detail="Admin token required. Set X-Admin-Token header with valid CASE_STUDY_ADMIN_TOKEN.",
        )


# ── Preset alias resolution ──────────────────────────────────────────────────
PRESETS_FILE = Path(__file__).resolve().parents[2] / "data" / "presets.json"


def _load_presets() -> dict:
    if PRESETS_FILE.exists():
        with open(PRESETS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _resolve_id(id_or_alias: str) -> str:
    """Resolve alias ke run_id. Jika sudah run_id, kembalikan apa adanya."""
    presets = _load_presets()
    return presets.get(id_or_alias, id_or_alias)


import json


@router.get("")
async def list_case_studies(limit: int = 50, offset: int = 0):
    """Daftar CaseStudy publik (hanya yang punya alias/preset)."""
    presets = _load_presets()
    items = []
    for alias, run_id in presets.items():
        cached = load_case_study(run_id)
        if cached:
            kualitas = cached.get("kualitas", {})
            items.append({
                "id": run_id,
                "alias": alias,
                "judul": cached.get("judul", ""),
                "tanggal": cached.get("meta", {}).get("tanggal"),
                "kualitas_status": kualitas.get("status", "unknown"),
                "narator_fallback": cached.get("narator_fallback"),
            })
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/runs")
async def list_runs_raw(limit: int = 50, offset: int = 0, _: None = Depends(_require_admin)):
    """Daftar run mentah (RunResult) dari run_store. Admin only."""
    items = list_runs(limit=limit, offset=offset)
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{id_or_alias}/raw")
async def get_case_study_raw(id_or_alias: str, _: None = Depends(_require_admin)):
    """Ambil data run mentah (RunResult) berdasarkan ID atau alias. Admin only."""
    run_id = _resolve_id(id_or_alias)
    data = load_run(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} tidak ditemukan")
    return data


@router.get("/{id_or_alias}")
async def get_case_study(id_or_alias: str):
    """
    Ambil CaseStudy lengkap (sudah di-assemble + narator).
    - id_or_alias: bisa run_id atau alias preset.
    - 404 jika tidak ditemukan.
    - 409 jika kualitas.status == "degraded" (data tidak layak dirangkai).
    - 200 untuk "ok" dan "warning" (kualitas ikut di respons).
    """
    run_id = _resolve_id(id_or_alias)

    # Cek cache di case_studies/ dulu
    cached = load_case_study(run_id)
    if cached:
        kualitas = cached.get("kualitas", {})
        if kualitas.get("status") == "degraded":
            raise HTTPException(
                status_code=409,
                detail=f"CaseStudy {run_id} degraded: {kualitas.get('fallback_count', 0)}/{kualitas.get('total_giliran', 0)} giliran fallback. Hasil tidak layak dirangkai.",
            )
        return cached

    # Belum ada cache → assemble
    try:
        case_dict = assemble_case_study(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} tidak ditemukan")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Cek kualitas setelah assemble
    kualitas = case_dict.get("kualitas", {})
    if kualitas.get("status") == "degraded":
        raise HTTPException(
            status_code=409,
            detail=f"CaseStudy {run_id} degraded: {kualitas.get('fallback_count', 0)}/{kualitas.get('total_giliran', 0)} giliran fallback. Hasil tidak layak dirangkai.",
        )

    # Simpan cache
    save_case_study(run_id, case_dict)

    return case_dict


@router.post("/{id_or_alias}/regenerate-narrative")
async def regenerate_narrative(id_or_alias: str, _: None = Depends(_require_admin)):
    """
    Jalankan ulang narator (LLM) dan timpa cache CaseStudy.
    - Tolak jika kualitas == "degraded".
    - Berguna saat narator_fallback=true karena kuota habis.
    """
    run_id = _resolve_id(id_or_alias)

    # Cek run exists
    run = load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} tidak ditemukan")

    # Cek kualitas run (sebelum assemble)
    kualitas = run.get("kualitas", {})
    if kualitas.get("status") == "degraded":
        raise HTTPException(
            status_code=409,
            detail="Tidak bisa regenerate: run degraded (fallback terlalu banyak).",
        )

    # Assemble ulang (narator dijalankan ulang via generate_narrative)
    try:
        case_dict = assemble_case_study(run_id)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Simpan ulang cache
    save_case_study(run_id, case_dict)

    return {"message": "Narator berhasil di-regenerate", "case_study_id": run_id}


def save_case_study(case_id: str, case_dict: dict) -> None:
    """Simpan CaseStudy ke file (atomik + lock). Re-export dari casestudy_assemble."""
    from backend.services.casestudy_assemble import save_case_study as _save
    _save(case_id, case_dict)


def load_case_study(case_id: str) -> dict | None:
    from backend.services.casestudy_assemble import load_case_study as _load
    return _load(case_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(router, host="0.0.0.0", port=8000)