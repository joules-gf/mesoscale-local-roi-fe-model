# Mesoscale Local ROI FE Model

<!-- GITHUB_STAGE_1_HEADER -->

## Project status

This repository contains a research-oriented **mesoscale finite element modeling workflow** for local/global mechanical-response analysis and region-of-interest (ROI) postprocessing in aluminum alloys. It uses **MicroStructPy** for microstructure/mesh generation and **Abaqus** for finite-element simulation and `.odb` postprocessing.

The code is currently kept close to its original research-script form. The immediate goal is to make it easy to share, clone, and run on Windows machines while also allowing partial workflow validation in WSL/Linux where Abaqus may not be available.

## Repository layout

- `00_Main_Scripts/` — active pipeline scripts for input generation, Abaqus execution, `.odb` extraction, and postprocessing.
- `01_Secondary_Scripts/` — secondary analysis/plotting scripts.
- `simulation_inputs/` — XML input cases and parameter-study inputs.
- `archive/old_script_versions/` — older script versions preserved for reference.
- `environment_notes.md` — setup notes for Windows, VS Code, WSL, Python dependencies, and Abaqus-specific limitations.
- `requirements.txt` — regular Python dependencies. Abaqus Python modules are provided by Abaqus and are not installed from pip.

## Quick setup

### Regular Python environment

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux/WSL:
source .venv/bin/activate

pip install -r requirements.txt
```

### Important Abaqus note

The full simulation workflow requires **Abaqus** to be installed and callable from the terminal as `abaqus`.

Some scripts, especially `getForceDisp.py`, must run inside the Abaqus Python environment using commands such as:

```bash
abaqus cae noGUI=path/to/getForceDisp.py
```

Those Abaqus-only modules, including `abaqus`, `abaqusConstants`, and `odbAccess`, should not be installed with pip.

## Current main entry point

The current full-pipeline entry point is:

```bash
python 00_Main_Scripts/full_simulation_runner.py
```

At this stage, some paths are still hardcoded for the original Windows development machine. The next portability step is to replace those hardcoded paths with project-relative paths using `pathlib` and/or command-line arguments.

## Cross-platform goal

Target usage:

- **Windows + VS Code:** run the full Abaqus workflow on a computer with Abaqus installed.
- **WSL/Linux:** validate Python logic, file layout, XML handling, plotting utilities, and non-Abaqus portions of the workflow.

Abaqus execution itself generally needs a machine/license where Abaqus is installed and configured.

---

This project is a **fully automated mesoscale FE modeling pipeline** built on top of MicroStructPy and Abaqus, with support for local/global response comparison and ROI postprocessing.

It extends the workflow from **input preprocessing → mesh generation → Abaqus simulation → postprocessing**, allowing you to run an entire simulation with minimal manual intervention.

If you'd just like to quickly run a simulation, you can skip this reading and go to the **Demo section below**.

---

## What this project does

Put simply, you can:

1. Submit an XML input file describing:

   * Microstructure (phases, shape, sizes)
   * Domain geometry
   * Abaqus simulation parameters (E, ν, plastic stresses, strain applied)

2. The script automatically can:

   * Expand `<include>` XML files to include Abaqus simulation parameters
   * Fill missing parameters (e.g., standard deviations)
   * Generate a MicroStructPy mesh
   * Convert it into an Abaqus `.inp` file
   * Insert:

     * Materials
     * Boundary conditions
     * Steps
     * Output requests

3. Run the Abaqus simulation

4. Postprocess results:

   * Extract force–displacement from `.odb`
   * Convert to stress–strain
   * Compare against:

     * ROM AA7075-T6 curve
     * Experimental data
   * Generate plots

---

## Overall Workflow

```
XML Input File
     ↓
[abaqus_input_generation_v02.py]
     ↓
MicroStructPy Mesh + Abaqus .inp
     ↓
[run_abaqus_sim.py]
     ↓
Abaqus Simulation (.odb)
     ↓
[getForceDisp.py]
     ↓
Force–Displacement CSV
     ↓
[postprocessing_abaqus_sim_v01.py]
     ↓
