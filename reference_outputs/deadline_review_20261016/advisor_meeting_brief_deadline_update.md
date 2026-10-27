# Advisor meeting brief — deadline update, 16 October 2026

## Decision

**Use completed set 3 to replace Figure 9(b). Keep the current uniform-distribution paper and its structure. Present the normal comparisons as advisor-discussion slides, not a rushed replacement sensitivity section.**

This narrows the earlier broad review to the highest-value corrections under a two-hour limit. The new size-RNG data resolve the missing diameter-realization experiment; they do not resolve every indentation/morphology inference limitation. No new simulations were launched and the manuscript itself was not edited.

## What was plotted and verified

A frozen snapshot was used:

- Set 1: 19 matched-normal diameter cases, including the baseline; two finest cases have no completed curve in this snapshot.
- Set 2: no result presented; user reports not started.
- Set 3: 20/20 uniform size-RNG cases, size seeds 1–20 and position seed 1000.
- Set 4: the user-confirmed first 13/20 matched-normal size-RNG cases. A case-14 CSV appeared during review, but was deliberately excluded from the frozen comparison rather than silently changing the sample.

For sets 3/4, inputs, controls, phase fractions and saved seed files were checked. All 20 set-3 inventories and all 13 set-4 inventories are distinct. Set 3 uses uniform diameter bounds 0.050–0.060 mm. Set 4 uses normal mean 0.055 mm and standard deviation 0.002886751 mm. Material properties, prescribed fractions, domain, loading and mesh policy match across the two ensembles.

The source loader was reused, but only named case CSVs were selected. Summary/statistics CSVs were not treated as simulation curves. Reference data are the actual AA7075-T651 cyclic-ROM file; a stale T6 label in the generic plotter was not carried into these figures. The original plotter was not edited.

Set 1's completed CSVs and resolved inputs were found under `simulation_outputs`, not an archived reference case tree in the snapshot. Its input moments and controls match the corresponding original uniform cases. Those 19 normal cases do not contain saved `seeds.txt`, so empirical seed moments were not claimed or fabricated. The new plots and source manifest are saved under `reference_outputs/deadline_review_20261016`.

## Results that affect the paper

### Set 3: a valid replacement Figure 9(b)

At prescribed 1% tensile strain, MPa:

- n = 20
- Mean = 539.13
- Sample standard deviation = 7.46
- Minimum–maximum = 522.22–549.56
- CV = 1.38%
- Full range / mean = 5.07%

Recommended interpretation: **modest but nonzero scatter in global response under the fixed uniform baseline**. It is not proof that size variability has no effect, that all distribution widths/families are equivalent, or that local stresses are insensitive.

Replace the embedded Figure 9(b) plot, caption, Methods RNG description, Table 3 size-RNG range, and corresponding Results/conclusion statements together. The new experiment varies size RNG 1–20; position RNG 1000 is fixed. This does not hold physical grain positions identical, because a changed seed inventory affects placement/packing.

### Grain position: retain or show the two inventories separately

The accessible Windows tree still contains two placement ensembles:

- Fixed size RNG 1000: n = 18; 544.18 ± 4.80 MPa; range 535.30–553.04 MPa; endpoint span 3.26% of mean.
- Fixed size RNG 0/default: n = 18; 537.54 ± 8.53 MPa; range 513.93–545.61 MPa; endpoint span 5.89% of mean.

Every group has one fixed phase/diameter inventory and 18 distinct placements. Inventories differ across groups: 422 versus 418 seeds. Do not pool all 36 as one placement-only variance estimate or describe them as 36 independent size samples.

**For the two-hour paper edit, retaining the original Figure 9(a) is acceptable if it is the size-RNG-1000 group already mapped to the paper.** Quote its 3.26% endpoint span if adding a number. If using the new combined plot, describe two fixed size inventories explicitly and retain separate group labels/statistics.

The user-mentioned newly organized aggregate files were not visible in repeated bounded scans of the supplied Desktop path at review time; case data were present. Rather than pretend those exact plots were reviewed, the 36 cases were re-audited, all 108 source hashes rechecked, and new separate/combined plots generated in this review folder. If another session has newer plots elsewhere, compare their case manifest before substituting them.

## Normal comparisons: best used in the meeting

### Set 4 versus set 3 at matched theoretical moments

Use a common first-13 seed-ID subset for a balanced descriptive comparison:

- Uniform first 13: mean 538.66 MPa, sample SD 8.27 MPa.
- Matched normal first 13: mean 542.36 MPa, sample SD 5.00 MPa.
- Difference in means (normal minus uniform): +3.69 MPa, +0.69% relative to the uniform subset mean.

Meeting statement: **"At the baseline size moments, the available matched-normal ensemble has a close mean response to uniform; the normal subset is preliminary and the groups overlap."**

