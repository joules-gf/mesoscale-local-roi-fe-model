# Submission-critical wording repairs — two-hour update

**This supersedes the priority order, not the evidence, in the longer October 15 review.** Keep the paper's structure/title and the existing uniform study. No new microscopy, hardware investigation, or complete normal sweep is required before making the current claims accurate. Source locators refer to unchanged `summer2_paper_v08.docx`, SHA-256 a055d591e70a6cbbaef5ed9188e131b0d008f66f50a3e04c8714b3929de638d2. The manuscript itself has not been edited.

## A. The Figure 9(b) problem now has a verified replacement

Use `set3_uniform_size_rng_20cases.png` from this folder. It contains all 20 completed set-3 curves and the correct AA7075-T651 cyclic ROM reference. All 20 saved phase/diameter inventories differ; the size RNG runs from 1 through 20; the position RNG is fixed at 1000. Every material uses uniform loc=0.050 mm with runtime width=0.010 mm.

**Suggested full Figure 9 caption, pending final selection of panel (a):**

> Figure 9. Effect of random realizations on the global stress–strain response: (a) seed-position realizations at a fixed sampled seed-size inventory; (b) 20 uniform seed-diameter realizations generated using size RNG seeds 1–20 and position RNG seed 1000. For panel (b), seed diameters were sampled uniformly over 0.050–0.060 mm. A fixed position RNG controls the random stream but does not guarantee identical spatial geometries when the sampled seed inventory changes.

If panel (a) is the new combined two-size-realization plot, replace its clause with "seed-position realizations for two fixed seed-size inventories" and name both size RNG values in the caption. Do not imply there is only one fixed inventory across the combined groups. Read the final grain-position audit before choosing the combined panel.

**Add to sensitivity Methods P86 and update Table 3 P128–130:**

> For diameter-resampling sensitivity, the uniform distribution parameters were held fixed while the size RNG seed was varied from 1 to 20; the position RNG seed was held at 1000.

Table row: parameter = "Seed-diameter realization (size RNG)"; fixed distribution = "Uniform, 0.050–0.060 mm"; tested seeds = "1–20"; position RNG = "1000". Remove the previous 0–964 diameter-sampling range for this replacement. Preserve the position-study row, updating its fixed-size groups if using the combined panel.

## B. Correct the uniform parameter definition, not the entire study

**Replace P120's final phrase** (20% of mean as standard deviation) with:

> Seed diameters followed a uniform distribution over [d, 1.2d], where d is the nominal seed-diameter parameter; the theoretical mean and standard deviation are 1.1d and 0.2d/√12, respectively.

**Introduction P23:** change "mean grain diameter of 50 µm" to "nominal seed-diameter parameter of 50 µm (uniform interval 50–60 µm; theoretical seed mean 55 µm)".

**Table 3 P131 and Figure 10 caption/embedded axis:** use "Nominal seed-diameter parameter, d" if retaining existing numerical axis values. The existing uniform sweep's nominal range remains 10–200 microns, confirmed from its actual inputs. Alternatively, plot the true theoretical means on a new axis; do not relabel unchanged numbers as true means. Keep final tessellated-region sizes distinct from seed-input statistics.

**P147 and P154:** remove normal-distribution wording associated with the replacement uniform RNG study. Also change the embedded plot title, not just the caption; the provided replacement is already corrected.

## C. Use the new statistics to make a precise, modest claim

At 1% strain, set 3 (20 runs) has mean 539.13 MPa, sample SD 7.46 MPa, minimum 522.22 MPa, maximum 549.56 MPa, CV 1.38%, and total span 5.07% of the mean. These are endpoint stress statistics across simulations, not confidence intervals or material test uncertainty.

**Suggested replacement for the diameter-resampling part of Results P154:**

> At fixed uniform seed-size parameters, changing the size-sampling realization across 20 runs produced an average stress of 539.13 MPa at 1% strain, with a sample standard deviation of 7.46 MPa and a range of 522.22–549.56 MPa. Thus, realization changes produced modest but nonzero scatter in the global response under the tested conditions.

**Conclusion P291:** avoid both "no effect" and a general statistical ranking across unrelated parameter ranges. Minimal repair:

> Within the investigated parameter ranges, assigned yield strengths and area fractions strongly influenced the global response. Random size realizations at the tested uniform baseline produced modest global-response scatter. These results do not establish insensitivity to distribution width or family, or to local-field variations.

Retain the existing diameter-scale study but reconcile its wording separately: P154 currently describes little size influence, whereas P291 describes diameter as particularly influential. Do not use the incomplete normal comparison to invent a new final ranking.

## D. Short scientific-scope edits: keep these, defer a wholesale rewrite

These are short accuracy repairs, not a new manuscript structure:

1. **P32, add one definition:** "The four numerical phases represent effective yield-strength classes; they are not experimentally identified metallurgical phases."
2. **P281, preserve the existing adjustment disclosure and add:** "The final FE inputs in Table 5 are therefore indentation-informed, globally calibrated effective parameters rather than direct local-property measurements."
3. **P18 abstract:** replace the broad "validated" claim with "calibrated against reference behavior and compared with experimental cyclic results" where calibration-data independence has not been established.
4. **P266:** replace "To validate the accuracy" with "As a forward–reverse consistency check". This preserves Figure 18 without treating reconstruction of the input response as independent validation.
5. **P268, replace its strongest accuracy claim with:** "The inferred spread combines possible physical heterogeneity with measurement scatter and reverse-model uncertainty; additional indents do not by themselves remove systematic or sampling bias."
6. **P267, add one qualification:** "Indentation-bin frequencies were adopted as model fractions; their equivalence to unbiased spatial area fractions was not independently established."
7. **P282, qualify the Vickers explanation:** "Although Dao et al.'s experiments used Berkovich, their framework also includes Vickers geometry; the effect of experimental calibration and the adapted inverse assumptions was not isolated here." Primary-source details are in the earlier instrument notes.

If time is extremely tight, prioritize items 1–4 together with A–C; flag 5–7 explicitly for advisor approval rather than silently retaining stronger accuracy claims. Do not claim that the new normal runs repair the indentation-to-property inference gap.

## E. What no longer needs to be presented as unresolved

- The missing true uniform size-resampling test: set 3 now supplies it.
- A choice between replacing Figure 9(b) and deleting it: replacement is now preferred because a complete verified set exists.
- A need to change the whole paper to normal sampling: no. The uniform study can remain the primary reported study.

## F. What to keep out of the paper for this deadline

- Set 1's 19/21 matched-normal sweep: useful advisor evidence but incomplete, with single-realization differences up to 40.81 MPa at 1% strain; do not claim family robustness across sizes.
- Set 4's first 13/20 matched-normal ensemble: label preliminary on slides. A close baseline ensemble mean is not proof of equivalent distributions or local fields.
- Set 2: not started; no result to report.
- New EBSD/grain-distribution experiments, a broad literature expansion, an instrument fault diagnosis, or a new uncertainty campaign. Preserve them as limitations/follow-up questions where relevant.

## Two-hour execution order

- 25 min: replace Figure 9(b) and update caption.
- 25 min: correct Methods and Table 3 RNG/diameter definitions.
- 15 min: insert bounded numerical Results/conclusion wording.
- 25 min: apply short calibration/inference scope edits.
- 20 min: check active figures/cross-references and export a clean PDF.
- 10 min: buffer.

Do not spend this block waiting for the finest normal cases. Keep completed snapshots and incomplete labels explicit. No simulations were launched for this review.
