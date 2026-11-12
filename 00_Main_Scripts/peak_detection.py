"""Find local stress extrema and match actual ODB step-local frame times.

Global CSVs have one metadata row followed by the header. Never infer indices
from times unless the caller explicitly requests historical scaling.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import NamedTuple

import pandas as pd


class PeakTimes(NamedTuple):
    """Final local maximum/minimum times and optional actual frame indices."""
    raw_times: list[float | None]
    frame_numbers: list[int | None]


def global_csv_path(case_folder: str | Path) -> Path:
    """Return ``<case_folder>/<case_folder_name>.csv``."""
    folder = Path(case_folder).expanduser().resolve()
    return folder / f"{folder.name}.csv"


def _find_peak_indices(values, *, positive: bool) -> list[int]:
    """Return interior signed extrema; flat peaks use the middle (rounded down).

    Endpoints and plateaus touching an endpoint are not local extrema.
    """
    series = list(values)
    peak_indices: list[int] = []
    index = 1
    while index < len(series) - 1:
        end = index
        while end + 1 < len(series) and series[end + 1] == series[index]:
            end += 1
        if end == len(series) - 1:
            break
        previous_value, current_value, next_value = series[index - 1], series[index], series[end + 1]
        if positive and current_value > previous_value and current_value > next_value:
            peak_indices.append((index + end) // 2)
        if not positive and current_value < previous_value and current_value < next_value:
            peak_indices.append((index + end) // 2)
        index = end + 1
    return peak_indices


def _inventory_step(frame_inventory, step_name=None):
    """Load an inventory and select exactly one named ODB step."""
    if isinstance(frame_inventory, (str, Path)):
        with Path(frame_inventory).open(encoding="utf-8-sig") as stream:
            frame_inventory = json.load(stream)
    if not isinstance(frame_inventory, dict):
        raise ValueError("Frame inventory must be a mapping or JSON path")
    steps = frame_inventory.get("steps")
    if not isinstance(steps, list) or not steps or any(not isinstance(s, dict) for s in steps):
        raise ValueError("Frame inventory requires a nonempty steps list")
    names = [s.get("name") for s in steps]
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        raise ValueError("Inventory step names must be nonempty and unique")
    if step_name is None:
        if len(steps) != 1:
            raise ValueError("Multiple steps require an explicit step_name; times are step-local")
        return steps[0]
    selected = [s for s in steps if s["name"] == step_name]
    if len(selected) != 1:
        raise ValueError(f"Expected exactly one inventory step named {step_name!r}")
    return selected[0]


def match_frame_times(times, frame_inventory, *, step_name=None, tolerance=1e-6) -> list[int | None]:
    """Match times to unique actual frames[].index, never increment numbers.

    Accept a JSON path or {'steps': [{'name': ..., 'frames': [{'index', 'time',
    'increment', ...}, ...]}]}. Inventory must contain the complete selected step
    (indices 0..len(frames)-1). No extrapolation or scaling is performed. None is
    an absent peak; a non-None unmatched or ambiguous time raises ValueError.
    """
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Time tolerance must be nonnegative and finite")
    step = _inventory_step(frame_inventory, step_name)
    frames = step.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("Selected inventory step requires nonempty frames")
    checked = []
    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError("Frame must be a mapping")
        index, time = frame.get("index"), frame.get("time")
        if type(index) is not int or not 0 <= index < len(frames):
            raise ValueError("Frame index must be an integer within selected step bounds")
        if isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time) or time < 0:
            raise ValueError("Frame time must be nonnegative and finite")
        checked.append((index, float(time)))
    checked.sort()
    if len({index for index, _ in checked}) != len(checked):
        raise ValueError("Inventory frame indices must be unique")
    if any(b[1] <= a[1] for a, b in zip(checked, checked[1:])):
        raise ValueError("Inventory frame times must be unique and strictly increasing")
    result = []
    for time in times:
        if time is None:
            result.append(None)
            continue
        if not math.isfinite(time) or time < checked[0][1] - tolerance or time > checked[-1][1] + tolerance:
            raise ValueError(f"Peak time is nonfinite or outside selected step bounds: {time}")
        matches = [index for index, frame_time in checked if abs(frame_time - time) <= tolerance]
        if len(matches) != 1:
            raise ValueError(f"Expected one frame within {tolerance} of time {time}, found {matches}")
        result.append(matches[0])
    return result


def last_stress_peak_times(
    case_folder: str | Path | None = None, *, csv_path: str | Path | None = None,
    frame_inventory=None, step_name: str | None = None, tolerance: float = 1e-6,
    time_to_frame_scale: float | None = None,
) -> PeakTimes:
    """Return final local maximum/minimum times, irrespective of stress sign.

    Provide a case folder or explicit global CSV, not both. Without inventory,
    frame_numbers are [None, None]. Historical round(time*100) reproduction is
    available ONLY through explicit time_to_frame_scale=100, mutually exclusive
    with inventory matching. Multiple steps require step_name; the CSV must
    represent that same step (checked when a Step Name column is available).
    """
    if (case_folder is None) == (csv_path is None):
        raise ValueError("Provide exactly one of case_folder or csv_path")
    if frame_inventory is not None and time_to_frame_scale is not None:
        raise ValueError("Inventory matching and legacy scaling are mutually exclusive")
    if time_to_frame_scale is not None and (not math.isfinite(time_to_frame_scale) or time_to_frame_scale <= 0):
        raise ValueError("Legacy time_to_frame_scale must be positive and finite")
    path = global_csv_path(case_folder) if csv_path is None else Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Expected global CSV at: {path}")
    data = pd.read_csv(path, header=1)
    missing_columns = {"Step Time", "Total RF Y"}.difference(data.columns)
    if missing_columns:
        raise ValueError(f"Global CSV is missing required columns: {sorted(missing_columns)}")
    time = data["Step Time"].astype(float).tolist()
    stress = data["Total RF Y"].astype(float).tolist()
    if not time or not all(map(math.isfinite, time + stress)):
        raise ValueError("Global CSV requires nonempty finite time and stress data")
    if any(t < 0 for t in time) or any(b <= a for a, b in zip(time, time[1:])):
        raise ValueError("Global CSV times must be nonnegative and strictly increasing within one step")
    if frame_inventory is not None:
        selected = _inventory_step(frame_inventory, step_name)
        if "Step Name" in data.columns and set(data["Step Name"]) != {selected["name"]}:
            raise ValueError("Global CSV Step Name does not match selected inventory step")
    maxima = _find_peak_indices(stress, positive=True)
    minima = _find_peak_indices(stress, positive=False)
    raw_times = [float(time[indices[-1]]) if indices else None for indices in (maxima, minima)]
    if frame_inventory is not None:
        frame_numbers = match_frame_times(raw_times, frame_inventory, step_name=step_name, tolerance=tolerance)
    elif time_to_frame_scale is not None:
        frame_numbers = [int(round(t * time_to_frame_scale)) if t is not None else None for t in raw_times]
    else:
        frame_numbers = [None, None]
    return PeakTimes(raw_times=raw_times, frame_numbers=frame_numbers)


def main() -> None:
    """Write actual-frame peak selection JSON to stdout and optionally a file."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", help="Global force-displacement CSV (one metadata row)")
    source.add_argument("--case-folder", help="Case folder containing <case>.csv")
    parser.add_argument("--frame-inventory", required=True, help="Read-only ODB inventory JSON")
    parser.add_argument("--step-name", help="Required when inventory contains multiple steps")
    parser.add_argument("--tolerance", type=float, default=1e-6)
    parser.add_argument("--output-json", help="Optional selection JSON output path")
    args = parser.parse_args()
    result = last_stress_peak_times(args.case_folder, csv_path=args.csv,
                                   frame_inventory=args.frame_inventory, step_name=args.step_name,
                                   tolerance=args.tolerance)
    payload = {"step_name": _inventory_step(args.frame_inventory, args.step_name)["name"], **result._asdict()}
    text = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    if args.output_json:
        Path(args.output_json).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
