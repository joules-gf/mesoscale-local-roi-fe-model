# ROI stress–plastic strain partitioning

Date captured: 2026-06-18

## Research question

Is it defensible to say that, in the ROI postprocessing results, regions with lower local stress can show higher local plastic strain, while regions with higher local stress can show lower local plastic strain?

## Short answer

Yes, but the statement needs to be phrased carefully.

The simple wording:

> When local stress is low, plastic strain tends to be high; when local stress is high, plastic strain tends to be low.

should **not** be presented as a universal pointwise law. It is better to frame it as a stress–strain partitioning behavior under imposed global strain / compatibility constraints.

A safer statement is:

> Under strain-controlled or compatibility-constrained cyclic loading, heterogeneous ROIs can show stress–strain partitioning. Softer, more favorably deforming, or locally less constrained regions may accommodate more plastic strain while comparatively harder, stiffer, or more constrained regions carry higher elastic stress and accumulate less plastic strain.

## Mechanical intuition

For a simple small-strain uniaxial decomposition:

```text
total strain = elastic strain + plastic strain
plastic strain = total strain - stress / E
```

So if two nearby regions experience comparable imposed total strain and have a similar modulus, the region with lower stress can have a larger inferred plastic strain.

This is especially relevant in strain-controlled fatigue, where the imposed macroscopic strain amplitude is split into elastic and plastic contributions. Local microstructure can cause different ROIs to partition that imposed deformation differently.

## Important caveats

This trend is not guaranteed everywhere. Exceptions can arise from:

- local stress concentrations;
- multiaxial stress state / triaxiality;
- crystallographic orientation;
- phase morphology and constraint from neighboring phases;
- residual stress;
- cyclic hardening or softening;
- differences in elastic/plastic material properties between phases;
- averaging over an ROI rather than evaluating a single material point.

So the thesis/presentation claim should be about **observed ROI-level partitioning**, not a universal material law.

## How to explain the normalized representative-ROI plot

The normalized plot should not be interpreted as directly comparing stress units to strain units.

Instead:

```text
normalized stress = |local ROI stress| / |global stress|
normalized strain = local ROI plastic strain / global plastic strain estimate
```

Both quantities are dimensionless indicators relative to the global specimen response.

Suggested audience explanation:

> The left panel is normalized so stress and plastic strain can be compared as relative enrichment/depletion measures. A value above 1 means the selected ROI is above the global reference; a value below 1 means it is below the global reference. The goal is not to compare MPa directly to strain, but to show whether a region is mechanically amplified or reduced relative to the global loading state.

Then connect the phase-fraction panel:

> The phase-fraction panel shows the local microstructural makeup of those same ROIs. This lets us ask whether a region with lower normalized stress but higher normalized plastic strain is associated with a different local phase composition.

## Literature anchors to read

These are useful starting points for building intuition about local stress/strain partitioning, heterogeneous deformation, and fatigue initiation:

1. Tasan et al., “Integrated experimental-simulation analysis of stress and strain partitioning in multiphase alloys,” *Acta Materialia*, 2014. DOI: https://doi.org/10.1016/j.actamat.2014.07.071
2. Ghadbeigi et al., “Local plastic strain evolution in a high strength dual-phase steel,” *Materials Science and Engineering A*, 2010. DOI: https://doi.org/10.1016/j.msea.2010.04.052
3. Kang et al., “Digital image correlation studies for microscopic strain distribution and damage in dual phase steels,” *Scripta Materialia*, 2007. DOI: https://doi.org/10.1016/j.scriptamat.2007.01.031
4. Barbe et al., “Intergranular and intragranular behavior of polycrystalline aggregates. Part 1: F.E. model,” *International Journal of Plasticity*, 2001. DOI: https://doi.org/10.1016/S0749-6419(00)00061-9
5. Di Gioacchino and da Fonseca, “Plastic strain mapping with sub-micron resolution using digital image correlation,” *Experimental Mechanics*, 2015. DOI: https://doi.org/10.1007/s11340-014-9972-5
6. Sangid, “The physics of fatigue crack initiation,” *International Journal of Fatigue*, 2013. DOI: https://doi.org/10.1016/j.ijfatigue.2012.10.009
7. Clyne and Withers, *An Introduction to Metal Matrix Composites*, Cambridge University Press, 1993. DOI: https://doi.org/10.1017/CBO9780511623080
8. Lloyd, “Particle reinforced aluminium and magnesium matrix composites,” *International Materials Reviews*, 1994. DOI: https://doi.org/10.1179/imr.1994.39.1.1

## Reading goals for Julio

When reading these papers, focus on:

- how authors distinguish stress partitioning from strain partitioning;
- whether the experiment/simulation is strain-controlled, stress-controlled, or compatibility-constrained;
- whether plots compare local values to global/macroscopic references;
- how local phase fraction, morphology, and constraint are connected to local plasticity;
- how carefully the authors phrase causality versus correlation.

## Thesis-safe phrasing draft

> The ROI results suggest local stress–strain partitioning near the specimen edges. ROIs with lower normalized stress can exhibit higher normalized plastic strain, while ROIs with higher normalized stress can exhibit lower normalized plastic strain. This should be interpreted as an ROI-averaged partitioning trend under imposed global cyclic strain, not as a universal pointwise inverse law between stress and plastic strain. Local phase composition, constraint, stress concentration, and cyclic material response may all influence the observed partitioning.
