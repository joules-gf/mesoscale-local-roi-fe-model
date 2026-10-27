# Grain-position audit / Figure 9a

Source: `/mnt/c/Users/MAEadmin/Desktop/Github Repos/mesoscale-local-roi-fe-model`.

## Verified endpoint statistics
At nominal 1% tensile strain, MPa. Sample SD uses ddof=1. Span is range/mean, not a confidence interval.

| Fixed size RNG | n | Mean | Sample SD | Min | Max | Range | Span (%) | Sample CV (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1000 | 18 | 544.177913 | 4.798040 | 535.299206 | 553.041126 | 17.741920 | 3.260316 | 0.881704 |
| 0 | 18 | 537.540177 | 8.534978 | 513.934716 | 545.607809 | 31.673094 | 5.892228 | 1.587784 |

## Deadline-focused Figure 9a interpretation
- Both existing ensembles vary placement, not sampled size: each has exactly one ordered phase/diameter fingerprint and 18 distinct position fingerprints. `bp_position*` fixes size RNG 1000; misleadingly named `bp_rng_size*` omits size RNG (effective default 0) and varies position RNG. Treat them as two fixed-size placement ensembles, not 36 draws of grain size.
- Minimal suggested wording: “Changing the grain-position realization produced a small but nonzero variation in the macroscopic tensile response for each of the two fixed grain-size realizations examined.” Add the endpoint range percentages from the table if useful.
- If Figure 9a contains only the original `bp_position*` ensemble, quote its statistics only. A combined figure may show both ensembles with separate labels; do not pool them into a single position-only variance estimate or claim distribution-family robustness, local-field insensitivity, statistical convergence, or universal placement independence.
- A second fixed-size realization supports repeating the placement comparison, not broad inference over all size realizations. No new simulations are required to support this bounded wording.

## Provenance and endpoint handling
- Saved CSV columns are read by numeric index 1 (strain/U_Y) and 2 (stress/Total RF Y); each source XML has unit domain side. All selected curves are monotonic.
- Completed step-time 1 endpoints are stored at 0.009999999776482582 strain (single-precision displacement); accepted as nominal prescribed 1% within 5e-10 absolute tolerance. No out-of-range extrapolation or arbitrary final-row selection.
- Material XML specifies uniform loc=0.05 mm, phase fractions 0.1/0.1/0.4/0.4, and no explicit scale. Generator fills missing scale with 20% of loc; saved inventories are the direct fixed-size evidence. These are seed sizes, not measured final tessellated-grain sizes.

## New separate/combined plots and statistics
- Repeated bounded scans of the current Desktop `Grain Position` and `RNG` trees found case-level figures but no separate/combined aggregate plots or summary/statistics files at audit time. The equivalent Documents paths do not exist. This is a current snapshot, not a claim that another session cannot create them later.
- No original plot or case file was changed. Source paths and SHA-256 values are retained in JSON/CSV; final verification re-discovers moved cases by filename.
