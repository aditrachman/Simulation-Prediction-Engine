#!/usr/bin/env python3
# scripts/make_preset.py
# Buat preset alias -> run_id.
# Menolak run yang kualitasnya bukan "ok", dan narator_fallback true kecuali --allow-fallback.

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.run_store import load_run
from backend.services.casestudy_assemble import load_case_study

PRESETS_FILE = ROOT / "backend" / "data" / "presets.json"


def load_presets() -> dict:
    if PRESETS_FILE.exists():
        with open(PRESETS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_presets(presets: dict) -> None:
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Buat preset alias -> run_id")
    parser.add_argument("run_id", help="ID run (dari run_store)")
    parser.add_argument("alias", help="Alias preset (contoh: mbg-2026)")
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Izinkan run dengan narator_fallback=true",
    )
    args = parser.parse_args()

    # Load run
    run = load_run(args.run_id)
    if run is None:
        print(f"Error: Run {args.run_id} tidak ditemukan", file=sys.stderr)
        sys.exit(1)

    # Cek kualitas run
    kualitas = run.get("kualitas", {})
    if kualitas.get("status") != "ok":
        print(
            f"Error: Run {args.run_id} kualitas '{kualitas.get('status')}' bukan 'ok'",
            file=sys.stderr,
        )
        sys.exit(1)

    # Cek CaseStudy cache (untuk narator_fallback)
    case = load_case_study(args.run_id)
    if case and case.get("narator_fallback") and not args.allow_fallback:
        print(
            f"Error: CaseStudy {args.run_id} punya narator_fallback=true. "
            "Gunakan --allow-fallback untuk memaksa.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Simpan preset
    presets = load_presets()
    if args.alias in presets and presets[args.alias] != args.run_id:
        print(
            f"Error: Alias '{args.alias}' sudah terpakai untuk run lain ({presets[args.alias]})",
            file=sys.stderr,
        )
        sys.exit(1)

    presets[args.alias] = args.run_id
    save_presets(presets)
    print(f"OK: Preset '{args.alias}' -> {args.run_id}")


if __name__ == "__main__":
    main()