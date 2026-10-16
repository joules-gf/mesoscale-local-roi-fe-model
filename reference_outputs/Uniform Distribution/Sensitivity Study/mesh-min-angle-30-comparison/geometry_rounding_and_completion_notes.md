# Completion and geometry-rounding qualification

The four requested 30-degree cases completed successfully. The existing successful 160-micron solve was resumed without resubmission; its original runtime record remains intact. Independent readback verified 28 cases (20 originals + 4 original midpoint solves + 4 angle-30 solves), 28 per-element CSVs, and 1,985,294 element records. All actual solver-input nodes/connectivity match the corresponding MicroStructPy INP. Original 24 source mesh/curve SHA-256 hashes match the saved pre-resume audit.

## Geometry is approximate, not full-precision identical

The installed MicroStructPy PolyMesh TXT serializer uses Python `{: e}`: six digits after the scientific-notation decimal, i.e. seven significant digits, NOT six significant digits. For the sub-unit mm coordinates in this study, individual coordinate rounding can approach 5e-8 mm; vector/projection errors can therefore exceed 5e-8 mm. The explicitly bounded study tolerance is 1e-7 mm. It must not be generalized to unrelated geometries.

All source polygon facets, endpoint spans/segment lengths, and occupied seed/material associations were checked before triangulation. Loaded saved caches were checked against both original and new meshes after triangulation. Pre/post seed/polygon cache hashes agree. Maximum perpendicular source-facet errors are 6.404182945108306e-8 mm (75 microns), 6.028723217469137e-8 mm (150), 6.013871031720884e-8 mm (155), and 6.806506944259745e-8 mm (160). Geometry proofs explicitly record `exact_geometry_identity: false`.

Regression tests accept a 4e-8 mm rounding perturbation and reject a 2e-7 mm displacement, shortened facet, and changed material assignment. All six tests passed on both Windows Python and WSL Python.

## Interpretation limits

Every new case has zero elements with r/R < 0.2. The 150/155/160-micron meshes meet the 30-degree minimum within the 1e-6-degree reporting tolerance. The 75-micron mesh retains one below-requested triangle: minimum angle 20.87453356697565 degrees. Do not interpret the requested mesher angle as an unconditional achieved minimum.

Across the 24 originals, cases 01 and 02 are the principal high-side IQR mesh-quality outliers (maximum edge ratio and fraction r/R < 0.2), not cases 08/16. There are no stress IQR outliers under the specified existing24 fences. Quality improvement and paired stress changes do not establish mesh convergence or numerical causation.

## Durable verification

- `independent_readback_verification.json`: all acceptance flags true; independent node-based metrics, percentile tails/bands/worst IDs, original hashes, paired stresses and three PNG figures verified.
- `verification.json`: all28 solve/mesh match and PNG integrity evidence.
- Simulation study `resumed_batch.log`, `independent_verification.log`, `windows_regression_tests.log`, `wsl_regression_tests.log`, `runtime_summary.csv`, and per-case `geometry_preservation.json` contain execution evidence.
