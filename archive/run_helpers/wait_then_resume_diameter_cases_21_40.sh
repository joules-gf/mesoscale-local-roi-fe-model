#!/usr/bin/env bash
set -u
cd /home/joules_gf/projects/dr-irwin-hermes/workspace/mesoscale-local-roi-fe-model

# Wait for the first attempt launched by Hermes to finish so we never run two
# Abaqus/MicroStructPy cases at the same time.
while pgrep -f "full_simulation_runner.py --input-folder simulation_inputs/AL7075-T6/bp_dif_size --input-file simulation_inputs/AL7075-T6/bp_dif_size/bp_size_case_21.xml" >/dev/null; do
    echo "$(date): waiting for active bp_size_case_21 run to finish before resuming cases 21-40..."
    sleep 60
done

chmod +x archive/run_helpers/run_diameter_cases_21_40_resume.sh
archive/run_helpers/run_diameter_cases_21_40_resume.sh
