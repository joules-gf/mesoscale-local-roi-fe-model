# Mesoscale Local ROI FE Model

## Essential-workflow candidate

This release is the repository reference version of the research workflow, approved by Julio for publication to `main`. The full research checkpoint is preserved on `integration/normal-sensitivity-consolidation` at `4cc9de1`. Publication does not establish independent scientific validation or completion of the target-machine checks below.

The workflow uses MicroStructPy to generate computational mesostructures and meshes, Abaqus to solve the model, and Python to extract macroscopic and local region responses. It does not explicitly model crystallographic slip or predict fatigue life.

## Included

- `00_Main_Scripts/`: the selected generation, execution, extraction, reference, platform and ROI scripts, including `peak_detection.py`.
- `00_Main_Scripts/material_reference_curves/`: the complete selected reference folder.
- `simulation_inputs/Uniform Distribution/examples/`: one monotonic example, one cyclic example, and their shared mesh definition. These are demonstration inputs, **not** the normal sensitivity-study input collection.
- `reference_outputs/Normal Distribution/Sensitivity Study/`: the five selected study folders, initially retained in full pending individual CSV/figure selection.
- `simulation_inputs/AA2024-T351/` and `simulation_inputs/AA7075-T651/`: normal-distribution material baselines, each with local include files and distinct monotonic/cyclic case stems.
- `tests/`: solver-free tests for the retained workflow.
- `docs/`: workflow, exact scope and release-review records.

Study runners, secondary analysis tools, historical code, uniform reference-output collections and matched-uniform results are excluded from this branch's tracked tree. In the original working checkout they remain on disk, ignored, and are preserved by the research checkpoint. A fresh clone of this candidate will not include them. This is tree cleanup, not history removal or a privacy guarantee.

## Setup

Use a regular Python environment compatible with the project's dependencies:

```text
python -m venv .venv
```

Activate it using `.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` in a POSIX shell, then:

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

A full solve additionally requires a working, licensed Abaqus installation. Abaqus supplies `abaqus`, `abaqusConstants` and `odbAccess`; do not install replacements from pip. The regular environment is not a complete Abaqus or native-meshing environment lock.

## Run a demonstration

From the repository root, on a machine configured for Abaqus:

```text
python 00_Main_Scripts/full_simulation_runner.py --input-file "simulation_inputs/Uniform Distribution/examples/aa7075-T6-base-parameters.xml"
```

For the cyclic example, use `strainRratio-1.xml` in the same folder. These commands launch real computation and may take substantial time. They were **not** run as part of release preparation. Use a unique input filename stem for a new case; output names are based on that stem and can collide across input folders.

`--generate-only` skips Abaqus and postprocessing, but still runs MicroStructPy; it is not a cheap validation command. The legacy direct-script demonstration blocks are not supported entry points. Prefer the runner's explicit `--input-file` interface. Windows Abaqus may be reached from WSL through `wsl_windows_compat.py` and the `MICROSTRUCTURE_ABAQUS_CMD` override; verify the installed command and licensing locally.

## ROI analysis

ROI processing is a **separate sequence**, not an automatic stage of the full runner. See `docs/WORKFLOW.md` for frame selection, a configuration template, safe ODB handling and commands.

ROI plots keep every phase separate by default. To deliberately combine phases 2 and 3, add `--combine-equal-yield-phases`; this option does not verify their constitutive equality. Historical grouped figures remain unchanged.

## Saved results and provenance

The retained normal-study folders are `Area Fraction`, `Grain Position`, `Plastic Stress`, `Size RNG`, and `Uniform Mean Diameter Change`. In the last name, "Uniform" means applying the same mean to all four phases, not a uniform probability distribution. The normal mean sweep also changes the absolute spread through the historical `0.2 * mean` default.

Resolved XML and solver input decks retained beside saved outputs are provenance records, not the excluded input campaigns or promises that every old path works in a fresh clone. Existing metadata can name batch folders, ignored ODBs or historical scripts not supplied here. In particular, `normal_study_plot_manifest.json` records a historical secondary plotter that is intentionally excluded; its name/hash are not a runnable command in this release. Reference curves and saved plots do not independently validate physical assumptions.

## Contributions and validation boundary

Detailed function-level attribution is retained separately and is not distributed in this repository. Git commit identity is not evidence of human-versus-AI implementation authorship. Release-preparation implementation included AI assistance; code review, historical authorship and independent scientific validation are distinct claims.

Read `docs/RELEASE_REVIEW.md` before treating this as a general-purpose package. Remaining assumptions include unit-domain stress/strain conversion, four phase labels, material/modulus choices, single-step frame selection and case-specific comparison data. Publication was authorized; thesis integration and licensed target-machine validation remain separate tasks. No new license grant or permission to redistribute third-party data is implied.
