# Archived run helpers

This folder preserves one-off batch runners, resume scripts, and monitoring helpers that were useful for specific Abaqus simulation campaigns.

These scripts were moved out of the repository root during cleanup so the top level stays focused on reusable project entry points and documentation.

## How to treat these files

- Keep them as provenance for how specific AA2024 and diameter-size batches were launched or recovered.
- Prefer `00_Main_Scripts/full_simulation_runner.py` for normal new runs.
- Before reusing an archived helper, read it first and verify paths, input XML names, output folders, and Windows Abaqus staging directories still match the current repo state.
- These helpers may create large ignored outputs under `simulation_outputs/` or Windows staging folders.

## Archived groups

- `run_aa2024_*.py` and `monitor_and_postprocess_aa2024_t351.py` — AA2024-T351 full-cycle, requested rerun, standard-deviation, adaptive, and VF/yield rerun helpers.
- `run_diameter_cases_21_40*.sh` and `run_diameter_cases_21_40_robust_resume.py` — diameter-size sensitivity continuation/resume helpers.
- `run_case28_fixed_elset_wrap.sh` — case-28 recovery helper for the Abaqus material-elset line wrapping issue.
- `wait_then_resume_diameter_cases_21_40.sh` — guard script used to avoid launching a resume while an earlier case-21 run was still active.
