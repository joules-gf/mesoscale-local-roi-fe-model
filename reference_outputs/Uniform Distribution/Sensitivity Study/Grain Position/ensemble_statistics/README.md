# Position ensembles: stress and morphology comparison

## Scope and execution

36 existing solved cases: 18 placements with size seed 1000 and 18 with size seed 0 (default). No FE solve or mesh generation was performed. All source XML, CSV, seeds, polygon mesh, triangular export, and solver-input bytes were hash checked. Nodes/connectivity in saved MicroStructPy triangular exports match the corresponding Abaqus inputs exactly.

The native `trimesh.txt` cache is absent. Calling CLI restart+verify would trigger new triangulation. Instead the helper reconstructed TriMesh from original Abaqus export nodes, CPS3 elements, seed element sets and parent-facet surfaces; geometrically checked surface-parent associations; and called the installed MicroStructPy verification routines directly. It generated phase fractions, fitted seeds, maximum-likelihood estimates and error statistics for every case, under `verification/`.

## Stress at nominal 1% strain

The saved unit-square/unit-thickness convention matches the existing ROM-vs-folder plotter. Stress is total top reaction / unit reference section; strain is top displacement / unit side length. Nominal 0.01 endpoints saved with float32 roundoff <1e-9 were accepted and labeled; other bracketing data use interpolation, never extrapolation.

- Cyclic Ramberg–Osgood reference: **542.600896 MPa**.
- Size seed 1000: **544.177913 MPa mean**, **4.798040 MPa sample standard deviation**, median 544.934939; 12/18 above the reference.
- Size seed 0: **537.540177 MPa mean**, **8.534978 MPa sample standard deviation**, median 539.640026; 4/18 above the reference.
- Difference of ensemble means (1000 minus 0): **6.637736 MPa**.

The seed-0 ensemble has a pronounced low-response tail. Cases `bp_rng_size231`, `bp_rng_size327`, and `bp_rng_size568` remain included; none was discarded as an outlier.

## Morphology interpretation

Mean realized tessellated phase fractions (phase 0 / 1 / 2 / 3):

- Size seed 1000: 9.6164% / 9.4001% / 39.5598% / 41.4237%.
- Size seed 0: 9.8049% / 9.6251% / 39.4819% / 41.0880%.
- Nominal input: 10% / 10% / 40% / 40%.

Phase yield strengths are 410 / 470 / 680 / 710 MPa. The saved phase material law is elastic–perfectly plastic, not grain-size-dependent. More strong-phase area in seed 1000 is directionally consistent with its higher mean stress. However, the area-weighted yield-strength diagnostic differs by only 1.082137 MPa and has modest within-group correlations with stress (r=0.2585 and 0.3619). This diagnostic is not a predicted stress at 1% and does not establish a fraction-only explanation of the 6.637736 MPa mean gap.

The ROM abbreviation in this project is **Ramberg–Osgood**, not rule of mixtures. Its reference curve is independent of the realized phase fractions. The final-region diameter violin uses per-case mean equivalent-circle diameter from tessellated area, not original seed diameter or the fitted-circle diameter; all three are separately tabulated in case statistics.

Basic triangular shape screens found no elements with r/R <0.1 in these saved meshes. That limited screen is not a mesh-convergence test and does not rule out other numerical effects.

## Limits and next investigation

These are two fixed phase/size inventories with repeated position realizations, NOT 36 independent size realizations. Only position seeds 1, 2, 10 and 20 overlap between ensembles. Equal numerical position seeds do not produce identical geometry for different inventories. No general conclusion that seed 1000 is stronger than seed 0 is justified.

The data support a group shift and a plausible small composition contribution; topology/load paths, boundary arrangement and plastic redistribution remain candidate explanations. Next inspect the three low-response seed-0 cases against nearby typical cases using local plasticity and phase connectivity before spending time on new simulations.

## Files

- `stress_at_1pct_violin.png`: 18 observations per group; cyclic reference; means and medians.
- `phase_area_fraction_violins.png`: four phase-fraction distributions, one point per case.
- `final_region_diameter_violins.png`: per-case mean final-region diameter distributions by phase.
- `phase_composition_vs_stress.png`: descriptive within-group trends versus area-weighted phase yield-strength proxy.
- `case_statistics.csv`: 36 rows for reproducible comparison.
- `analysis_summary.json`: numerical summary and limitations.
- `verification/Size RNG <seed>/<case>/`: source hashes and official verification-stage text artifacts.
- `previews/`: resized copies for visual inspection; full-resolution PNGs remain in this folder.

One-off helper: `archive/run_helpers/analyze_position_rng_ensembles.py`.
Reproduce from repository root with `.venv/Scripts/python.exe archive/run_helpers/analyze_position_rng_ensembles.py`. Source-hash-matching per-case verification results are reused; figures are regenerated. Nothing here was committed or pushed as part of this analysis.
