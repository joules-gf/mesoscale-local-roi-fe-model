#!/usr/bin/env bash
set -euo pipefail

cd /home/joules_gf/projects/dr-irwin-hermes/workspace/mesoscale-local-roi-fe-model
source .venv/bin/activate
export MPLBACKEND=Agg
export MICROSTRUCTURE_NONINTERACTIVE=1
export PYTHONUNBUFFERED=1

CASE="bp_size_case_28"
CASE_DIR="simulation_outputs/${CASE}"
ABAQUS_DIR="${CASE_DIR}/abaqus_files"
LOG_DIR="simulation_outputs/run_logs_diameter_cases_21_40"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/${CASE}_fixed_elset_wrap_$(date +%Y%m%d_%H%M%S).log"

exec > >(tee "$LOG_FILE") 2>&1

echo "===== ${CASE}: fixed elset-wrap rerun START $(date) ====="
echo "Log: $LOG_FILE"

python - <<'PY'
from pathlib import Path
import shutil
import sys

root = Path.cwd()
case = "bp_size_case_28"
case_dir = root / "simulation_outputs" / case
abaqus_dir = case_dir / "abaqus_files"
inp = abaqus_dir / f"{case}.inp"
if not inp.exists():
    raise FileNotFoundError(inp)

backup = abaqus_dir / ("failed_job_backup_before_elset_wrap_rerun")
backup.mkdir(exist_ok=True)
for item in list(abaqus_dir.iterdir()):
    if item.name == inp.name or item.name == backup.name:
        continue
    target = backup / item.name
    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    shutil.move(str(item), str(target))
print(f"Backed up old failed Abaqus job files to {backup.relative_to(root)}")

sys.path.insert(0, str(root / "00_Main_Scripts"))
from abaqus_input_generation_v02 import wrap_abaqus_elset_include_lines
wrap_abaqus_elset_include_lines(str(inp), max_line_length=160)

bad = []
in_elset = False
for line_no, line in enumerate(inp.read_text(errors="ignore").splitlines(), 1):
    stripped = line.strip()
    if stripped.startswith("*"):
        in_elset = stripped.lower().startswith("*elset")
        continue
    if in_elset and "Set-E-Seed-" in line and len(line) > 160:
        bad.append((line_no, len(line)))
if bad:
    raise RuntimeError(f"Still found overlong Set-E-Seed elset lines: {bad[:10]}")
print("Verified wrapped material/seed elset include lines are <= 160 chars.")
PY

python - <<'PY'
from pathlib import Path
import sys
root = Path.cwd()
sys.path.insert(0, str(root / "00_Main_Scripts"))
from run_abaqus_sim import run_simulation
run_simulation(str(root / "simulation_outputs" / "bp_size_case_28" / "abaqus_files"), "bp_size_case_28")
PY

python - <<'PY'
from pathlib import Path
import sys
root = Path.cwd()
sys.path.insert(0, str(root / "00_Main_Scripts"))
from postprocessing_abaqus_sim_v01 import post_processing
post_processing(str(root / "simulation_outputs" / "bp_size_case_28" / "abaqus_files"), "bp_size_case_28", (True, False, True))
PY

python - <<'PY'
from pathlib import Path
import csv
root = Path.cwd()
case = "bp_size_case_28"
case_dir = root / "simulation_outputs" / case
abaqus_dir = case_dir / "abaqus_files"
sta = abaqus_dir / f"{case}.sta"
odb = abaqus_dir / f"{case}.odb"
csv_path = case_dir / f"{case}.csv"
png = case_dir / f"stress_strain_{case}.png"
errors = []
if not sta.exists():
    errors.append(f"missing {sta}")
elif "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" not in sta.read_text(errors="ignore"):
    errors.append(f"{sta} does not contain successful completion line")
for path in [odb, csv_path, png]:
    if not path.exists() or path.stat().st_size <= 0:
        errors.append(f"missing/empty {path}")
rows = []
if csv_path.exists():
    text = csv_path.read_text(errors="ignore").splitlines()
    header_idx = next((i for i, line in enumerate(text) if "U_Y" in line and "Total RF Y" in line), None)
    if header_idx is not None:
        reader = csv.DictReader(text[header_idx:])
        for row in reader:
            try:
                float(row["U_Y"]); float(row["Total RF Y"])
                rows.append(row)
            except Exception:
                pass
    if not rows:
        errors.append(f"{csv_path} has no numeric force-displacement rows")
if errors:
    raise RuntimeError("Verification failed:\n" + "\n".join(errors))
print(f"VERIFIED {case}: successful .sta, ODB size={odb.stat().st_size}, numeric CSV rows={len(rows)}, PNG size={png.stat().st_size}")
PY

echo "===== ${CASE}: fixed elset-wrap rerun COMPLETE $(date) ====="
