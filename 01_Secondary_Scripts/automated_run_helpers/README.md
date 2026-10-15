# Automated run helpers

Run these from the repository root with the configured project Python and
Abaqus environment. Scripts resolve the root from their location, not a user's
absolute machine path. Do not execute an old rerun helper merely to test imports:
some intentionally create fresh outputs or replace their own rerun folders.

- `run_uniform_size_rng.py`: 20 uniform size-RNG cases, position seed 1000;
  supports `--dry-run`, verified-completion skipping and per-case logs.
- `run_mesh_angle30_comparison.py`: controlled 30-degree mesh comparison.
- `mesh_angle30_quality.py`: mesh-quality parsing and analysis helpers.
- `verify_mesh_angle30_comparison.py`: independent saved-result verification.
- `test_mesh_angle30_study.py`: solver-free mesh helper unit tests.
- `run_midpoint_mapping_cases_70_80_150_160.py`: midpoint mapping reruns.
- `run_microstructpy_verify_existing_meshes.py`: morphology verification using
  existing MicroStructPy mesh caches, not an Abaqus rerun.
- `rerun_cases_08_16_and_overlay.py`: professor-requested fresh reruns and overlay.

Uniform batch:

```console
python 01_Secondary_Scripts/automated_run_helpers/run_uniform_size_rng.py --dry-run
python -u 01_Secondary_Scripts/automated_run_helpers/run_uniform_size_rng.py
```

Solver-free tests:

```console
python -m unittest discover -s tests -p test_uniform_size_rng_batch.py
python -m unittest discover -s 01_Secondary_Scripts/automated_run_helpers -p test_mesh_angle30_study.py
```

The moved historical helpers now point at the current `Uniform Distribution`
input/reference layout. Their existing simulation-output locations are unchanged.
Historical data availability and full FE solves are not checked by unit tests.
