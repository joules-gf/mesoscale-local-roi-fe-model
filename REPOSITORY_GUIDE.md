# Repository guide

This repository contains a research-oriented mesoscale finite-element workflow for microstructure generation, Abaqus simulation, global stress-strain postprocessing, and local ROI analysis.

The code intentionally remains close to its original research-script style while the repository is being cleaned for easier use across Windows, WSL, and GitHub.

## Main folders

| Path | Purpose |
|---|---|
| `00_Main_Scripts/` | Core workflow scripts: XML parsing, MicroStructPy/Abaqus input generation, Abaqus execution helpers, ODB extraction, material-reference selection, ROI extraction, ROI postprocessing, and plotting support. |
| `01_Secondary_Scripts/` | Secondary analysis and plotting helpers. These are more script-like than package-like, but should generally be reusable or at least directly relevant to analysis. |
| `simulation_inputs/` | Tracked XML/CSV inputs used to reproduce baseline cases and sensitivity studies. Generated simulation outputs are not tracked. |
| `00_Main_Scripts/material_reference_curves/` | Small reference CSVs used for ROM/experimental comparisons. These are tracked because they are inputs to reproducible plots/comparisons. |
| `tests/` | Regression tests for key workflow behavior, especially path handling, material references, ROI logic, and Abaqus input/postprocessing helpers. |
| `archive/old_script_versions/` | Older versions of core scripts kept only for historical reference. |
| `archive/fatigue_reference_zhao_2007/` | Curated fatigue-reference provenance package: source CSV, generated figures, and companion plotting script. |
| `archive/run_helpers/` | One-off batch/resume/monitor scripts moved out of the repo root. Preserve as provenance; verify carefully before reusing. |
| `reference_outputs/` | Placeholder for small curated example outputs. Routine generated simulation results should remain ignored. |
| `notes/` | Repo-adjacent notes. Broader thesis/literature notes may eventually move to a separate thesis notes system. |

## Normal entry points

For normal pipeline work, start with:

```bash
python 00_Main_Scripts/full_simulation_runner.py --input-file <path-to-input.xml>
```

For a safe Python/MicroStructPy-only check without launching a full Abaqus solve:

```bash
MPLBACKEND=Agg MICROSTRUCTURE_NONINTERACTIVE=1 \
python 00_Main_Scripts/full_simulation_runner.py \
  --input-file simulation_inputs/AL7075-T6/baseline_parameters.xml \
  --generate-only
```

For ROM/reference curve generation:

```bash
python 01_Secondary_Scripts/generate_ROM_stress-strain_curve.py --help
```

## What should usually be tracked

Track:

- source code;
- tests;
- setup/documentation files;
- baseline and study XML inputs;
- small reference CSVs needed for comparisons;
- curated provenance packages under `archive/`.

Do not normally track:

- virtual environments;
- Python caches;
- routine generated plots;
- Abaqus `.odb`, `.dat`, `.msg`, `.sta`, `.lck`, and related solver files;
- full `simulation_outputs/` folders.

## Cleanup status notes

The repository root should stay clean. Historical run-specific scripts belong in `archive/run_helpers/` unless they are promoted into reusable workflow tools.

The main open cleanup decisions are:

1. whether tracked `*_mesh.xml` files are reproducibility inputs or generated intermediates;
2. which secondary scripts are still active analysis tools versus archive provenance;
3. whether broader research notes should remain in the code repo;
4. whether currently tracked generated PNGs under `01_Secondary_Scripts/rom_outputs/` should stay there, move to `reference_outputs/`, or be regenerated locally only.
