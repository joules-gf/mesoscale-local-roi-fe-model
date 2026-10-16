# Normal equal-mean diameter sweep — original intended parameters

Prepared inputs only: 20 sweep cases plus the separate 0.050 mm mean baseline.
This study restores the intended normal interpretation of the original numerical
diameter settings. It is separate from the moment-matched normal batch.

## Parameters

- Each original uniform `loc` value becomes the intended normal mean.
- Distribution family: `norm` (SciPy/MicroStructPy normal distribution).
- No `<scale>` tags: the existing `complete_input_data` calculation supplies
  standard deviation `scale = 0.2 * loc`, without changes to that code.
- Baseline: mean 0.050 mm, standard deviation 0.010 mm (50 and 10 microns).
- Sweep means span 0.010–0.200 mm; the exact 20-point sequence is preserved from
  the original sweep, not replaced by evenly spaced new values.
- All four phases have the same normal mean and standard deviation in a case.
- Domain, fractions, loading, materials, plastic stresses and mesh controls
  are unchanged from the corresponding original XML.
- Size RNG remains 1000; position RNG remains omitted as in the original
  diameter sweep. It is not changed to the separate size-RNG study's seed 1000.
- `verbose=True`; `restart=False`; unique case stems prevent output collisions.

`manifest.csv` maps every new input to its original uniform case and records
expected runtime distribution parameters. `parameters_microns.csv` is a readable
table of mean and standard deviation for every case, including the baseline.
The input-completion step, rather than raw XML parsing, must be used to verify
the injected standard deviation.

## Interpretation

Compared with the original uniform study, this changes distribution family,
mean, and spread together: an implementation-correction comparison, not an
isolated distribution-shape experiment. Standard deviation varies with mean,
so this is not a fixed-absolute-standard-deviation mean sweep either.

These are ordinary normal inputs, not explicitly truncated normal inputs.
Any rejection/size filtering in generation and the realized seed statistics
must be checked after generation; nominal input moments do not establish final
microstructure statistics or final tessellated-cell sizes.

## Execution and conditional handoff

```console
python -u 01_Secondary_Scripts/automated_run_helpers/run_normal_intended.py --after-matched
```

`--dry-run` validates/lists all 21 cases without waiting or running any solver.
`--after-matched` waits for the matched batch's completion marker AND released
lock, then verifies all 21 success rows, per-case completion records, input hashes,
Abaqus success statuses, and curve CSVs before running. A failed/stopped predecessor
blocks the handoff. Intended XML hashes are checked again after waiting.

Cases run largest-to-smallest with verbose=True and postprocessing enabled;
figure windows are suppressed, while plots continue to save. Existing verified
completed cases are skipped; unrecorded partial case folders are never overwritten.

Queue/status, per-case logs, console log and runtime summary:
`simulation_outputs/normal_intended_batch/`. The current handoff state is recorded
in `handoff_status.json` (`waiting`, `running`, `completed`, or `blocked`).

For the configured local queue, attach from WSL with:

```console
tmux attach -t normal-intended-queued
```

Preparing/verifying inputs does not launch simulations. Starting this runner
without `--after-matched` launches immediately only when the matched batch lock
is absent; conditional handoff is the preferred route for sequential studies.
The matched batch's inputs, runner, and outputs are not modified by this runner.
