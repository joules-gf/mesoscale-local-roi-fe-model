# Matched-normal size-RNG ensemble — position seed 1000

20 simulations that mirror the existing uniform size-RNG ensemble, with matching
theoretical diameter mean and standard deviation. This is the remote computer's
next set, not another diameter-parameter sweep.

## Fixed parameters and varied seed

- Size RNG seeds **1–20**, in that order.
- Position RNG fixed at **1000**.
- All four phases use normal mean **0.055 mm** (55 microns) and normal standard
  deviation **0.0028867513459481294 mm** (about 2.887 microns).
- Source uniform lower bound **0.050 mm**, implicit width **0.010 mm**.
- Normal `<scale>` is explicit: the generic `0.2 * loc` default would NOT match
  the uniform variance. Uniform source files remain unchanged and omit scale.
- Other source XML fields are unchanged, including `verbose=False`,
  `restart=False`, mesh settings, phase fractions, materials and loading.
- Fixed position seed does not imply identical geometries when sizes or seed
  counts change. Compare ensembles; do not assume identical-geometry pairs.

`manifest.csv` pairs every normal case with its uniform source and records the
normal parameters and RNG seeds. Inputs are self-contained: the uniform XMLs
are used by the runner only for validation, not via XML includes.

## Run on the friend's computer

After finishing the current uniform batch and pulling your Git changes, run from
the repository root with the existing configured project Python:

```console
python 01_Secondary_Scripts/automated_run_helpers/run_normal_matched_size_rng.py --dry-run
python 01_Secondary_Scripts/automated_run_helpers/run_normal_matched_size_rng.py --verify-inputs
python -u 01_Secondary_Scripts/automated_run_helpers/run_normal_matched_size_rng.py
```

For the established Windows environment, replace `python` with
`.venv\Scripts\python.exe`. Dry-run requires only Python's standard library.
`--verify-inputs` exercises the installed MicroStructPy/input-completion code but
does not generate a mesh or run Abaqus. The final command performs simulations.
A Git push by itself does not launch anything. This runner is a manual start;
it does not queue itself behind the remote uniform batch.

## Runner behavior

- Runs sequentially using the same interpreter for each child process.
- Prints each case start/finish and streams child output to console and log.
- Enables postprocessing and saved figures, suppresses popup windows.
- Forces Agg and suppresses `plt.show()` only inside each child, preserving
  legacy code that saves figures after show. No shared pipeline changes or
  modifications to the uniform runner are required for this handoff.
- Handles UTF-8 output, including legacy postprocessing messages.
- Uses an exclusive lock to prevent duplicate batch starts.
- Verifies successful Abaqus `.sta` plus at least two finite numeric curve rows.
- Skips only verified completed cases with matching input hashes.
- Stops at first failure. Partial/unrecorded case folders are refused, never
  silently deleted; inspect/recover or archive them before retrying.

Case artifacts: `simulation_outputs/normal_matched_size_rng_0001_pos1000/` etc.
Logs, timing CSV, completion records and batch lock:
`simulation_outputs/normal_matched_size_rng_position1000_batch/`.
Generated outputs remain ignored by Git.

## Files to include in your commit

- This entire input folder, including its 20 XMLs, manifest and README.
- `01_Secondary_Scripts/automated_run_helpers/run_normal_matched_size_rng.py`
- `tests/test_normal_matched_size_rng.py`

The already committed uniform inputs and existing core workflow are prerequisites.
The runner does NOT depend on the uncommitted local matched/intended sweep
runners or modifications to `run_uniform_size_rng.py`.

Solver-free tests:

```console
python -m unittest discover -s tests -p test_normal_matched_size_rng.py
```

Tests use explicitly mocked solver execution and fixture artifacts, not real FE
results. Full input completion separately checks actual runtime distributions.
