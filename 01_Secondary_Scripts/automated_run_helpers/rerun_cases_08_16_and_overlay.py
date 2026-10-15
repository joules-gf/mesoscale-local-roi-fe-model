"""Rerun same-mean-diameter cases 08 and 16 from fresh input copies.

This helper creates fresh XML input names for the professor-requested reruns,
runs the full MicroStructPy/Abaqus/postprocessing pipeline for each case, and
then overlays the rerun stress-at-1%-strain points on the existing phase mean
diameter sensitivity plot.
"""

from __future__ import annotations

import csv
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SCRIPTS = PROJECT_ROOT / "00_Main_Scripts"
ORIGINAL_INPUT_DIR = (
    PROJECT_ROOT
    / "simulation_inputs"
    / "Uniform Distribution"
    / "sensitivity-study-AA7075-T651"
    / "bp_same_mean_diameter"
)
RERUN_INPUT_DIR = ORIGINAL_INPUT_DIR / "professor-requested-reruns"
REFERENCE_RESULTS_DIR = (
    PROJECT_ROOT
    / "reference_outputs"
    / "Uniform Distribution"
    / "Sensitivity Study"
    / "mean-diameter-equal-4all-phases"
)
OUTPUT_ROOT = PROJECT_ROOT / "simulation_outputs"
RERUN_LOG_DIR = OUTPUT_ROOT / "professor_requested_reruns_case_08_16"
RERUN_SUMMARY_CSV = RERUN_LOG_DIR / "rerun_case_08_16_summary.csv"
OVERLAY_FIG = REFERENCE_RESULTS_DIR / "phase_mean_diameter_vs_stress_at_1pct_strain_with_reruns.png"
TARGET_STRAIN = 0.01
MM_TO_MICRONS = 1000.0

FIG_SIZE = (8, 6)
LABEL_SIZE = 16
TITLE_SIZE = 18
LEGEND_SIZE = 16
TICK_SIZE = 16

CASES = [
    ("bp_same_size_case_08", "bp_same_size_case_08_rerun_prof_check"),
    ("bp_same_size_case_16", "bp_same_size_case_16_rerun_prof_check"),
]

sys.path.insert(0, str(MAIN_SCRIPTS))
from full_simulation_runner import run_full_simulation  # noqa: E402


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def set_text(parent: ET.Element, path: str, value: str) -> None:
    elem = parent.find(path)
    if elem is None:
        raise ValueError(f"Missing XML element: {path}")
    elem.text = f" {value} "


def prepare_fresh_input(original_case: str, rerun_case: str) -> Path:
    """Copy original XML to a fresh stem and disable restart reuse."""
    RERUN_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = ORIGINAL_INPUT_DIR / f"{original_case}.xml"
    destination = RERUN_INPUT_DIR / f"{rerun_case}.xml"
    if not source.exists():
        raise FileNotFoundError(source)

    tree = ET.parse(source)
    root = tree.getroot()
    set_text(root, "settings/restart", "False")
    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass
    tree.write(destination, encoding="unicode")
    return destination


def read_phase_mean_diameter_microns(xml_path: Path) -> float:
    root = ET.parse(xml_path).getroot()
    diameters_mm = []
    for material in root.findall("material"):
        loc = material.findtext("size/loc")
        if loc is not None:
            diameters_mm.append(float(loc.strip()))
    if not diameters_mm:
        raise ValueError(f"No material/size/loc values found in {xml_path}")
    return diameters_mm[0] * MM_TO_MICRONS


def read_stress_at_strain(csv_path: Path, target_strain: float = TARGET_STRAIN) -> float:
    points: list[tuple[float, float]] = []
    with csv_path.open(newline="") as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            try:
                points.append((float(row[1]), float(row[2])))
            except (IndexError, ValueError):
                continue
    if not points:
        raise ValueError(f"No numeric rows found in {csv_path}")
    points.sort(key=lambda pair: pair[0])
    for strain, stress in points:
        if abs(strain - target_strain) < 1e-8:
            return stress
    for (strain_0, stress_0), (strain_1, stress_1) in zip(points, points[1:]):
        if strain_0 <= target_strain <= strain_1:
            fraction = (target_strain - strain_0) / (strain_1 - strain_0)
            return stress_0 + fraction * (stress_1 - stress_0)
    raise ValueError(f"Target strain {target_strain:g} outside {csv_path}")


