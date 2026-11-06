# Uniform Mean Diameter Change

This is a NORMAL grain-diameter distribution study. "Uniform" in the folder name means applying the same prescribed mean diameter to all four phases, not using a uniform probability distribution or equally spaced sweep points.

Contains 20 original sweep cases and the 0.050 mm baseline, moved in full from simulation_outputs. The prescribed common means span 0.010 to 0.200 mm. The source completion function supplies an omitted scale as 0.2 * mean, so standard deviation changes with the mean; this is not a fixed-standard-deviation experiment. Size RNG remains 1000 and position RNG is omitted in every saved resolved input.

All case files, including ignored Abaqus databases, were retained byte-for-byte. Original resolved XML/solver files were not rewritten. Batch manifests, completion markers, runtime logs and aggregate figures remain in simulation_outputs/normal_equal_mean_batch; the runner and plotters use an archive-aware resolver, reject duplicate original/archive locations, and were verified with solver-free tests, a completed-batch dry run, and loading all 21 archived curves. Existing embedded historical source paths in logs/provenance are intentionally preserved.

Six similarly named uniform-distribution midpoint/professor-rerun cases were excluded from this normal study. They are now archived under `reference_outputs/Uniform Distribution/Sensitivity Study/lower-bound-diameter-equal-4all-phases/Simulations/`. The initial exclusion inventory in VERIFICATION.json records their locations at the time of the normal-study move. Later normal_round2 cases are not part of this original 21-case move. No simulations were launched and no plots regenerated. See CASE_INVENTORY.csv and VERIFICATION.json.
