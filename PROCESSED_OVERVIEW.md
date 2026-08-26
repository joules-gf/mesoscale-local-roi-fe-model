# Processed overview: mesoscale local ROI FE model

Processed from uploaded zip: `/home/hermes/.hermes/cache/documents/doc_b709858ccae1_microstucture fatigue simulation.zip`

Extraction path: `/workspace/mesoscale_local_roi_fe_model`

## Archive integrity and size

- Zip entries: 157
- Compressed size: 1,294,004 bytes
- Uncompressed size: 1,894,232 bytes
- SHA-256: `9a1d8fc18895667a27a3a36a4de62df3a5f94221ff457e8d0acf221233c3ebe3`
- No suspicious absolute paths or `..` path traversal entries were detected before extraction.

## What this project is

This is an automated mesoscale local ROI FE model pipeline built around:

1. XML input files describing domain, material phases, and Abaqus settings.
2. MicroStructPy mesh generation.
3. Abaqus `.inp` generation and Abaqus job execution.
4. Abaqus `.odb` force/displacement extraction.
5. Stress-strain/cyclic postprocessing and comparison against ROM/experimental reference curves.

The project README identifies `00_Main_Scripts/full_simulation_runner.py` as the intended main entry point.

## Directory structure

- `00_Main_Scripts/`
  - Main end-to-end pipeline scripts.
  - Contains Abaqus input generation, simulation launching, `.odb` extraction, postprocessing, and material reference curves.
- `01_Secondary_Scripts/`
  - Analysis and plotting utilities: ROM curvature analysis, fatigue comparison plots, strain-energy balance, plotting batches of simulation CSVs.
- `simulation_inputs/`
  - XML input cases for AA7075-T6 studies.
  - Includes baseline mesh/parameters and parameter-sweep case families.
- `Readme.md`
  - Project explanation, workflow, demo, assumptions, and suggested future upgrades.

## File inventory

File counts by extension:

- `.xml`: 98 files, 103,153 bytes
- `.py`: 16 files, 140,205 bytes
- `.png`: 14 files, 1,101,978 bytes
- `.csv`: 7 files, 447,416 bytes
- `.pyc`: 6 files, 93,936 bytes
- `.md`: 1 file, 7,544 bytes

Top-level file counts:

- `simulation_inputs`: 103 files
- `01_Secondary_Scripts`: 20 files
- `00_Main_Scripts`: 18 files
- `Readme.md`: 1 file

## Main pipeline scripts

- `00_Main_Scripts/full_simulation_runner.py`
  - Calls `generate_input(...)`, then `run_simulation(...)`, then `post_processing(...)`.
  - Currently has a hardcoded Windows input folder path.

- `00_Main_Scripts/abaqus_input_generation_v02.py`
  - Current/main version of input generation.
  - Handles XML includes, missing input defaults, cyclic loading waveform creation, MicroStructPy execution, `.inp` copying, and Abaqus input file completion.
  - Largest project file: 843 total lines, about 574 code-ish lines.

- `00_Main_Scripts/run_abaqus_sim.py`
  - Changes into the Abaqus output directory and runs:
    - `abaqus j={simulation_name} interactive`

- `00_Main_Scripts/getForceDisp.py`
  - Intended to run under Abaqus CAE `noGUI`.
  - Uses Abaqus modules such as `abaqus`, `abaqusConstants`, and `odbAccess`.
  - Extracts reaction force and displacement from named node sets.

- `00_Main_Scripts/postprocessing_abaqus_sim_v01.py`
  - Calls Abaqus CAE noGUI extraction.
  - Loads generated CSV results.
  - Plots simulation vs ROM, cyclic displacement vs time, and simulation vs experimental data.

## Secondary scripts

- `01_Secondary_Scripts/curvature_ofROM.py`
  - ROM curve generation/curvature/second-derivative analysis and piecewise fitting.
- `01_Secondary_Scripts/strain_energy_balance.py`
  - Attempts to infer missing phase yield stress using energy balance.
- `01_Secondary_Scripts/plot_ROM_vs_sim_folder.py`
  - Batch plots simulation CSVs against ROM.
- `01_Secondary_Scripts/stress_strain_fatigue_approach_comparison*.py`
  - Fatigue/S-N comparison plotting.

## Simulation input families

XML cases by directory:

- `simulation_inputs/AL7075-T6/bp_dif_size`: 21 XML files
- `simulation_inputs/AL7075-T6/bp_diff_vf`: 21 XML files
- `simulation_inputs/AL7075-T6/bp_dif_position`: 20 XML files
- `simulation_inputs/AL7075-T6/bp_dif_rng_size`: 20 XML files
- `simulation_inputs/AL7075-T6`: 7 XML files
- `simulation_inputs/AL7075-T6/diff_yields_vfs`: 5 XML files
- `simulation_inputs/AL7075-T6/elliptical_grains`: 3 XML files
- `simulation_inputs`: 1 XML file

