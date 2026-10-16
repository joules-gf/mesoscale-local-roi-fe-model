# Mesh-angle study outlier report

Verified cases: 24 existing + 4 new; all .sta successful and actual solved meshes match MSP nodes/connectivity.
Quality criteria are professor study criteria, not universal acceptance limits: r/R < 0.2 poor-screening; 0.2 <= r/R < 0.3 caution; >=0.3 good-screening. Edge ratio is descriptive, without an imposed acceptance criterion.
Angle violation tolerance: 1e-6 degrees. Requested 30 degrees is not a guarantee, especially at constrained small input angles.
r/R = 4 A^2/(s a b c); equilateral r/R=0.5. All elements included, no degenerates/nontriangles permitted.

## Paired stress changes
- 75 microns: 509.154107 -> 508.195971 MPa (-0.1882%).
- 150 microns: 507.242828 -> 506.169333 MPa (-0.2116%).
- 155 microns: 509.234261 -> 508.436048 MPa (-0.1567%).
- 160 microns: 511.064993 -> 510.447436 MPa (-0.1208%).

## Empirical IQR screening (not numerical causation)
- edge_ratio_max: existing24 IQR fences [2.35397, 2.37184]; bp_same_size_case_01=2.91713, bp_same_size_case_02=2.73782, mesh_angle30_075um=2.58742, mesh_angle30_150um=1.99942, mesh_angle30_155um=1.9984, mesh_angle30_160um=1.9996
- r_over_R_lt_0p2_fraction: existing24 IQR fences [0.000849911, 0.00327132]; bp_same_size_case_01=0.00541162, bp_same_size_case_02=0.00336852, mesh_angle30_075um=0, mesh_angle30_150um=0, mesh_angle30_155um=0, mesh_angle30_160um=0
- min_angle_below_requested_fraction: existing24 IQR fences [-4.15732e-05, 6.92887e-05]; bp_same_size_case_01=0.000388113, bp_same_size_case_02=0.000328637, bp_same_size_case_03=0.000176972, bp_same_size_case_04=7.87271e-05
- stress_at_1pct_MPa: existing24 IQR fences [488.286, 580.28]; none

## Worst actual elements
- bp_same_size_case_01: min r/R=0.141345, element 47135, centroid (0.18962107, 0.33177623) mm; min angle=19.1338 deg, max edge ratio=2.91713.
- bp_same_size_case_03: min r/R=0.14303, element 57933, centroid (0.13180576, -0.44257956) mm; min angle=21.7333 deg, max edge ratio=2.36399.
- bp_same_size_case_02: min r/R=0.144594, element 41673, centroid (-0.41733931, 0.052725358) mm; min angle=20.2317 deg, max edge ratio=2.73782.
- bp_same_size_case_05: min r/R=0.152575, element 29262, centroid (-0.13328679, -0.45261938) mm; min angle=21.9059 deg, max edge ratio=2.36208.
- bp_same_size_case_04: min r/R=0.15315, element 44831, centroid (0.032700241, 0.34660159) mm; min angle=21.712 deg, max edge ratio=2.36545.

Warnings are saved per case in simulation study/warnings; successful solves do not prove convergence or that morphology/mesh quality caused stress outliers.
Primary sources: MicroStructPy installed cli.py restart branches (seeds/poly reuse but omitted trimesh.txt triggers new triangulation); MicroStructPy settings documentation; Triangle -q documentation.
https://docs.microstructpy.org/en/latest/cli/settings.html
https://www.cs.cmu.edu/~quake/triangle.q.html
