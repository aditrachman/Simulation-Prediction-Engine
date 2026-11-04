#!/usr/bin/env python3
# scripts/export_case_study.py
# Export CaseStudy ke file JSON (untuk fallback frontend).
# Tidak menimpa frontend/template/mbg.json.

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.casestudy_assemble import load_case_study, assemble_case_study
from backend.services.run_store import load_run

PRESETS_FILE = ROOT / "backend" / "data" / "presets.json"


def load_presets() -> dict:
    if PRESETS_FILE.exists():
        with open(PRESETS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def resolve_id(id_or_alias: str) -> str:
    presets = load_presets()
    return presets.get(id_or_alias, id_or_alias)


def main():
    parser = argparse.ArgumentParser(description="Export CaseStudy ke file JSON")
    parser.add_argument("id_or_alias", help="Run ID atau alias preset")
    parser.add_argument("output", help="Path file output (contoh: exported/mbg.json)")
    parser.add_argument(
        "--assemble",
        action="store_true",
        help="Jalankan assemble (panggil narator LLM) jika cache tidak ada",
    )
    args = parser.parse_args()

    run_id = resolve_id(args.id_or_alias)

    # Cek cache dulu
    case = None
    if not args.assemble:
        case = load_case_study(run_id)  # Mencoba load dari cache case_studies/
        if case is None:
            # Coba load run dan assemble tanpa narator (fallback only)
            from backend.services.casestudy_builder import build_computed
            from backend.services.narrator import _fallback_narrative

            run = load_run(run_id)
            if run is None:
                print(f"Error: Run {run_id} tidak ditemukan", file=sys.stderr)
                sys.exit(1)
            computed = build_computed(run)
            narrative = _fallback_narrative(computed)
            case_dict = {
                **computed,
                **narrative,
                "judul": run.get("topik", ""),
                "kategori": run.get("kategori", "Umum"),
            }
            from backend.core.case_study_schema import CaseStudy
            case_obj = CaseStudy.model_validate(case_dict)
            case = case_obj.model_dump(by_alias=True, exclude_none=True)
    else:
        # Assemble penuh (panggil narator LLM)
        from backend.services.casestudy_assemble import assemble_case_study
        try:
            case = assemble_case_study(run_id)
        except Exception as e:
            print(f"Error assembling: {e}", file=sys.stderr)
            sys.exit(1)

    if case is None:
        print("Error: CaseStudy tidak bisa dibangun", file=sys.stderr)
        sys.exit(1)

    # Validasi output path
    out_path = Path(args.output)
    template_path = ROOT / "frontend" / "template" / "mbg.json"
    try:
        if out_path.resolve() == template_path.resolve():
            print(f"Error: Tidak boleh menimpa {template_path}", file=sys.stderr)
            sys.exit(1)
    except Exception:
        pass  # jika path tidak exist, resolve bisa gagal tapi itu ok

    # Tulis file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)

    print(f"OK: CaseStudy diekspor ke {out_path}")


if __name__ == "__main__":
    main()