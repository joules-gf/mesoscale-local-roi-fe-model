#!/usr/bin/env python3
"""Robust resume runner for diameter-size cases 21-40.

This handles the August 2026 situation where bp_size_case_21 solved on the
Windows Abaqus staging directory, but the ODB/CSV/plots were not copied back to
WSL before the batch stopped.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# This script is archived under archive/run_helpers/ for provenance.  Keep it
# runnable from its archived location by resolving back to the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "simulation_inputs" / "AL7075-T6" / "bp_dif_size"
OUTPUT_ROOT = PROJECT_ROOT / "simulation_outputs"
WINDOWS_STAGE_ROOT = Path("/mnt/c/Users/Public/mesoscale_local_roi_fe_model_abaqus")
LOG_DIR = OUTPUT_ROOT / "run_logs_diameter_cases_21_40"

sys.path.insert(0, str(PROJECT_ROOT / "00_Main_Scripts"))
from full_simulation_runner import run_full_simulation  # noqa: E402
from postprocessing_abaqus_sim_v01 import post_processing  # noqa: E402


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("RUN:", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def copy_tree_contents(src: Path, dst: Path) -> None:
    """Copy contents with cp -a to handle large ODB files reliably under WSL."""
    dst.mkdir(parents=True, exist_ok=True)
    run(["cp", "-a", str(src) + "/.", str(dst) + "/"])


def sta_success(sta_path: Path) -> bool:
    if not sta_path.exists():
        return False
    text = sta_path.read_text(errors="ignore")
    return "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in text


def artifact_paths(case: str) -> dict[str, Path]:
    out_dir = OUTPUT_ROOT / case
    abaqus_dir = out_dir / "abaqus_files"
    return {
        "out_dir": out_dir,
        "abaqus_dir": abaqus_dir,
        "odb": abaqus_dir / f"{case}.odb",
        "sta": abaqus_dir / f"{case}.sta",
        "csv": out_dir / f"{case}.csv",
        "stress_png": out_dir / f"stress_strain_{case}.png",
        "cyclic_png": out_dir / f"cyclic_stress_strain_{case}.png",
        "cycles_png": out_dir / f"cycles_{case}.png",
    }


def basic_complete(case: str) -> bool:
    p = artifact_paths(case)
    return (
        p["odb"].is_file()
        and p["odb"].stat().st_size > 0
        and sta_success(p["sta"])
        and p["csv"].is_file()
        and p["csv"].stat().st_size > 0
        and p["stress_png"].is_file()
        and p["stress_png"].stat().st_size > 0
    )


def copy_back_existing_windows_solve(case: str) -> None:
    """If a case solved in C:\ staging but was not copied back, bring it home."""
    p = artifact_paths(case)
    stage_dir = WINDOWS_STAGE_ROOT / case
    stage_odb = stage_dir / "abaqus_files" / f"{case}.odb"
    stage_sta = stage_dir / "abaqus_files" / f"{case}.sta"
    if p["odb"].exists():
        return
    if stage_odb.exists() and sta_success(stage_sta):
        print(f"{case}: found successful Windows-staged solve; copying back to WSL output folder", flush=True)
        copy_tree_contents(stage_dir, p["out_dir"])


def run_postprocess_if_needed(case: str) -> None:
    p = artifact_paths(case)
    if not p["odb"].exists():
        return
    if p["csv"].exists() and p["stress_png"].exists() and p["cycles_png"].exists() and p["cyclic_png"].exists():
        print(f"{case}: postprocessing artifacts already present", flush=True)
        return
    print(f"{case}: running ODB postprocessing and plots", flush=True)
    post_processing(str(p["abaqus_dir"]), case, (True, False, True))


def verify_case(case: str) -> None:
    p = artifact_paths(case)
    missing = []
    for key in ["odb", "sta", "csv", "stress_png", "cycles_png", "cyclic_png"]:
        path = p[key]
        if not path.exists() or path.stat().st_size <= 0:
            missing.append(str(path.relative_to(PROJECT_ROOT)))
    if not sta_success(p["sta"]):
        missing.append(f"{p['sta'].relative_to(PROJECT_ROOT)} lacks successful Abaqus completion line")
    if missing:
        raise RuntimeError(f"{case}: missing/invalid artifacts: " + "; ".join(missing))
    print(f"{case}: COMPLETE + VERIFIED", flush=True)


def main() -> int:
    os.chdir(PROJECT_ROOT)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MICROSTRUCTURE_NONINTERACTIVE", "1")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    print("Robust diameter-size resume for bp_size_case_21 through bp_size_case_40", flush=True)
    for i in range(21, 41):
        case = f"bp_size_case_{i:02d}"
        input_file = INPUT_DIR / f"{case}.xml"
        print(f"\n===== {case}: CHECK =====", flush=True)
        if not input_file.exists():
            raise FileNotFoundError(input_file)

        copy_back_existing_windows_solve(case)
        if basic_complete(case):
            run_postprocess_if_needed(case)  # fills optional cyclic/cycles if needed
            verify_case(case)
            continue

        p = artifact_paths(case)
        if p["odb"].exists() and sta_success(p["sta"]):
            run_postprocess_if_needed(case)
            verify_case(case)
            continue

        print(f"{case}: running full simulation from input {input_file.relative_to(PROJECT_ROOT)}", flush=True)
        run_full_simulation(
            input_files_folder=str(INPUT_DIR),
            input_file=str(input_file),
            run_abaqus=True,
            run_postprocessing=True,
        )
        verify_case(case)

    print("\nALL CASES 21-40 COMPLETE + VERIFIED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
