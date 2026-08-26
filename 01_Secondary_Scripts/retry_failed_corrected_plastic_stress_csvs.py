from pathlib import Path
import shutil
import subprocess
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "simulation_outputs"
CORRECTED_SCRIPT = REPO_ROOT / "00_Main_Scripts" / "getForceDisp.py"
STAGE_ROOT = Path("/mnt/c/Users/Public/mesoscale_local_roi_fe_model_abaqus/corrected_plastic_stress_postprocess_retry")
CMD_EXE = "/mnt/c/Windows/System32/cmd.exe"
FAILED_CASES = [
    "plastic_stress_sensitivity/bp_plastic_stress_case_08",
    "plastic_stress_sensitivity/bp_plastic_stress_case_09",
    "plastic_stress_sensitivity_mesh00328_backup_20260624_144408/bp_plastic_stress_case_01",
    "plastic_stress_sensitivity_mesh00328_backup_20260624_144408/bp_plastic_stress_case_02",
    "plastic_stress_sensitivity_mesh00328_backup_20260624_144408/bp_plastic_stress_case_19",
    "plastic_stress_sensitivity_mesh00328_backup_20260624_144408/bp_plastic_stress_case_20",
]


def win_path(path: Path) -> str:
    return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()


def run_once(case_rel: str):
    case_dir = OUTPUT_ROOT / case_rel
    odbs = sorted((case_dir / "abaqus_files").glob("*.odb"))
    if len(odbs) != 1:
        return False, f"expected one ODB, found {len(odbs)}"
    odb = odbs[0]
    case_name = odb.stem
    corrected_csv = case_dir / f"{case_name}_corrected_nozip.csv"
    if corrected_csv.exists():
        return True, f"already exists {corrected_csv}"

    stage_case = STAGE_ROOT / case_rel
    stage_abaqus = stage_case / "abaqus_files"
    stage_scripts = stage_case / "_abaqus_scripts"
    stage_abaqus.mkdir(parents=True, exist_ok=True)
    stage_scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy2(odb, stage_abaqus / odb.name)
    shutil.copy2(CORRECTED_SCRIPT, stage_scripts / "getForceDisp.py")
    local_scripts = case_dir / "_abaqus_scripts"
    local_scripts.mkdir(exist_ok=True)
    shutil.copy2(CORRECTED_SCRIPT, local_scripts / "getForceDisp.py")

    produced_csv = stage_case / f"{case_name}.csv"
    if produced_csv.exists():
        produced_csv.unlink()

    bat_path = stage_case / "run_corrected_postprocess.bat"
    bat_path.write_text(
        "@echo off\n"
        f'cd /D "{win_path(stage_abaqus)}"\n'
        f"abaqus cae noGUI={win_path(stage_scripts / 'getForceDisp.py')}\n"
        "exit /b %ERRORLEVEL%\n",
        encoding="utf-8",
    )
    result = subprocess.run([CMD_EXE, "/C", win_path(bat_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0 or not produced_csv.exists():
        return False, result.stdout[-1200:]
    shutil.copy2(produced_csv, corrected_csv)
    return True, str(corrected_csv)


def main():
    failed = []
    for case_rel in FAILED_CASES:
        ok = False
        msg = ""
        for attempt in range(1, 4):
            print(f"{case_rel} attempt {attempt}", flush=True)
            ok, msg = run_once(case_rel)
            print(("OK: " if ok else "FAILED: ") + msg, flush=True)
            if ok:
                break
            time.sleep(2 * attempt)
        if not ok:
            failed.append((case_rel, msg))
    if failed:
        print("\nStill failed:")
        for case_rel, msg in failed:
            print(case_rel, msg)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
