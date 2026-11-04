# backend/routers/case_study.py
# Router untuk endpoint Case Study (FASE 5c/5d).

from fastapi import APIRouter, HTTPException
from pathlib import Path

from backend.services.run_store import list_runs, load_run

router = APIRouter(prefix="/case-study", tags=["case-study"])


@router.get("")
async def list_case_studies(limit: int = 50, offset: int = 0):
    """Daftar semua run studi kasus tersimpan."""
    items = list_runs(limit=limit, offset=offset)
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{run_id}/raw")
async def get_case_study_raw(run_id: str):
    """Ambil data run mentah (RunResult) berdasarkan ID."""
    data = load_run(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} tidak ditemukan")
    return data