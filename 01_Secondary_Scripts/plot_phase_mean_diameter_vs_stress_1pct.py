"""Plot phase mean diameter versus stress at 1% strain.

This script reads the same-mean-diameter sensitivity-study cases from
``reference_outputs/Sensitivity Study/lower-bound-diameter-equal-4all-phases``.
For each case it extracts:

- phase mean diameter from the resolved input XML ``material/size/loc`` values,
  converted from mm to microns
- stress at 1% strain from the case CSV, interpolating if needed

The generated figure is saved in the sensitivity-study folder.
"""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = (
    REPO_ROOT
    / "reference_outputs"
    / "Uniform Distribution"
    / "Sensitivity Study"
    / "lower-bound-diameter-equal-4all-phases"
)
OUTPUT_FIG = RESULTS_DIR / "phase_mean_diameter_vs_stress_at_1pct_strain.png"
TARGET_STRAIN = 0.01
MM_TO_MICRONS = 1000.0

# Regular figure dimensions; text sizes are matplotlib defaults + 6 pt.
FIG_SIZE = (8, 6)
LABEL_SIZE = 16
TITLE_SIZE = 18
LEGEND_SIZE = 16
TICK_SIZE = 16


def read_phase_mean_diameter_microns(xml_path: Path) -> float:
    """Return the common phase mean diameter from a resolved input XML file.

    The XML stores ``material/size/loc`` in mm; the plot x-axis is in microns.
    """
    root = ET.parse(xml_path).getroot()
    diameters_mm = []

    for material in root.findall("material"):
        loc = material.findtext("size/loc")
        if loc is not None:
            diameters_mm.append(float(loc.strip()))

    if not diameters_mm:
        raise ValueError(f"No material/size/loc values found in {xml_path}")

    rounded = {round(value, 12) for value in diameters_mm}
    if len(rounded) != 1:
        raise ValueError(
            f"Expected all phases to have the same mean diameter in {xml_path}; "
            f"found {diameters_mm} mm"
        )

    return diameters_mm[0] * MM_TO_MICRONS


def read_stress_at_strain(csv_path: Path, target_strain: float = TARGET_STRAIN) -> float:
    """Return stress at target strain from a case CSV, with linear interpolation."""
    points: list[tuple[float, float]] = []

    with csv_path.open(newline="") as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            try:
                # Case CSV columns: Step Time, U_Y/strain, Total RF Y/stress, ...
                points.append((float(row[1]), float(row[2])))
            except (IndexError, ValueError):
                continue

    if not points:
        raise ValueError(f"No numeric strain/stress rows found in {csv_path}")

    points.sort(key=lambda pair: pair[0])

    for strain, stress in points:
        if abs(strain - target_strain) < 1e-8:
            return stress

    for (strain_0, stress_0), (strain_1, stress_1) in zip(points, points[1:]):
        if strain_0 <= target_strain <= strain_1:
            fraction = (target_strain - strain_0) / (strain_1 - strain_0)
            return stress_0 + fraction * (stress_1 - stress_0)

    raise ValueError(
        f"Target strain {target_strain:g} is outside the strain range "
        f"{points[0][0]:g} to {points[-1][0]:g} in {csv_path}"
    )


def collect_data(results_dir: Path = RESULTS_DIR) -> list[tuple[float, float, str]]:
    """Collect (diameter, stress, case_name) tuples from all case folders."""
    rows: list[tuple[float, float, str]] = []

    for case_dir in sorted(results_dir.glob("bp_same_size_case_*")):
        if not case_dir.is_dir():
            continue

        case_name = case_dir.name
        xml_path = case_dir / f"{case_name}_resolved_input.xml"
        csv_path = case_dir / f"{case_name}.csv"

        if not xml_path.exists() or not csv_path.exists():
            print(f"Skipping {case_name}: missing XML or CSV")
            continue

        diameter = read_phase_mean_diameter_microns(xml_path)
        stress = read_stress_at_strain(csv_path)
        rows.append((diameter, stress, case_name))

    if not rows:
        raise ValueError(f"No valid case data found in {results_dir}")

    rows.sort(key=lambda row: row[0])
    return rows


def make_plot(rows: list[tuple[float, float, str]], output_fig: Path = OUTPUT_FIG) -> Path:
    """Create and save the diameter-vs-stress plot."""
    diameters = [row[0] for row in rows]
    stresses = [row[1] for row in rows]

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    ax.plot(
        diameters,
        stresses,
        marker="o",
        linewidth=2,
        markersize=6,
        label="Sensitivity cases",
    )

    ax.set_xlabel("Phase mean diameter (microns)", fontsize=LABEL_SIZE)
    ax.set_ylabel("Stress at 1% strain (MPa)", fontsize=LABEL_SIZE)
    ax.set_title(
        "Phase Mean Diameter vs Stress at 1% Strain",
        fontsize=TITLE_SIZE,
    )
    ax.tick_params(axis="both", labelsize=TICK_SIZE)
    ax.grid(True, alpha=0.35)
    ax.legend(fontsize=LEGEND_SIZE)

    fig.tight_layout()
    output_fig.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_fig, dpi=300)
    plt.close(fig)
    return output_fig


def main() -> None:
    rows = collect_data()
    output_fig = make_plot(rows)
    print(f"Saved figure: {output_fig}")
    print("Data points:")
    for diameter, stress, case_name in rows:
        print(f"  {case_name}: diameter={diameter:g} microns, stress={stress:.6g} MPa")


if __name__ == "__main__":
    main()