def collect_original_rows() -> list[tuple[float, float, str]]:
    rows = []
    for case_dir in sorted(REFERENCE_RESULTS_DIR.glob("bp_same_size_case_*")):
        case_name = case_dir.name
        xml_path = case_dir / f"{case_name}_resolved_input.xml"
        csv_path = case_dir / f"{case_name}.csv"
        if xml_path.exists() and csv_path.exists():
            rows.append(
                (
                    read_phase_mean_diameter_microns(xml_path),
                    read_stress_at_strain(csv_path),
                    case_name,
                )
            )
    rows.sort(key=lambda row: row[0])
    return rows


def run_case(original_case: str, rerun_case: str) -> dict[str, str]:
    input_file = prepare_fresh_input(original_case, rerun_case)
    output_dir = OUTPUT_ROOT / rerun_case
    if output_dir.exists():
        shutil.rmtree(output_dir)

    start = time.time()
    start_iso = now_iso()
    print(f"===== START {rerun_case} from {original_case}: {start_iso} =====", flush=True)
    run_full_simulation(
        input_files_folder=str(RERUN_INPUT_DIR),
        input_file=str(input_file),
        run_abaqus=True,
        run_postprocessing=True,
    )
    end_iso = now_iso()
    elapsed = time.time() - start

    resolved_xml = output_dir / f"{rerun_case}_resolved_input.xml"
    result_csv = output_dir / f"{rerun_case}.csv"
    diameter = read_phase_mean_diameter_microns(resolved_xml)
    stress = read_stress_at_strain(result_csv)
    row = {
        "original_case": original_case,
        "rerun_case": rerun_case,
        "diameter_microns": f"{diameter:.6g}",
        "stress_at_1pct_MPa": f"{stress:.12g}",
        "start_time": start_iso,
        "end_time": end_iso,
        "elapsed_seconds": f"{elapsed:.1f}",
        "elapsed_hours": f"{elapsed / 3600.0:.4f}",
        "output_dir": str(output_dir),
    }
    print(
        f"===== END {rerun_case}: stress@1%={stress:.6g} MPa, "
        f"elapsed={elapsed/3600.0:.4f} h =====",
        flush=True,
    )
    return row


def write_summary(rows: list[dict[str, str]]) -> None:
    RERUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "original_case",
        "rerun_case",
        "diameter_microns",
        "stress_at_1pct_MPa",
        "start_time",
        "end_time",
        "elapsed_seconds",
        "elapsed_hours",
        "output_dir",
    ]
    with RERUN_SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_overlay(rerun_rows: list[dict[str, str]]) -> Path:
    original = collect_original_rows()
    x_orig = [row[0] for row in original]
    y_orig = [row[1] for row in original]
    x_rerun = [float(row["diameter_microns"]) for row in rerun_rows]
    y_rerun = [float(row["stress_at_1pct_MPa"]) for row in rerun_rows]

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    ax.plot(
        x_orig,
        y_orig,
        marker="o",
        linewidth=2,
        markersize=6,
        label="Original sensitivity cases",
    )
    ax.scatter(
        x_rerun,
        y_rerun,
        marker="X",
        s=160,
        color="tab:red",
        edgecolor="black",
        linewidth=0.8,
        label="Fresh reruns: cases 8 and 16",
        zorder=5,
    )
    for row in rerun_rows:
        ax.annotate(
            row["original_case"].replace("bp_same_size_", ""),
            (float(row["diameter_microns"]), float(row["stress_at_1pct_MPa"])),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=10,
        )

    ax.set_xlabel("Phase mean diameter (microns)", fontsize=LABEL_SIZE)
    ax.set_ylabel("Stress at 1% strain (MPa)", fontsize=LABEL_SIZE)
    ax.set_title("Phase Mean Diameter vs Stress at 1% Strain", fontsize=TITLE_SIZE)
    ax.tick_params(axis="both", labelsize=TICK_SIZE)
    ax.grid(True, alpha=0.35)
    ax.legend(fontsize=LEGEND_SIZE)
    fig.tight_layout()
    fig.savefig(OVERLAY_FIG, dpi=300)
    plt.close(fig)
    return OVERLAY_FIG


def main() -> int:
    os.chdir(PROJECT_ROOT)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MICROSTRUCTURE_NONINTERACTIVE", "1")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    rows = []
    for original_case, rerun_case in CASES:
        rows.append(run_case(original_case, rerun_case))
        write_summary(rows)

    overlay = make_overlay(rows)
    print(f"Summary CSV: {RERUN_SUMMARY_CSV}", flush=True)
    print(f"Overlay figure: {overlay}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
