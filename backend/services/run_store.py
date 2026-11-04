# backend/services/run_store.py
# Penyimpanan run simulasi: satu file JSON per run, tulis atomik + lock.

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from backend.core.models import SimulationState

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "runs"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def _slugify(teks: str) -> str:
    """Buat slug aman untuk nama file dari topik."""
    # Ambil 50 char pertama, ganti non-alnum dengan underscore
    aman = "".join(c if c.isalnum() else "_" for c in teks[:50])
    return aman.strip("_")


def _generate_id(topik: str) -> str:
    """ID = slug_topik + timestamp."""
    slug = _slugify(topik)
    ts = int(time.time() * 1000)
    return f"{slug}_{ts}"


def _atomic_write(path: Path, data: dict) -> None:
    """Tulis ke file sementara lalu rename (atomik di POSIX)."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # atomik


def save_run(run_data: dict) -> str:
    """
    Simpan satu run ke file JSON.

    Args:
        run_data: Dict lengkap hasil run_simulation (termasuk topik, ronde_detail, dll)

    Returns:
        ID run (nama file tanpa .json)
    """
    topik = run_data.get("topik", "simulasi")
    run_id = _generate_id(topik)
    path = DATA_DIR / f"{run_id}.json"

    # Tambahkan metadata simpan
    payload = dict(run_data)
    payload.setdefault("_meta", {})["saved_at"] = time.time()
    payload["_meta"]["id"] = run_id

    with _lock:
        _atomic_write(path, payload)

    return run_id


def load_run(run_id: str) -> dict | None:
    """
    Baca run berdasarkan ID.

    Args:
        run_id: ID yang dikembalikan save_run (tanpa .json)

    Returns:
        Dict run atau None jika tidak ditemukan.
    """
    path = DATA_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_runs(limit: int = 100, offset: int = 0) -> list[dict]:
    """
    Daftar run tersedia, terbaru dulu.

    Returns:
        List dict dengan kunci: id, topik, tanggal, mode, kualitas_status
    """
    files = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    hasil = []
    for f in files[offset : offset + limit]:
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            meta = data.get("_meta", {})
            kualitas = data.get("kualitas", {})
            hasil.append({
                "id": meta.get("id", f.stem),
                "topik": data.get("topik", ""),
                "tanggal": meta.get("saved_at"),
                "mode": data.get("mode", ""),
                "kualitas_status": kualitas.get("status", "unknown"),
                "total_giliran": kualitas.get("total_giliran"),
                "fallback_count": kualitas.get("fallback_count"),
            })
        except Exception:
            continue
    return hasil


# Backward compatibility: adapter dari SimulationState lama (jika diperlukan)
def state_to_run_dict(state: SimulationState, **extra) -> dict:
    """Konversi SimulationState ke format run yang bisa disimpan."""
    return {
        "topik": state.topik,
        "ronde_detail": [],  # butuh data lengkap dari simulation.py
        "agent_states": [s.model_dump() for s in state.agent_states],
        "events": [e.model_dump() for e in state.events],
        "polarization_score": state.polarization_score,
        "consensus_score": state.consensus_score,
        **extra,
    }