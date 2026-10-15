"""Run midpoint diameter mapping cases near existing cases 8 and 16.

Creates and runs four fresh same-mean-diameter XMLs:
- 70 microns: midpoint between cases 07 and 08
- 80 microns: midpoint between cases 08 and 09
- 150 microns: midpoint between cases 15 and 16
- 160 microns: midpoint between cases 16 and 17

The runs are fresh: restart is disabled in the generated XMLs and matching
output directories are removed before execution. After all cases finish, this
writes a summary CSV and overlays the new points on the existing phase mean
diameter vs. stress at 1% strain plot.
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
BASE_INPUT_DIR = PROJECT_ROOT / "simulation_inputs" / "Uniform Distribution" / "sensitivity-study-AA7075-T651" / "bp_same_mean_diameter"
MIDPOINT_INPUT_DIR = BASE_INPUT_DIR / "professor-requested-midpoint-mapping"
OUTPUT_ROOT = PROJECT_ROOT / "simulation_outputs"
LOG_DIR = OUTPUT_ROOT / "professor_requested_midpoint_mapping_70_80_150_160"
SUMMARY_CSV = LOG_DIR / "midpoint_mapping_70_80_150_160_summary.csv"
LIVE_LOG = LOG_DIR / "live_log.txt"
REFERENCE_RESULTS_DIR = (
    PROJECT_ROOT
    / "reference_outputs"
    / "Uniform Distribution"
    / "Sensitivity Study"
    / "mean-diameter-equal-4all-phases"
)
OVERLAY_FIG = REFERENCE_RESULTS_DIR / "phase_mean_diameter_vs_stress_at_1pct_strain_with_midpoint_mapping.png"
TARGET_STRAIN = 0.01
MM_TO_MICRONS = 1000.0

# Larger/easier cases first, then finer/slower cases.
CASES = [
    {
        "case": "bp_same_size_case_16_17_mid_160um",
        "template": "bp_same_size_case_16.xml",
        "diameter_mm": 0.160,
        "note": "midpoint between cases 16 and 17",
    },
    {
        "case": "bp_same_size_case_15_16_mid_150um",
        "template": "bp_same_size_case_15.xml",
        "diameter_mm": 0.150,
        "note": "midpoint between cases 15 and 16",
    },
    {
        "case": "bp_same_size_case_08_09_mid_080um",
        "template": "bp_same_size_case_08.xml",
        "diameter_mm": 0.080,
        "note": "midpoint between cases 8 and 9",
    },
    {
        "case": "bp_same_size_case_07_08_mid_070um",
        "template": "bp_same_size_case_07.xml",
        "diameter_mm": 0.070,
        "note": "midpoint between cases 7 and 8",
    },
]

FIG_SIZE = (8, 6)
LABEL_SIZE = 16
TITLE_SIZE = 18
LEGEND_SIZE = 16
TICK_SIZE = 16

sys.path.insert(0, str(MAIN_SCRIPTS))
from full_simulation_runner import run_full_simulation  # noqa: E402


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log(message: str) -> None:
    print(message, flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LIVE_LOG.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def set_text(parent: ET.Element, path: str, value: str) -> None:
    elem = parent.find(path)
    if elem is None:
        raise ValueError(f"Missing XML element: {path}")
    elem.text = f" {value} "


def prepare_input(case: str, template: str, diameter_mm: float) -> Path:
    source = BASE_INPUT_DIR / template
    destination = MIDPOINT_INPUT_DIR / f"{case}.xml"
    if not source.exists():
        raise FileNotFoundError(source)
    MIDPOINT_INPUT_DIR.mkdir(parents=True, exist_ok=True)

    tree = ET.parse(source)
    root = tree.getroot()
    for material in root.findall("material"):
        size = material.find("size")
        if size is None:
            raise ValueError(f"Missing material/size in {source}")
        loc = size.find("loc")
        if loc is None:
            raise ValueError(f"Missing material/size/loc in {source}")
        loc.text = f" {diameter_mm:.3f} "
    set_text(root, "settings/restart", "False")
    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass
    tree.write(destination, encoding="unicode")
    return destination


def read_phase_mean_diameter_microns(xml_path: Path) -> float:
    root = ET.parse(xml_path).getroot()
    values = []
    for material in root.findall("material"):
        loc = material.findtext("size/loc")
        if loc is not None:
            values.append(float(loc.strip()))
    if not values:
        raise ValueError(f"No material/size/loc values found in {xml_path}")
    return values[0] * MM_TO_MICRONS


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
        raise ValueError(f"No numeric strain/stress rows found in {csv_path}")
    points.sort(key=lambda item: item[0])
    for strain, stress in points:
        if abs(strain - target_strain) < 1e-8:
            return stress
    for (strain_0, stress_0), (strain_1, stress_1) in zip(points, points[1:]):
        if strain_0 <= target_strain <= strain_1:
            fraction = (target_strain - strain_0) / (strain_1 - strain_0)
            return stress_0 + fraction * (stress_1 - stress_0)
    raise ValueError(f"Target strain {target_strain:g} outside CSV range: {csv_path}")


def collect_original_rows() -> list[tuple[float, float, str]]:
    rows = []
    for case_dir in sorted(REFERENCE_RESULTS_DIR.glob("bp_same_size_case_*")):
        case_name = case_dir.name
        xml_path = case_dir / f"{case_name}_resolved_input.xml"
        csv_path = case_dir / f"{case_name}.csv"
        if xml_path.exists() and csv_path.exists():
            rows.append((read_phase_mean_diameter_microns(xml_path), read_stress_at_strain(csv_path), case_name))
    rows.sort(key=lambda row: row[0])
    return rows


def run_case(config: dict[str, object]) -> dict[str, str]:
    case = str(config["case"])
    template = str(config["template"])
    diameter_mm = float(config["diameter_mm"])
    note = str(config["note"])
    input_file = prepare_input(case, template, diameter_mm)
    output_dir = OUTPUT_ROOT / case

    if output_dir.exists():
        log(f"Removing existing output folder for fresh run: {output_dir}")
        shutil.rmtree(output_dir)

    start_iso = now_iso()
    start = time.time()
    log("=" * 80)
    log(f"START {case} | {diameter_mm:.3f} mm = {diameter_mm * MM_TO_MICRONS:.0f} microns | {note} | {start_iso}")
    log(f"Input XML: {input_file}")

    status = "unknown"
    notes = ""
    try:
        run_full_simulation(
            input_files_folder=str(MIDPOINT_INPUT_DIR),
            input_file=str(input_file),
            run_abaqus=True,
            run_postprocessing=True,
        )
        status = "finished"
        notes = "run_full_simulation returned normally"
    except Exception as exc:  # noqa: BLE001 - keep batch moving if one case fails
        status = "failed"
        notes = f"{type(exc).__name__}: {exc}"
        log(f"ERROR {case}: {notes}")
        raise
    finally:
        end_iso = now_iso()
        elapsed = time.time() - start
        log(f"END {case} | status={status} | elapsed={elapsed / 3600.0:.4f} h | {end_iso}")

    resolved_xml = output_dir / f"{case}_resolved_input.xml"
    result_csv = output_dir / f"{case}.csv"
    diameter_microns = read_phase_mean_diameter_microns(resolved_xml)
    stress = read_stress_at_strain(result_csv)
    log(f"RESULT {case}: diameter={diameter_microns:.6g} microns | stress@1%={stress:.12g} MPa")

    return {
        "case": case,
        "diameter_mm": f"{diameter_mm:.6g}",
        "diameter_microns": f"{diameter_microns:.6g}",
        "stress_at_1pct_MPa": f"{stress:.12g}",
        "start_time": start_iso,
        "end_time": end_iso,
        "elapsed_seconds": f"{elapsed:.1f}",
        "elapsed_hours": f"{elapsed / 3600.0:.4f}",
        "status": status,
        "notes": notes,
        "output_dir": str(output_dir),
    }


def write_summary(rows: list[dict[str, str]]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case",
        "diameter_mm",
        "diameter_microns",
        "stress_at_1pct_MPa",
        "start_time",
        "end_time",
        "elapsed_seconds",
        "elapsed_hours",
        "status",
        "notes",
        "output_dir",
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_overlay(new_rows: list[dict[str, str]]) -> Path:
    original = collect_original_rows()
    x_orig = [row[0] for row in original]
    y_orig = [row[1] for row in original]
    x_new = [float(row["diameter_microns"]) for row in new_rows]
    y_new = [float(row["stress_at_1pct_MPa"]) for row in new_rows]

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    ax.plot(x_orig, y_orig, marker="o", linewidth=2, markersize=6, label="Original sensitivity cases")
    ax.scatter(
        x_new,
        y_new,
        marker="D",
        s=110,
        color="tab:orange",
        edgecolor="black",
        linewidth=0.8,
        label="Midpoint mapping cases",
        zorder=5,
    )
    for row in new_rows:
        ax.annotate(
            f"{float(row['diameter_microns']):.0f}",
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

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log("=" * 80)
    log(f"Midpoint mapping run started: {now_iso()}")
    log(f"Project root: {PROJECT_ROOT}")
    log(f"Input dir:    {MIDPOINT_INPUT_DIR}")
    log(f"Summary CSV:  {SUMMARY_CSV}")
    log(f"Overlay fig:  {OVERLAY_FIG}")

    rows: list[dict[str, str]] = []
    for config in CASES:
        rows.append(run_case(config))
        write_summary(rows)

    overlay = make_overlay(rows)
    write_summary(rows)
    log(f"All midpoint cases finished: {now_iso()}")
    log(f"Summary CSV: {SUMMARY_CSV}")
    log(f"Overlay figure: {overlay}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
