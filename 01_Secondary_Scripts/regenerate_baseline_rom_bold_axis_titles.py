#!/usr/bin/env python3
"""Regenerate the baseline ROM comparison figure with bold axis titles."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
MAIN_SCRIPTS = REPO / "00_Main_Scripts"
sys.path.insert(0, str(MAIN_SCRIPTS))

from postprocessing_abaqus_sim_v01 import compute_area, load_csv  # noqa: E402

CASE = "baseline_parameters_mel_0p00175"
OUT_DIR = REPO / "simulation_outputs" / CASE
REFERENCE_CSV = MAIN_SCRIPTS / "material_reference_curves" / "aa7075-T6_monotonic_ROM_cyclic_parameters.csv"
RESULTS_CSV = OUT_DIR / f"{CASE}.csv"
OUTPUT_PNG = OUT_DIR / "stress_strain_baseline_parameters_most_recent_mesh_calibri_bold_axis_titles.png"


def register_calibri() -> None:
    for font_path in [
        "/mnt/c/Windows/Fonts/calibri.ttf",
        "/mnt/c/Windows/Fonts/calibrib.ttf",
    ]:
        if os.path.exists(font_path):
            fm.fontManager.addfont(font_path)
    plt.rcParams["font.family"] = "Calibri"


def main() -> None:
    register_calibri()

    ref_strain, ref_stress = load_csv(str(REFERENCE_CSV), strain_col=0, stress_col=1)
    sim_strain, sim_stress = load_csv(str(RESULTS_CSV), strain_col=1, stress_col=2)
    ref_area = compute_area(ref_strain, ref_stress)
    sim_area = compute_area(sim_strain, sim_stress)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    ax.plot(
        ref_strain,
        ref_stress,
        label=f"ROM of AA7075-T6 (Area = {ref_area:.3f})",
        linewidth=4,
        ls="--",
        color="black",
    )
    ax.plot(
        sim_strain,
        sim_stress,
        label=f"Simulation (Area = {sim_area:.3f})",
        linewidth=3,
        color="red",
    )

    ax.set_title("Comparison of Simulation against ROM of AA7075-T6", fontname="Calibri", fontsize=22, pad=12)
    ax.set_xlabel("Strain", fontname="Calibri", fontsize=20, fontweight="bold")
    ax.set_ylabel("Stress (MPa)", fontname="Calibri", fontsize=20, fontweight="bold")
    ax.tick_params(axis="both", labelsize=18)
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontname("Calibri")

    ax.grid(True)
    ax.legend(loc="lower right", prop={"family": "Calibri", "size": 18}, frameon=True)

    fig.subplots_adjust(left=0.13, right=0.98, bottom=0.14, top=0.88)
    fig.savefig(OUTPUT_PNG)
    plt.close(fig)

    print(f"saved={OUTPUT_PNG}")
    print(f"ref_area={ref_area:.3f}")
    print(f"sim_area={sim_area:.3f}")


if __name__ == "__main__":
    main()
