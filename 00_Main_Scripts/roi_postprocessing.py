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
import csv
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


def load_area_fractions(area_fractions_csv: str | Path, *, required_roi_names=()) -> dict[str, dict[str, float]]:
    """Read unique, finite phase percentages; never normalize malformed input.

    Optional area diagnostics, when supplied by roi_area_fractions.py, must show
    full coverage. These values replace phase count columns only, not mechanics.
    """
    fractions = {}
    with Path(area_fractions_csv).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        required = {"roi_name", *PHASE_NAMES}
        if not required.issubset(columns):
            raise ValueError("Area-fractions CSV requires roi_name and Phase 0..Phase 3 columns")
        for row in reader:
            name = row["roi_name"]
            if not name or name in fractions:
                raise ValueError(f"Missing or duplicate ROI name in area fractions: {name}")
            try:
                values = {phase: float(row[phase]) for phase in PHASE_NAMES}
                if any(not math.isfinite(value) or not 0 <= value <= 100.000001 for value in values.values()):
                    raise ValueError("Nonfinite or out-of-range phase percentage")
                if not math.isclose(math.fsum(values.values()), 100., abs_tol=1e-6):
                    raise ValueError("Area percentages must sum to 100")
                diagnostics = {"represented_area", "expected_area", "coverage_error"}
                if diagnostics.intersection(columns):
                    if not diagnostics.issubset(columns):
                        raise ValueError("Incomplete area-coverage diagnostics")
                    represented, expected, error = (float(row[key]) for key in ("represented_area", "expected_area", "coverage_error"))
                    if (not all(map(math.isfinite, (represented, expected, error))) or expected <= 0 or
                        not math.isclose(represented, expected, rel_tol=1e-8, abs_tol=1e-12) or
                        not math.isclose(error, represented - expected, abs_tol=1e-12)):
                        raise ValueError("Invalid ROI area coverage")
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid area fractions for {name}: {exc}") from exc
            fractions[name] = values
    missing = set(required_roi_names) - fractions.keys()
    if missing:
        raise ValueError(f"Area-fractions CSV is missing ROIs: {sorted(missing)}")
    return fractions


def summarize_roi_report(
    report_csv: str | Path,
    *,
    youngs_modulus_mpa: float = 71000.0,
    crack_length_m: float = 0.1e-3,
    stress_column: str = "         S-S22",
    strain_column: str = "         E-E22",
    area_fractions_csv: str | Path | None = None,
    plastic_strain_source: str = "legacy",
) -> RoiSummary:
    """Compute ROI mechanics with explicit strain provenance.

    ``pe22`` averages signed Abaqus PE22 rows, including zero, without E22 or
    modulus dependence and never falls back to subtraction. The API default
    ``legacy`` preserves E22-S22/E, clipping and thresholding for reproduction.
    """
    if plastic_strain_source not in ("pe22", "legacy"):
        raise ValueError("plastic_strain_source must be 'pe22' or 'legacy'")
    if plastic_strain_source == "legacy" and (not math.isfinite(youngs_modulus_mpa) or youngs_modulus_mpa <= 0):
        raise ValueError("Young's modulus must be positive and finite (MPa)")
    report_path = Path(report_csv)
    roi_name, frame_number = parse_roi_report_name(report_path)

    selected_strain_column = strain_column
    if plastic_strain_source == "pe22":
        # Inspect the original header before pandas can mangle duplicate names.
        # Abaqus pads by field-name width; PE-PE22 need not have S-S22's padding.
        with report_path.open(newline="", encoding="utf-8-sig") as stream:
            headers = next(csv.reader(stream), [])
        normalized = [column.strip() for column in headers]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate normalized column names in direct PE22 report")
        selected_strain_column = next((column for column in headers if column.strip() == "PE-PE22"), "PE-PE22")
    report_data = pd.read_csv(report_path)
    missing_columns = [column for column in (stress_column, selected_strain_column) if column not in report_data.columns]
    if missing_columns:
        raise ValueError(f"ROI report is missing required columns: {missing_columns}")

    step_time = extract_step_time(report_data)
    stress = report_data[stress_column].astype(float)
    strain = report_data[selected_strain_column].astype(float)

    if plastic_strain_source == "pe22" and (
        report_data.empty or not math.isfinite(step_time) or
        not np.isfinite(stress).all() or not np.isfinite(strain).all()
    ):
        raise ValueError("Direct PE22 reports require nonempty, finite S22 and PE22 rows and Step Time")

    average_stress = float(stress.mean())
    if plastic_strain_source == "pe22":
        plastic_strain = strain
    else:
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
        phase_fractions=(phase_fractions(report_data) if area_fractions_csv is None else
                         load_area_fractions(area_fractions_csv, required_roi_names=[roi_name])[roi_name]),
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


