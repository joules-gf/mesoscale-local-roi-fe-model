"""Run the 20 plastic/yield-stress sensitivity Abaqus jobs.

Run from the repository root after Abaqus is available on PATH, or after setting
MICROSTRUCTURE_ABAQUS_CMD. In WSL, the existing wsl_windows_compat bridge will
try `cmd.exe /C abaqus` when Windows Abaqus is exposed.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "00_Main_Scripts"))

from run_abaqus_sim import run_simulation  # noqa: E402
from wsl_windows_compat import AbaqusUnavailableError  # noqa: E402

STUDY_OUTPUT = ROOT / "simulation_outputs" / "plastic_stress_sensitivity"


def main() -> int:
    cases = [f"bp_plastic_stress_case_{i:02d}" for i in range(1, 21)]
    for case in cases:
        abaqus_dir = STUDY_OUTPUT / case / "abaqus_files"
        inp_file = abaqus_dir / f"{case}.inp"
        if not inp_file.exists():
            print(f"SKIP missing input: {inp_file}")
            continue
        print(f"\n=== Running {case} ===")
        run_simulation(str(abaqus_dir), case)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AbaqusUnavailableError as exc:
        print(f"\nAbaqus unavailable: {exc}")
        raise SystemExit(2) from exc
