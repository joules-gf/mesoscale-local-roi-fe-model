"""Regenerate plastic-stress sensitivity CSVs with corrected no-zip RF extraction.

This script stages one ODB at a time on a Windows-backed path, runs Abaqus/CAE
noGUI with the corrected 00_Main_Scripts/getForceDisp.py, and copies the result
back as <case>_corrected_nozip.csv without overwriting the original CSV.
"""
from pathlib import Path
import shutil
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
CORRECTED_SCRIPT = REPO_ROOT / "00_Main_Scripts" / "getForceDisp.py"
OUTPUT_ROOT = REPO_ROOT / "simulation_outputs"
TARGET_GROUPS = [
    "plastic_stress_sensitivity",
    "plastic_stress_sensitivity_mesh00328_backup_20260624_144408",
]
STAGE_ROOT = Path("/mnt/c/Users/Public/microstructure_fatigue_simulation_abaqus/corrected_plastic_stress_postprocess")
CMD_EXE = "/mnt/c/Windows/System32/cmd.exe"


def win_path(path: Path) -> str:
    return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()


def run_case(case_dir: Path) -> tuple[bool, str]:
    odbs = sorted((case_dir / "abaqus_files").glob("*.odb"))
    if len(odbs) != 1:
        return False, f"expected one ODB, found {len(odbs)}"

    odb = odbs[0]
    case_name = odb.stem
    stage_case = STAGE_ROOT / case_dir.relative_to(OUTPUT_ROOT)
    stage_abaqus = stage_case / "abaqus_files"
    stage_scripts = stage_case / "_abaqus_scripts"
    stage_abaqus.mkdir(parents=True, exist_ok=True)
    stage_scripts.mkdir(parents=True, exist_ok=True)

    staged_odb = stage_abaqus / odb.name
    staged_script = stage_scripts / "getForceDisp.py"
    shutil.copy2(odb, staged_odb)
    shutil.copy2(CORRECTED_SCRIPT, staged_script)

    # Also update the case-local script copy so future manual reruns use the fixed default.
    local_scripts = case_dir / "_abaqus_scripts"
    local_scripts.mkdir(exist_ok=True)
    shutil.copy2(CORRECTED_SCRIPT, local_scripts / "getForceDisp.py")

    produced_csv = stage_case / f"{case_name}.csv"
    if produced_csv.exists():
        produced_csv.unlink()

    win_abaqus_dir = win_path(stage_abaqus)
    win_script = win_path(staged_script)
    bat_path = stage_case / "run_corrected_postprocess.bat"
    bat_path.write_text(
        "@echo off\n"
        f'cd /D "{win_abaqus_dir}"\n'
        f"abaqus cae noGUI={win_script}\n"
        "exit /b %ERRORLEVEL%\n",
        encoding="utf-8",
    )
    result = subprocess.run([CMD_EXE, "/C", win_path(bat_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0 or not produced_csv.exists():
        return False, result.stdout[-2000:]

    corrected_csv = case_dir / f"{case_name}_corrected_nozip.csv"
    shutil.copy2(produced_csv, corrected_csv)
    return True, str(corrected_csv)


def main() -> int:
    cases = []
    for group in TARGET_GROUPS:
        group_dir = OUTPUT_ROOT / group
        cases.extend(sorted(group_dir.glob("bp_plastic_stress_case_*")))

    print(f"Cases to process: {len(cases)}")
    failures = []
    for i, case_dir in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case_dir.relative_to(OUTPUT_ROOT)}", flush=True)
        ok, message = run_case(case_dir)
        if ok:
            print(f"  wrote {message}", flush=True)
        else:
            print(f"  FAILED: {message}", flush=True)
            failures.append((case_dir, message))

    if failures:
        print("\nFailures:")
        for case_dir, message in failures:
            print(case_dir.relative_to(OUTPUT_ROOT), message)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