def summarize_roi_folder(
    roi_reports_folder: str | Path,
    *,
    area_fractions_csv: str | Path | None = None,
    youngs_modulus_mpa: float = 71000.0,
    plastic_strain_source: str = "legacy",
) -> pd.DataFrame:
    """Summarize all ``roi_*_frame*.csv`` files in a folder."""
    if plastic_strain_source not in ("pe22", "legacy"):
        raise ValueError("plastic_strain_source must be 'pe22' or 'legacy'")
    if plastic_strain_source == "legacy" and (not math.isfinite(youngs_modulus_mpa) or youngs_modulus_mpa <= 0):
        raise ValueError("Young's modulus must be positive and finite (MPa)")
    rows = []
    for report_csv in sorted(Path(roi_reports_folder).glob("roi_*_frame*.csv")):
        summary = summarize_roi_report(report_csv, youngs_modulus_mpa=youngs_modulus_mpa,
                                       plastic_strain_source=plastic_strain_source)
        row = summary._asdict()
        row.update(summary.phase_fractions)
        row.pop("phase_fractions")
        if plastic_strain_source == "pe22":
            row["plastic_strain_source"] = "PE22"
        rows.append(row)
    result = pd.DataFrame(rows)
    if area_fractions_csv is not None:
        overrides = load_area_fractions(area_fractions_csv, required_roi_names=[row["roi_name"] for row in rows])
        for phase in PHASE_NAMES:
            result[phase] = [overrides[row["roi_name"]][phase] for row in rows]
    return result


def write_roi_summary_csv(
    roi_reports_folder: str | Path,
    output_csv: str | Path | None = None,
    *,
    area_fractions_csv: str | Path | None = None,
    youngs_modulus_mpa: float = 71000.0,
    plastic_strain_source: str = "legacy",
) -> Path:
    """Write a flat CSV summary for all ROI reports."""
    folder = Path(roi_reports_folder)
    if output_csv is None:
        output_csv = folder / "roi_summary.csv"
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summarize_roi_folder(folder, area_fractions_csv=area_fractions_csv,
                         youngs_modulus_mpa=youngs_modulus_mpa,
                         plastic_strain_source=plastic_strain_source).to_csv(output_path, index=False)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize exported Abaqus ROI field-report CSVs.")
    parser.add_argument("--roi-reports", required=True, help="Folder containing roi_*_frame*.csv reports")
    parser.add_argument("--output-csv", default=None, help="Output roi_summary.csv path")
    parser.add_argument("--area-fractions-csv", default=None, help="Optional exact ROI phase-area CSV; replaces phase count percentages only")
    parser.add_argument("--youngs-modulus-mpa", type=float, default=71000.0, help="Young's modulus for legacy elastic subtraction only (MPa)")
    parser.add_argument("--plastic-strain-source", choices=("pe22", "legacy"), default="pe22",
                        help="Signed Abaqus PE22 mean (default), or explicit legacy E22-S22/E reproduction")
    args = parser.parse_args()

    output_path = write_roi_summary_csv(args.roi_reports, args.output_csv,
                                       area_fractions_csv=args.area_fractions_csv,
                                       youngs_modulus_mpa=args.youngs_modulus_mpa,
                                       plastic_strain_source=args.plastic_strain_source)
    print(f"Wrote ROI summary: {output_path}")


if __name__ == "__main__":
    main()
