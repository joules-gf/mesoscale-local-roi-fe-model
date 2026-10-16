# Uniform diameter size-RNG study — position seed 1000

## Experiment

20 sequential fresh simulations, size seeds **1 through 20**, position seed
**1000**. All other XML controls are identical. Fixing a position seed does NOT
fix identical spatial geometry when the sampled sizes/seed counts change.

Baseline provenance: saved `bp_position1000_resolved_input.xml` in
`reference_outputs/Uniform Distribution/Sensitivity Study/Grain Position/Size RNG 1000/bp_position1000/`.
The new files are self-contained; that reference folder is not required to run.
The baseline's machine-specific `reference_curve_csv` was removed so the normal
reference-material resolver uses this checkout's curve file. The XML files omit
`scale`, preserving the established generator calculation `scale = 0.2 * loc`.

- Domain: square, side 1 (existing model units).
- Four phases: fractions 0.1, 0.1, 0.4, 0.4.
- Each diameter XML specifies `uniform` and `loc=0.05`, with no `scale` tag.
  The existing pipeline computes scale as 0.01; this is NOT mean 0.05/std 0.01.
- Material: AA7075-T651, E=70000, nu=0.33.
- Plastic stresses: 410, 470, 680, 710; displacement_yy=0.01.
- Mesh minimum angle 25; maximum edge length 0.0026.
- `restart=False`; no original mesh cache reused.
- `manifest.csv` specifies the execution order.

## Run on the friend's computer

From the repository root, using the project's configured Python environment
with MicroStructPy and its other dependencies, and working Abaqus access:

```console
python 01_Secondary_Scripts/automated_run_helpers/run_uniform_size_rng.py --dry-run
python -u 01_Secondary_Scripts/automated_run_helpers/run_uniform_size_rng.py
```

For the established Windows virtual environment, replace `python` with
`.venv\Scripts\python.exe`. The runner uses that same interpreter for each child
process. No local absolute input path is embedded. A Git push only transfers
these files; it does not automatically execute the runner remotely.

## Outputs and operational safety

- Case artifacts: `simulation_outputs/uniform_size_rng_0001_pos1000/` etc.
- Logs, completion records and runtime CSV:
  `simulation_outputs/uniform_size_rng_position1000_batch/`.
- All generated outputs remain ignored by Git.
- Cases run one at a time; the batch stops on the first failure.
- Success requires zero subprocess exit, a successful Abaqus `.sta`, and a
  nonempty curve CSV with at least two data rows. This is an operational check,
  not scientific validation of the response.
- Re-running skips only cases with matching input hash and verified artifacts,
  including results moved to the canonical reference archive.
- Archive finished cases with `archive_completed_rng_results.py`; see
  `docs/RNG_RESULT_ARCHIVING.md`. The canonical archive is
  `reference_outputs/Uniform Distribution/Sensitivity Study/Size RNG/Position RNG 1000/`.
  Keep `rng_result_locations.py` alongside the runner for archive-aware resume.
- Existing partial/unrecorded case folders are refused, never deleted. Inspect
  and recover or manually archive such a folder before retrying. The runner
  does not automatically recover postprocessing from an existing ODB.
- An exclusive `RUNNING.lock` guards against concurrent batch launches. After
  a forced shutdown, confirm no batch is active before removing a stale lock.
- Noninteractive plotting and UTF-8 output are enabled for child processes.

## Validation (no Abaqus job)

```console
python -m unittest discover -s tests -p test_uniform_size_rng_batch.py
```

Tests mock solver execution in temporary directories. They test order, resume,
failure stopping, control validation, and overwrite protection; they do not
claim that any FE simulation was solved.
