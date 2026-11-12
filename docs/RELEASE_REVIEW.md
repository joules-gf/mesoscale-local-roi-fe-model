# Release review gates

Status: publication to main explicitly authorized by Julio. The validation limitations below remain; authorization is not evidence that all scientific/target-machine checks are complete.

## Implemented in this preparation

- Exact selected core script/reference-curve allowlist; minimal three-file monotonic/cyclic example set; retained core tests.
- Preserve the five selected normal result folders in full until individual result selection is agreed. Resolved XML beside outputs remains provenance, not an input campaign.
- Excluded research files remain local/ignored and preserved in checkpoint `4cc9de1`; trimming is index-only, not deletion of the research archive or Git history. Do not run destructive ignored-file cleanup such as `git clean -fdx`. This checkout's local preservation does not protect other checkouts applying the tracked deletions; retain the checkpoint and independent backups.
- The ROI exporter validates empty frame selections and values that cannot be converted to integers before backup restoration or ODB access. Actual frame bounds still require checking against the chosen ODB.
- ROI plotting separates phases by default, with explicit legacy grouping available.
- ROI global-CSV reader follows the extractor's one metadata row + header layout while retaining compatibility with older blank-line exports.
- Detailed function/class contribution records are retained privately, outside the published repository. Release-preparation implementation is separately disclosed as AI-assisted.

## Verification boundary

Tests use temporary fixtures or selected saved records. No new MicroStructPy generation, Abaqus solve or real ODB export is authorized or performed as release verification. Passing unit tests does not establish independent scientific validation, solver/version compatibility, unattended execution or arbitrary-geometry support. A clean-tree test verifies only the dependencies and behaviors actually exercised; requirements are not an environment lock.

## Remaining validation and review boundaries

- [ ] Julio reviews the exact keep/exclude list and selected output granularity.
- [ ] Confirm historical human/AI/third-party function contributions from declarations or records; do not infer them from Git author names. Record review separately from implementation.
- [ ] Review fixed four-material labels, modulus 71000 MPa, plastic-strain clipping/threshold, characteristic length and shape factor; choose which settings should become CLI/config inputs. Do not silently change historical numerical semantics.
- [ ] Review unit-square/triangular-mesh assumptions, hard-coded boundary/node-set/instance/step conventions and their failure behavior before advertising different geometry support.
- [ ] Replace the peak time-to-frame shortcut with verified ODB frame mapping, or explicitly keep its restricted scope.
- [ ] Review unconditional AA7075-T651 experimental overlays for other material choices, interactive postprocessing and legacy machine-specific direct-script defaults.
- [ ] Verify one fresh example and one ROI export on a licensed target machine, with unique output stems and a disposable ODB copy; launch only after explicit approval.
- [ ] Decide which historical saved figures/data should be highlighted; old aggregate plotter name/hash and historical external paths remain provenance, not current runnable links. Original output bytes stay unchanged.
- [ ] Confirm rights/licenses and inspect reachable history before public-release claims. A trimmed branch does not remove earlier files or secrets from history, and this preparation is not a comprehensive historical secret scan.
- [ ] Update the thesis appendix against the accepted code state; remove A.1.3, retain A.1.2 and contribution distinctions. No thesis edits are included here.
- [x] Julio explicitly authorized committing/pushing the reviewed release branch and merging it into main without force-push or history rewriting.

## Direct PE22 additions

The released runtime includes read-only ODB frame inventory, actual-time peak matching, signed direct PE22 summaries, triangular ROI phase-area calculation and explicit magnitude/log display. See `WORKFLOW.md` for restrictions and the historical reproduction path. Solver-free regression tests do not substitute for a licensed-target ODB export or a new solve. No new solve or thesis edit is part of publication.
