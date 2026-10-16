# Normal equal-mean diameter sweep — moment-matched to prior uniform study

21 fresh inputs: the original 20 sweep points plus the separate baseline.
Theoretical diameter mean and standard deviation are matched to each corresponding
uniform case. All four phases share the same diameter distribution within a case.

For original uniform lower bound `a` and interval width `w = 0.2 * a`:

- New normal `loc` (mean): `a + w / 2`.
- New normal `scale` (standard deviation): `w / sqrt(12)`.
- Example original lower bound 0.050 mm: normal mean 0.055 mm,
  normal standard deviation approximately 0.002886751345948129 mm.

The normal `<scale>` is explicit: omitting it would trigger the generic
20%-of-loc default and would NOT match the uniform variance. The existing
input-completion calculation is unmodified. The uniform XMLs still omit scale.

`manifest.csv` maps every new case to the original case and lists both sets of
parameters. Baseline suffix `0p050` identifies the source uniform lower bound,
not the new normal mean. Normal family is encoded as `norm` for SciPy/MicroStructPy.

## Controls

Domain, phase fractions, material, loading, plastic stresses and mesh criteria
are copied from each source XML. Only distribution family/parameters and
`restart=False` differ. Size RNG remains 1000. Position RNG remains OMITTED,
exactly as in the prior diameter sweep; it is not changed to the size-RNG study's
position seed 1000. Same RNG settings do not ensure identical realized geometry.
All new case names are distinct from original outputs.

The original source directory is now:
`simulation_inputs/Uniform Distribution/sensitivity-study-AA7075-T651/bp_same_lower_bound_diameter/`.

This is a matched-family comparison, NOT the separate intended normal study
with mean 0.05 mm and standard deviation 0.01 mm. Standard deviation increases
proportionally across this sweep; it is not an independent mean-only sweep
at fixed absolute standard deviation. Matching moments does not match tails or
bounds. Inputs use an ordinary normal distribution, not explicit truncation;
any size rejection by the generator must be checked in the realized seeds.

Preparation does not start any simulations. Verify all inputs without meshing or solving:

```console
python 01_Secondary_Scripts/automated_run_helpers/verify_normal_matched_uniform_inputs.py
```

Run the sequential batch (largest normal mean first, baseline inserted by mean):

```console
python -u 01_Secondary_Scripts/automated_run_helpers/run_normal_matched_uniform.py
```

Use `--dry-run` to validate/list the plan without solving. The wrapper requires
verbose=True, preserves postprocessing, and sets noninteractive plotting in child
processes. It tees live output to the console and each case log. Batch logs,
completion records and `runtime_summary.csv` live in
`simulation_outputs/normal_matched_uniform_batch/`. Completed cases are skipped
only with matching input hashes and verified result artifacts; partial outputs
are refused rather than overwritten.

`uniform_vs_normal_parameters_microns.csv` provides a presentation-friendly
21-row comparison table: uniform bounds/width/mean/std and matched normal
mean/std, all in microns. These are theoretical input statistics, not measured
statistics of generated or tessellated microstructures.
