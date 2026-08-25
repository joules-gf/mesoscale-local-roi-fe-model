"""Postprocess ROI field-report CSVs.

This module carries forward the useful pieces of the old crack postprocessing
scripts while renaming the concept from crack to ROI.  It expects files exported
by ``abaqus_roi_report_export.py`` such as:

    simulation_outputs/<case>/roi_reports/roi_right_01_frame50.csv

The functions are intentionally small and direct so the calculations are easy to
check and modify during thesis work.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd


STEP_TIME_RE = re.compile(r"Step Time\s*=\s*([0-9eE+.\-]+)")
ROI_REPORT_RE = re.compile(r"(?P<roi_name>.+)_frame(?P<frame_number>\d+)\.csv$")

MATERIAL_TO_PHASE = {
    "MATERIAL-0": "Phase 0",
    "MATERIAL-1": "Phase 1",
    "MATERIAL-2": "Phase 2",
    "MATERIAL-3": "Phase 3",
}
PHASE_NAMES = ["Phase 0", "Phase 1", "Phase 2", "Phase 3"]
ROI_SIF_SHAPE_FACTOR = 1.12


class RoiSummary(NamedTuple):
    roi_name: str
    frame_number: int
    step_time: float
    average_stress_mpa: float
    average_plastic_strain: float
    stress_intensity_factor: float
    phase_fractions: dict[str, float]


class RRatioResult(NamedTuple):
    local_r_ratios: dict[str, float]
    global_r_ratio: float


def parse_roi_report_name(path: str | Path) -> tuple[str, int]:
    """Return ``(roi_name, frame_number)`` from a report filename."""
    match = ROI_REPORT_RE.match(Path(path).name)
    if not match:
        raise ValueError(f"ROI report name must look like roi_name_frame50.csv: {path}")
    return match.group("roi_name"), int(match.group("frame_number"))


def extract_step_time(report_data: pd.DataFrame) -> float:
    """Extract the single Step Time encoded in the Abaqus 'Frame' column."""
    if "Frame" not in report_data.columns:
        raise ValueError("Expected a 'Frame' column in the ROI report CSV.")
    times = report_data["Frame"].astype(str).str.extract(STEP_TIME_RE)[0].dropna().astype(float).unique()
    if len(times) != 1:
        raise ValueError(f"Expected exactly one Step Time in ROI report, found {times}.")
    return float(times[0])


def phase_fractions(report_data: pd.DataFrame) -> dict[str, float]:
    """Return phase percentages based on Abaqus 'Material Name'."""
    fractions = {phase_name: 0.0 for phase_name in PHASE_NAMES}
    if "Material Name" not in report_data.columns:
        return fractions

    mapped = report_data["Material Name"].map(MATERIAL_TO_PHASE)
    counts = mapped.value_counts()
    total_count = float(counts.sum())
    if total_count == 0.0:
        return fractions

    for phase_name in PHASE_NAMES:
        fractions[phase_name] = 100.0 * float(counts.get(phase_name, 0)) / total_count
    return fractions


def summarize_roi_report(
    report_csv: str | Path,
    *,
    youngs_modulus_mpa: float = 71000.0,
    crack_length_m: float = 0.1e-3,
    stress_column: str = "         S-S22",
    strain_column: str = "         E-E22",
) -> RoiSummary:
    """Compute one ROI's stress, plastic strain, SIF, and phase fractions."""
    report_path = Path(report_csv)
    roi_name, frame_number = parse_roi_report_name(report_path)
    report_data = pd.read_csv(report_path)

    missing_columns = [column for column in (stress_column, strain_column) if column not in report_data.columns]
    if missing_columns:
        raise ValueError(f"ROI report is missing required columns: {missing_columns}")

    step_time = extract_step_time(report_data)
    stress = report_data[stress_column].astype(float)
    strain = report_data[strain_column].astype(float)

    average_stress = float(stress.mean())
    plastic_strain = np.maximum(strain - (stress / youngs_modulus_mpa), 0.0)
    plastic_strain[plastic_strain < 0.00025] = 0.0
    average_plastic_strain = float(plastic_strain.mean())
    stress_intensity_factor = ROI_SIF_SHAPE_FACTOR * average_stress * math.sqrt(math.pi * crack_length_m)

    return RoiSummary(
        roi_name=roi_name,
        frame_number=frame_number,
        step_time=step_time,
        average_stress_mpa=average_stress,
        average_plastic_strain=average_plastic_strain,
        stress_intensity_factor=stress_intensity_factor,
        phase_fractions=phase_fractions(report_data),
    )


def compute_r_ratios(
    high_stress_by_roi: dict[str, float],
    low_stress_by_roi: dict[str, float],
    *,
    global_high_stress: float,
    global_low_stress: float,
) -> RRatioResult:
    """Compute local and global R-ratios as sigma_min / sigma_max."""
    local_r_ratios: dict[str, float] = {}
    for roi_name in sorted(set(high_stress_by_roi).intersection(low_stress_by_roi)):
        sigma_high = max(high_stress_by_roi[roi_name], low_stress_by_roi[roi_name])
        sigma_low = min(high_stress_by_roi[roi_name], low_stress_by_roi[roi_name])
        local_r_ratios[roi_name] = float("nan") if np.isclose(sigma_high, 0.0) else sigma_low / sigma_high

    global_sigma_high = max(global_high_stress, global_low_stress)
    global_sigma_low = min(global_high_stress, global_low_stress)
    global_r_ratio = float("nan") if np.isclose(global_sigma_high, 0.0) else global_sigma_low / global_sigma_high
    return RRatioResult(local_r_ratios=local_r_ratios, global_r_ratio=global_r_ratio)


def summarize_roi_folder(roi_reports_folder: str | Path) -> pd.DataFrame:
    """Summarize all ``roi_*_frame*.csv`` files in a folder."""
    rows = []
    for report_csv in sorted(Path(roi_reports_folder).glob("roi_*_frame*.csv")):
        summary = summarize_roi_report(report_csv)
        row = summary._asdict()
        row.update(summary.phase_fractions)
        row.pop("phase_fractions")
        rows.append(row)
    return pd.DataFrame(rows)


def write_roi_summary_csv(roi_reports_folder: str | Path, output_csv: str | Path | None = None) -> Path:
    """Write a flat CSV summary for all ROI reports."""
    folder = Path(roi_reports_folder)
    if output_csv is None:
        output_csv = folder / "roi_summary.csv"
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summarize_roi_folder(folder).to_csv(output_path, index=False)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize exported Abaqus ROI field-report CSVs.")
    parser.add_argument("--roi-reports", required=True, help="Folder containing roi_*_frame*.csv reports")
    parser.add_argument("--output-csv", default=None, help="Output roi_summary.csv path")
    args = parser.parse_args()

    output_path = write_roi_summary_csv(args.roi_reports, args.output_csv)
    print(f"Wrote ROI summary: {output_path}")


if __name__ == "__main__":
    main()