Plots + Analysis
```

---

## Main Scripts

### 1) Input Generation & Preprocessing

📄 `abaqus_input_generation_v02.py` 

Handles:

* XML parsing and `<include>` expansion
* Default parameter completion (i.e., std = 20% of mean, if no std is provided)
* Cyclic loading definition (periodic amplitude)
* MicroStructPy execution
* Abaqus `.inp` file completion:

  * Materials
  * Sections
  * Boundary conditions
  * Step definition
  * Output requests

⚠️ Important notes:

* Requires **at least 2 phases** to avoid unkown bug
* If one phase lacks `scale`, all phases will be assigned default values

#### Cyclic Loading Pre-Visualization (Optional)

This module includes a feature to **pre-visualize the expected cyclic loading profile before running the simulation**.

When cyclic parameters are defined in the input file (`<cyclic_parameters>`), the script generates a **time–amplitude waveform** based on the specified:

* Strain ratio ( R )
* Frequency ( f )
* Time increment ( \Delta t )
* Phase shift (controlled by `start_min`)

Internally, the loading follows a periodic formulation of the form:

$$ A(t) = A_0 + B \sin(\omega t + \phi) $$

where:

* ( $A_0$ ) = mean amplitude
* ( $B$ ) = amplitude range
* ( $\omega = 2\pi f$ )
* ( $\phi$ ) = phase shift

A preview plot is displayed **before the simulation begins**, allowing you to:

* Verify the correctness of the loading definition
* Inspect resolution based on the chosen time increment
* Confirm whether the cycle starts at maximum or minimum strain

You are then prompted to:

* **Continue** with the simulation, or
* **Abort** and adjust parameters

If accepted, the waveform is saved as:

```id="z3e8rm"
expected_cycles_<simulation_name>.png
```

and stored alongside the simulation outputs for reference.

This is particularly useful when working with:

* High-frequency loading (risk of under-resolution)
* Non-standard ( R )-ratios
* Debugging cyclic boundary condition behavior in Abaqus

---


### 2) Full Simulation Runner

📄 `full_simulation_runner.py` 

This is the **main entry point**.

It:

1. Calls input generation
2. Runs Abaqus simulation
3. Executes postprocessing

This is the script you should run for a full pipeline.

---

### 3) Abaqus Data Extraction

📄 `getForceDisp.py` 

Runs inside Abaqus (`noGUI`) and:

* Opens `.odb`
* Extracts:

  * Reaction force (RF)
  * Displacement (U)
* Outputs a CSV:

  ```
  Step Time | U_Y | Total RF_Y
  ```

Key assumption:

* Uses node sets:

  * `BOTTOMNODES`
  * `UPPERNODES`

---

### 4) Postprocessing & Plotting

📄 `postprocessing_abaqus_sim_v01.py` 

Handles:

* Running `getForceDisp.py`
* Loading CSV data
* Assummes that domain is of unit length:

  * Stress = Force / 1
  * Strain = Displacement / 1
* Plotting:

  * Simulation vs ROM curve
  * Simulation vs experimental data
  * Cyclic displacement vs time

⚠️ Important assumption:

* Domain size = 1 →

  ```
  stress = force
  strain = displacement
  ```

---

## Demo

### Quick Setup

1. Go to:

```
00_Main_Scripts/full_simulation_runner.py
```

2. Modify:

```python
input_files_folder = r'YOUR_PATH_TO_INPUTS'
```

Options:

* `''` → opens GUI file selector
* Full path → directly loads from folder

3. Run:

```bash
python full_simulation_runner.py
```

---

## Input File Requirements

Your XML input should include:

### Required Sections

* `<domain>`
* `<material>` (multiple phases recommended)
* `<abaqus>`

### Example Abaqus Parameters

```xml
<abaqus>
  <E> 71000 </E>
  <nu> 0.33 </nu>
  <displacement_yy> 0.01 </displacement_yy>
  <plastic_stresses> 350, 470, 710, 710 </plastic_stresses>
</abaqus>
```

### Optional (Cyclic Loading)

```xml
<abaqus>
  <cyclic_parameters>
    <rRatio_strain>-1</rRatio_strain>
    <frequency_hz>1</frequency_hz>
    <time_increment_s>0.01</time_increment_s>
    <start_min>true</start_min>
  </cyclic_parameters>
</abaqus>
```

---

## Output Structure

```
simulation_outputs/
└── simulation_name/
    ├── msp_mesh_files/
    │   ├── *.inp (raw mesh)
    │   ├── polymesh.png
    │   ├── seeds.png
    │   └── trimesh.png
    ├── abaqus_files/
    │   ├── simulation_name.inp (final input)
    │   ├── simulation report files
    │   └── simulation_name.odb
    ├── stress_strain_simulation_name.png
    ├── simulation_name.csv
    ├── cycles_simulation_name.png
```

---

## Key Design Features

### 1) Automatic Input Completion

* Handles missing statistical parameters
* Ensures MicroStructPy compatibility

### 2) Abaqus Input Injection System

* Modular insertion via:

```python
insert_text_in_abaqus_file(...)
```

### 3) Cyclic Simulation Support

* Generates periodic amplitude:

```
A(t) = A0 + B sin(ωt + φ)
```

### 4) Fully Scripted Pipeline

* No GUI dependency (except optional file picker)
* End-to-end automation

---

## Limitations / Assumptions

* Requires:

  * Abaqus installed and callable via CLI
  * MicroStructPy installed
* Assumes:

  * 2D domain with unit dimensions (for stress/strain interpretation)
* Mesh format:

  * Triangle/TetGen compatible
* Node set naming must remain consistent:

  * `Ext-Surface-3`, `Ext-Surface-4`

---

## Suggested Use Cases

* Fatigue microstructure studies
* Cyclic loading simulations
* Validation against ROM or experimental data

---

## Next Steps

Based on your workflow, the next logical upgrades would be:

* Batch simulation runner (multiple XMLs automatically)
* Mesh convergence automation 
* ROI-based stress/strain extraction 
* Parallel execution for large studies
