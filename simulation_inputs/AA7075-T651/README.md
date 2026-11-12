# AA7075-T651 normal baseline inputs

- `aa7075_t651_baseline_mesh.xml`: unit square, side 1; four circle phases, normal diameter mean 0.050 mm each. **Scale is omitted**: `complete_input_data` supplies 0.2 * loc = 0.010 mm standard deviation in every phase.
- `aa7075_t651_baseline_parameters.xml`: E auto -> 70000 MPa via the material registry; nu 0.33 (existing material example; registry does not define nu), displacement_yy 0.01, minimum angle 25 degrees, maximum edge 0.00328, size RNG 1000. Position RNG remains omitted, matching the normal baseline; do not describe it as an explicit fixed-position ensemble. verbose True, restart False. Seeds/poly text requested; completion forces tri format to Abaqus.
- Monotonic input includes the local parameters and has no cyclic settings.
- Cyclic input uses strain ratio -1, frequency 5 Hz, start_min False, time_increment_s 0.01, num_increments_step 250, plot_before False. These loading controls follow the regular `strainRratio-1.xml` example, except plot_before is disabled for noninteractive use.

AA7075 yields/fractions follow the current normal baseline: 410/470/680/710 MPa and 10/10/40/40%.

Geometry/distribution source: `simulation_inputs/Normal Distribution/aa7075-T651-base-mesh.xml`. Standard mesh controls use the regular examples' 0.00328 maximum edge, **not** the sensitivity baseline's finer 0.0026. Fresh runs intentionally use restart False. Includes are wholly local to this folder; reference curves are resolved by material name, with no machine-specific CSV path stored here. Helpers and cases have globally distinct material-specific stems, since output identity is the XML stem.

## Manual runs from the repository root (not executed during preparation)

```powershell
$env:MICROSTRUCTURE_NONINTERACTIVE="1"
$env:MPLBACKEND="Agg"
$env:PYTHONIOENCODING="utf-8"
.venv/Scripts/python.exe 00_Main_Scripts/full_simulation_runner.py --input-file simulation_inputs/AA7075-T651/aa7075_t651_normal_monotonic.xml
.venv/Scripts/python.exe 00_Main_Scripts/full_simulation_runner.py --input-file simulation_inputs/AA7075-T651/aa7075_t651_normal_cyclic_Rminus1.xml
```

Run the cases, not the helper XMLs; inspect existing `simulation_outputs/<case-stem>` before launching. Input verification is not a mesh or FE solve. `plot_before=False` still enters the current completion helper's plotting branch because it tests presence, so the noninteractive environment above is required to avoid a GUI; no source behavior was changed.

This folder is included in the release allowlist. Input checks do not launch mesh generation or a solve.
