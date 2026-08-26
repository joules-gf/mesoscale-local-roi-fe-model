#!/usr/bin/env bash
set -u

cd /home/joules_gf/projects/dr-irwin-hermes/workspace/mesoscale-local-roi-fe-model
source .venv/bin/activate
export MPLBACKEND=Agg
export MICROSTRUCTURE_NONINTERACTIVE=1

INPUT_DIR="simulation_inputs/AL7075-T6/bp_dif_size"
LOG_DIR="simulation_outputs/diameter_size_sensitivity/run_logs_cases_21_40"
mkdir -p "$LOG_DIR"

echo "Starting diameter-size cases 21-40 at $(date)"
echo "Running serially: each case must finish and verify before the next starts."
echo

for n in $(seq -w 21 40); do
    case="bp_size_case_${n}"
    input_file="${INPUT_DIR}/${case}.xml"
    out_dir="simulation_outputs/diameter_size_sensitivity/${case}"
    case_log="${LOG_DIR}/${case}.log"

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

    csv_file="${out_dir}/${case}.csv"
    odb_file="${out_dir}/abaqus_files/${case}.odb"
    png_file="${out_dir}/stress_strain_${case}.png"

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
