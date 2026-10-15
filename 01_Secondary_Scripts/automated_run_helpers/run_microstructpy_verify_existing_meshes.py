"""Run MicroStructPy's verify flag on existing same-mean-diameter meshes.

This does not rerun Abaqus. It reuses the saved MicroStructPy artifacts in
``simulation_outputs/sensitivity-mean-diameter-diff-4all-phases/<case>/msp_mesh_files``
with restart enabled and creates/updates the MicroStructPy ``verification``
folder for selected cases.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SCRIPTS = PROJECT_ROOT / "00_Main_Scripts"
INPUT_DIR = PROJECT_ROOT / "simulation_inputs" / "Uniform Distribution" / "sensitivity-study-AA7075-T651" / "bp_same_mean_diameter"
OUTPUT_BASE = PROJECT_ROOT / "simulation_outputs" / "sensitivity-mean-diameter-diff-4all-phases"
CASES = [
    "bp_same_size_case_08",
    "bp_same_size_case_16",
    "bp_same_size_case_09",
    "bp_same_size_case_15",
]

sys.path.insert(0, str(MAIN_SCRIPTS))
from abaqus_input_generation_v02 import complete_input_data, get_microstructpy  # noqa: E402


def run_verify(case: str) -> Path:
    input_xml = INPUT_DIR / f"{case}.xml"
    mesh_dir = OUTPUT_BASE / case / "msp_mesh_files"

    if not input_xml.exists():
        raise FileNotFoundError(input_xml)
    if not mesh_dir.exists():
        raise FileNotFoundError(mesh_dir)

    complete_input, _simulation_name, _output_dir, _default_mesh_dir, _ec_dir, _resolved = complete_input_data(input_xml)
    domain, phases, settings, _abaqus = complete_input

    settings["directory"] = str(mesh_dir)
    settings["restart"] = True
    settings["verify"] = True
    settings.setdefault("filetypes", {})
    settings["filetypes"].setdefault("verify_plot", "png")

    print(f"===== VERIFY {case} =====", flush=True)
    print(f"mesh_dir: {mesh_dir}", flush=True)
    msp = get_microstructpy()
    msp.cli.run(phases=phases, domain=domain, **settings)
    ver_dir = mesh_dir / "verification"
    print(f"verification_dir: {ver_dir}", flush=True)
    return ver_dir


def main() -> int:
    os.chdir(PROJECT_ROOT)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MICROSTRUCTURE_NONINTERACTIVE", "1")
    for case in CASES:
        run_verify(case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
