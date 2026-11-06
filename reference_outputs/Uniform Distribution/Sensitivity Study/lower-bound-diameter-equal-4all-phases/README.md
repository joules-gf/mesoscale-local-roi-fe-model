# Uniform lower-bound-diameter sensitivity study

This folder was previously named `mean-diameter-equal-4all-phases`.
The varied XML parameter was the uniform diameter **lower bound** (`loc`),
shared across all four phases, not the mean.

The existing generator supplies interval width `scale = 0.2 * loc`.
Consequently, mean is `1.1 * loc`, and standard deviation is
`0.2 * loc / sqrt(12)`. Both mean and absolute spread change along the sweep.
The actual responses are unchanged by this labeling correction.

Input folder: `simulation_inputs/Uniform Distribution/sensitivity-study-AA7075-T651/bp_same_lower_bound_diameter/`.

Existing case IDs, solved files, filenames and images are preserved for provenance.
Legacy plot titles/axes and historical resolved-input names have NOT been
regenerated or rewritten; figures calling these lower-bound values "mean"
need a separate labeling correction before presentation. Do not interpret
seed input diameter statistics as final tessellated-region measurements.

## Additional archived uniform cases

`Simulations/` contains the 20 original cases plus four midpoint cases and two professor-check reruns:

- `bp_same_size_case_07_08_mid_070um`
- `bp_same_size_case_08_09_mid_080um`
- `bp_same_size_case_15_16_mid_150um`
- `bp_same_size_case_16_17_mid_160um`
- `bp_same_size_case_08_rerun_prof_check`
- `bp_same_size_case_16_rerun_prof_check`

The six additional folders were moved in full from `simulation_outputs/`, including ignored solver databases. All 99 files were SHA-256 verified before and after moving; scientific file bytes and historical provenance paths were unchanged. Existing aggregate figures were not regenerated. The all-cases plotter still selects 20 originals plus four midpoint cases, not the two reruns.