Notable examples:

- `baseline_mesh.xml`
  - Unit square domain, four circular material phases.
- `baseline_parameters.xml`
  - Includes `baseline_mesh.xml`; defines Abaqus E, nu, displacement, plastic stresses, and MicroStructPy settings.
- `strainRratio-1_15cycles.xml`
  - Includes `baseline_parameters.xml`; adds cyclic loading parameters.
- `bp_diff_vf/case_study_overview_vf.csv`
  - 20 volume-fraction cases.

## Dependencies inferred from imports

Python-side imports include:

- Standard library: `os`, `csv`, `math`, `sys`, `tempfile`, `shutil`, `pathlib`, `itertools`, `re`, `copy`, `xml`
- Scientific/plotting: `numpy`, `pandas`, `matplotlib`
- GUI: `tkinter`
- Simulation: `microstructpy`
- Abaqus Python runtime only: `abaqus`, `abaqusConstants`, `odbAccess`

On the current Hermes WSL environment:

- `numpy`: available
- `pandas`: missing
- `matplotlib`: missing
- `microstructpy`: missing
- `abaqus`: not detected on PATH

So I could inspect and syntax-check the code, but I could not run the full simulation pipeline here without installing dependencies and having Abaqus available.

## Checks performed

- Safely inspected the zip before extraction.
- Extracted to `/workspace/mesoscale_local_roi_fe_model`.
- Parsed Python files with `compileall`.
- Result: Python syntax compilation passed for all `.py` files.
- Parsed the Python AST to identify imports and function definitions.
- Read the README and representative XML inputs.

## Initial issues / risks noticed

1. Hardcoded Windows paths

   Several scripts contain paths like:

   - `C:\Users\MAEadmin\Desktop\mesoscale local ROI FE model\...`
   - OneDrive paths in older postprocessing script examples.

   This will be fragile for collaborators unless moved to command-line arguments, a config file, or path auto-discovery.

2. `os.system(...)` use

   Abaqus execution currently uses `os.system`, for example:

   - `abaqus j={simulation_name} interactive`
   - `abaqus cae noGUI=..\..\..\00_Main_Scripts\getForceDisp.py`

   This works for quick scripts, but `subprocess.run([...], check=True)` would be safer, more debuggable, and more cross-platform.

3. Windows path separator in Abaqus noGUI call

   `postprocessing_abaqus_sim_v01.py` uses backslashes in:

   - `..\..\..\00_Main_Scripts\getForceDisp.py`

   This is Windows-specific. It should be constructed with `pathlib.Path` or `os.path.join`.

4. Unit-domain assumption

   The postprocessing assumes domain side length = 1, so:

   - stress = force / 1
   - strain = displacement / 1

   This is valid only if the simulation domain and thickness/area assumptions are consistent. If future geometries change, this becomes a scientific correctness risk.

5. Interactive GUI/plot prompts in automation path

   The main generation code can use file dialogs and cyclic pre-visualization prompts. These are useful manually but may block batch or cluster runs.

6. Versioned duplicate scripts

   There are `abaqus_input_generation_v00.py`, `v01.py`, and `v02.py`, plus two postprocessing versions. This is okay for development history, but for thesis reproducibility I would recommend marking one official pipeline and moving old versions to `archive/`.

7. Missing dependency declaration

   No `requirements.txt`, `environment.yml`, or setup instructions were found. This will make reproduction harder.

8. Included `__pycache__` files

   The archive includes Python bytecode caches. These are not needed and should usually be excluded from shared source archives.

## Recommended next improvements

Highest priority:

1. Add `requirements.txt` or `environment.yml` for non-Abaqus dependencies.
2. Replace hardcoded input/output paths with CLI arguments or a config file.
3. Replace `os.system` with `subprocess.run` and capture errors.
4. Make path handling cross-platform using `pathlib.Path`.
5. Add a small `run_demo.py` or command example using a known XML input.
6. Create a `.gitignore` excluding `__pycache__/`, Abaqus output files, and generated plots/CSVs if not intended as source data.

For scientific robustness:

1. Make domain dimensions and cross-sectional area explicit in postprocessing.
2. Store simulation metadata next to each output: input XML, git commit/version, mesh parameters, Abaqus settings, and postprocessing assumptions.
3. Add validation checks for XML inputs before running expensive simulations.
4. Add batch-run support for the parameter-sweep folders.

## Bottom line

This is a promising and fairly complete research pipeline, not just a loose script collection. The core idea is clear: XML-driven MicroStructPy microstructure generation, Abaqus simulation, then ROM/experimental comparison. The biggest practical risks are reproducibility and portability: hardcoded Windows paths, missing dependency file, interactive prompts in the main path, and implicit unit-domain stress/strain assumptions.
