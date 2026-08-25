#!/usr/bin/env bash
set -u

cd /home/joules_gf/projects/dr-irwin-hermes/workspace/microstructure_fatigue_simulation
source .venv/bin/activate
export MPLBACKEND=Agg
export MICROSTRUCTURE_NONINTERACTIVE=1

INPUT_DIR="simulation_inputs/AL7075-T6/bp_dif_size"
LOG_DIR="simulation_outputs/run_logs_diameter_cases_21_40"
mkdir -p "$LOG_DIR"

echo "Resume runner for diameter-size cases 21-40 at $(date)"
echo "Running serially and skipping cases whose ODB/CSV/PNG already exist."
echo

for n in $(seq -w 21 40); do
    case="bp_size_case_${n}"
    input_file="${INPUT_DIR}/${case}.xml"
    out_dir="simulation_outputs/${case}"
    case_log="${LOG_DIR}/${case}.log"
    csv_file="${out_dir}/${case}.csv"
    odb_file="${out_dir}/abaqus_files/${case}.odb"
    png_file="${out_dir}/stress_strain_${case}.png"

    if [[ -s "$csv_file" && -s "$odb_file" && -s "$png_file" ]]; then
        echo "===== ${case}: already verified; skipping ====="
        continue
    fi

    echo "===== ${case}: START $(date) ====="
    if [[ ! -f "$input_file" ]]; then
        echo "ERROR: missing input file $input_file" | tee -a "$case_log"
        exit 1
    fi

    python 00_Main_Scripts/full_simulation_runner.py --input-folder "$INPUT_DIR" --input-file "$input_file" 2>&1 | tee "$case_log"
    status=${PIPESTATUS[0]}
    if [[ $status -ne 0 ]]; then
        echo "===== ${case}: FAILED with exit code ${status} at $(date) ====="
        exit $status
    fi

    missing=0
    for f in "$csv_file" "$odb_file" "$png_file"; do
        if [[ ! -s "$f" ]]; then
            echo "ERROR: expected artifact missing or empty: $f"
            missing=1
        fi
    done
    if [[ $missing -ne 0 ]]; then
        echo "===== ${case}: ARTIFACT VERIFICATION FAILED at $(date) ====="
        exit 1
    fi

    echo "===== ${case}: COMPLETE + VERIFIED $(date) ====="
    echo

done

echo "All cases 21-40 completed and verified at $(date)"