Do not claim statistical equivalence, significance, converged variance, or identical geometries. Equal numeric seed IDs preserve traceability but do not create identical microstructures across different distribution families. The lower observed normal SD in 13 cases is descriptive, not a proven general reduction in variability.

### Set 1 versus original uniform diameter sweep

Nineteen common sizes were compared at 1% strain. Normal-minus-uniform differences range from −17.78 to +40.81 MPa; mean signed difference is +2.51 MPa. Largest absolute difference is nominal d=0.075 mm (theoretical mean 0.0825 mm): uniform 509.15 MPa versus matched normal 549.96 MPa.

Meeting statement: **"The small baseline ensemble mean difference does not establish negligible differences across the entire size sweep."** Individual size cases can separate noticeably. With one realization per size, differences mix distribution family with realized grain inventories and packing; do not attribute each difference uniquely to the family. Two finest normal points remain unavailable. No intended-normal result exists in this package.

Keep Figure 10's existing uniform sweep in the paper for the immediate deadline; correct its nominal-parameter versus theoretical-mean labeling and avoid unsupported universal mechanism claims.

## How the previous recommendations change

### Resolved or reduced

- Figure 9(b) no longer needs deletion for lack of a valid experiment: set 3 supplies a verified replacement.
- Diameter-resampling scatter is now measured at the tested uniform baseline; replace the earlier statement that it was untested.
- A full conversion of the paper to normal sampling is unnecessary. The paper can honestly report uniform sampling while the new normal checks remain separate.
- New microscopy and equipment investigations should not become submission prerequisites for the narrower model claims.

### Still worth short corrections

- Correct the uniform parameter rule everywhere relevant: nominal d, support [d,1.2d], theoretical mean 1.1d, SD 0.2d/√12.
- Define computational phases as effective strength classes, without renaming every figure or rebuilding the paper.
- Preserve the disclosed indentation-to-global adjustment; explicitly label final FE parameters calibrated effective inputs.
- Change the strongest same-data forward-reconstruction accuracy claim to a consistency check.
- Avoid claims that more indents automatically recover the true local spatial property distribution, or that targeted indentation-bin frequencies are independently measured phase area fractions.
- Keep Vickers-versus-Berkovich wording accurate; do not diagnose instrument failure without records.

The companion `submission_critical_wording_repairs_deadline_update.md` supplies short replacements. Use it as the action list; retain the longer original review as background, not a task queue to finish today.

## Recommended presentation

A four-slide, image-backed PowerPoint is supplied with speaker notes and exact PNG previews:

1. **Main slide: correction and replacement.** Set-3 overlay plus n20, mean±sample SD, range and bounded interpretation. This is the single slide to use if discussion time is short.
2. **Baseline robustness check.** Common-13 endpoint scatter; +3.69 MPa / +0.69% mean difference, preliminary normal status, and no equivalence claim.
3. **Size-sweep comparison.** Nineteen paired nominal cases on the theoretical-mean axis, with signed difference panel; highlight 40.81 MPa maximum and pending finest cases.
4. **Minimal paper edits.** Measured → inferred → calibrated diagram and the short corrective action list.

Optional backup: `grain_position_two_inventories_combined.png`, with separate 18-case statistics. It explains why the old mislabeled RNG set is not wasted; it is a second placement ensemble, not the replacement diameter-resampling experiment.

The slide previews are the exact full-slide PNGs embedded in the PPTX; a PowerPoint-application layout render is not being claimed. The plot layouts were visually checked and a clipped diagnostic axis label/legend was repaired before delivery.

## Two-hour paper plan

1. 25 minutes — replace Figure 9(b) and caption.
2. 25 minutes — correct Methods/Table 3 and diameter definitions.
3. 15 minutes — add bounded numerical Results/conclusion wording.
4. 25 minutes — short calibrated/inferred/numerical-class clarifications.
5. 20 minutes — verify active figures and cross-references; export a clean PDF.
6. 10 minutes — buffer.

Do not spend the edit window waiting for the unfinished normal cases. No manuscript edits, solver runs, or case moves were performed in this review.

## Key files

- Requested overlays: `set1_matched_normal_19cases.png`, `set3_uniform_size_rng_20cases.png`, `set4_matched_normal_rng_13cases.png`.
- Comparative slides/figures: `ensemble_uniform_vs_normal.png`, `ensemble_endpoint_scatter.png`, `diameter_sweep_uniform_vs_matched_normal.png`.
- Placement figures: `grain_position_size_rng_1000.png`, `grain_position_size_rng_0.png`, `grain_position_two_inventories_combined.png`.
- Statistics/provenance: `summary.json`, `case_statistics.csv`, `source_manifest.json`, `grain_position_endpoint_statistics.csv`, `grain_position_parent_verified.json`.
- Manuscript action list: `submission_critical_wording_repairs_deadline_update.md`.
