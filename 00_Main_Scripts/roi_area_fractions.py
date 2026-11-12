"""Undeformed phase AREA fractions in exact edge semicircles (stdlib only).

Read the FINAL, self-contained Abaqus deck, not centroid-selected field reports
or a preliminary mesh. Supported geometry is one planar CPS3 part with one
untransformed instance (or an orphan mesh). Unsupported scope/geometry fails
closed. Circle boundaries are analytic, not polygonal approximations.

Repository-root Windows example::

    .venv\\Scripts\\python.exe 00_Main_Scripts/roi_area_fractions.py \
        --input-deck simulation_outputs/case/abaqus_files/case.inp \
        --output-csv simulation_outputs/case/roi_reports/roi_area_fractions.csv

The default ROIs reuse the exporter's names/radius/count/spacing and inferred
bounds: 18 semicircles on a unit square, including [-.5,.5]^2. Only phase
fractions change; this module never opens an ODB or changes field averaging.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import NamedTuple

# Explicit loading also supports importlib-based script tests without sys.path edits.
import importlib.util
_spec = importlib.util.spec_from_file_location("_roi_area_export_geometry", Path(__file__).with_name("abaqus_roi_report_export.py"))
assert _spec is not None and _spec.loader is not None
_export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_export)

PHASE_NAMES = [f"Phase {i}" for i in range(4)]
MATERIAL_TO_PHASE = {f"MATERIAL-{i}": phase for i, phase in enumerate(PHASE_NAMES)}
COVERAGE_REL_TOL = 1e-8
COVERAGE_ABS_TOL = 1e-12


class Mesh(NamedTuple):
    triangles: dict
    phases: dict
    bounds: tuple
    source_path: str
    source_sha256: str


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def _signed_area(poly):
    if len(poly) < 3:
        return 0.0
    origin = poly[0]
    return math.fsum(_cross(_sub(poly[i], origin), _sub(poly[i + 1], origin))
                     for i in range(1, len(poly) - 1)) / 2


def _clip(poly, signed_distance):
    """Sutherland-Hodgman clipping against one closed linear half-plane."""
    out = []
    if not poly:
        return out
    previous = poly[-1]
    dp = signed_distance(previous)
    for current in poly:
        dc = signed_distance(current)
        if (dp >= 0) != (dc >= 0):
            t = dp / (dp - dc)
            out.append((previous[0] + t * (current[0] - previous[0]),
                        previous[1] + t * (current[1] - previous[1])))
        if dc >= 0:
            out.append(current)
        previous, dp = current, dc
    return out


def _disk_edge_area(a, b, radius):
    """Signed line/arc integral contribution, splitting at exact circle roots."""
    d = _sub(b, a)
    aa = d[0]**2 + d[1]**2
    if aa == 0:
        return 0.0
    bb = 2 * (a[0] * d[0] + a[1] * d[1])
    cc = a[0]**2 + a[1]**2 - radius**2
    discriminant = bb**2 - 4 * aa * cc
    cuts = [0.0, 1.0]
    if discriminant >= 0:
        root = math.sqrt(discriminant)
        cuts.extend(t for t in ((-bb - root) / (2 * aa), (-bb + root) / (2 * aa)) if 0 < t < 1)
    cuts.sort()
    pieces = []
    for start, end in zip(cuts, cuts[1:]):
        p = (a[0] + start * d[0], a[1] + start * d[1])
        q = (a[0] + end * d[0], a[1] + end * d[1])
        mid = (a[0] + (start + end) * .5 * d[0], a[1] + (start + end) * .5 * d[1])
        if mid[0]**2 + mid[1]**2 <= radius**2:
            pieces.append(_cross(p, q) / 2)
        else:
            pieces.append(radius**2 * math.atan2(_cross(p, q), p[0]*q[0] + p[1]*q[1]) / 2)
    return math.fsum(pieces)


def triangle_semicircle_area(triangle, roi):
    """Area of a triangle intersected with an inward-facing exact semicircle.

    Clip to the diameter half-plane, then integrate straight chords inside the
    disk and signed circular arcs outside. Vertex winding is immaterial.
    """
    if roi.side not in ("left", "right") or not math.isfinite(roi.radius) or roi.radius <= 0:
        raise ValueError("ROI requires left/right side and positive finite radius")
    poly = [_sub(p, roi.center) for p in triangle]
    sign = 1 if roi.side == "left" else -1
    poly = _clip(poly, lambda p: sign * p[0])
    if len(poly) < 3 or _signed_area(poly) == 0:
        return 0.0
    return abs(math.fsum(_disk_edge_area(a, b, roi.radius)
                         for a, b in zip(poly, poly[1:] + poly[:1])))


def _validate_nonoverlap(triangles):
    """Sweep triangle bounding boxes; shared edges/vertices have zero area."""
    boxes = []
    for label, tri in triangles.items():
        xs, ys = zip(*tri)
        boxes.append((min(xs), max(xs), min(ys), max(ys), label))
    active = []
    for box in sorted(boxes):
        x0, x1, y0, y1, label = box
        active = [other for other in active if other[1] > x0]
        tri = triangles[label]
        for other in active:
            if other[3] <= y0 or y1 <= other[2]:
                continue
            other_tri = triangles[other[4]]
            poly = list(tri)
            for a, b in zip(other_tri, other_tri[1:] + other_tri[:1]):
                poly = _clip(poly, lambda p, a=a, b=b: _cross(_sub(b, a), _sub(p, a)))
                if len(poly) < 3:
                    break
            tolerance = max(1e-20, min(_signed_area(tri), _signed_area(other_tri)) * 1e-9)
            if abs(_signed_area(poly)) > tolerance:
                raise ValueError(f"Overlapping mesh elements {label} and {other[4]}")
        active.append(box)


def read_input_deck(input_deck):
    """Parse final *Node/*Element/*Elset/*Solid Section material ownership.

    Sets may use generate, element-block elset membership, or nested set names.
    All CPS3 elements must have exactly one declared Material-0..3 section.
    Includes, multiple parts/instances, transforms, nonplanarity and ambiguous
    assignments are rejected rather than silently interpreted in the wrong frame.
    """
    path = Path(input_deck).resolve()
    raw = path.read_bytes()
    nodes, elements, sets, sections, materials = {}, {}, {}, [], set()
    keyword, options = "", {}
    in_assembly = False
    part_names, instances = [], []
    for number, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("**"):
            continue
        if line.startswith("*"):
            tokens = [token.strip().upper() for token in line.split(",")]
            keyword = tokens[0][1:]
            options = {}
            for token in tokens[1:]:
                if token:
                    key, _, value = token.partition("=")
                    options[key] = value
            options = {key.strip(): value.strip() for key, value in options.items()}
            if keyword in ("INCLUDE", "SYSTEM", "NGEN", "NFILL", "ELGEN", "ELCOPY", "NCOPY", "IMPORT", "TRANSFORM"):
                raise ValueError(f"Unsupported geometry keyword *{keyword} at line {number}")
            if keyword == "PART":
                part_names.append(options.get("NAME"))
                if len(part_names) > 1:
                    raise ValueError("Multiple parts are unsupported")
            elif keyword == "ASSEMBLY":
                in_assembly = True
            elif keyword == "END ASSEMBLY":
                in_assembly = False
            elif keyword == "INSTANCE":
                instances.append(options.get("PART"))
                if len(instances) > 1:
                    raise ValueError("Multiple instances are unsupported")
            elif keyword == "MATERIAL":
                materials.add(options["NAME"])
            elif keyword == "ELEMENT":
                if in_assembly or options.get("TYPE") != "CPS3":
                    raise ValueError("Only part-level/orphan CPS3 elements are supported")
            elif keyword == "SOLID SECTION":
                if in_assembly:
                    raise ValueError("Assembly-scoped solid section is unsupported")
                sections.append((options.get("ELSET"), options.get("MATERIAL")))
            continue
        fields = [value.strip().upper() for value in line.split(",") if value.strip()]
        try:
            if keyword == "INSTANCE":
                raise ValueError("Instance translation/rotation is unsupported")
            if keyword == "NODE" and not in_assembly:
                label = int(fields[0])
                xyz = tuple(float(value) for value in fields[1:])
                if label in nodes or len(xyz) not in (2, 3) or not all(map(math.isfinite, xyz)):
                    raise ValueError("Duplicate/invalid node")
                if len(xyz) == 3 and abs(xyz[2]) > 1e-12:
                    raise ValueError("Nonplanar nodes: expected z=0")
                nodes[label] = xyz[:2]
            elif keyword == "ELEMENT":
                label, *connectivity = map(int, fields)
                if label in elements or len(connectivity) != 3:
                    raise ValueError("Duplicate/invalid CPS3 element")
                elements[label] = tuple(connectivity)
                if "ELSET" in options:
                    sets.setdefault(options["ELSET"], []).append(label)
            elif keyword == "ELSET" and not in_assembly:
                if "INSTANCE" in options:
                    raise ValueError("Instance-scoped elset is unsupported")
                members = sets.setdefault(options["ELSET"], [])
                if "GENERATE" in options:
                    if len(fields) != 3:
                        raise ValueError("Elset generate requires start,end,increment")
                    start, end, step = map(int, fields)
                    if step <= 0 or end < start or (end - start) % step:
                        raise ValueError("Invalid generated elset range")
                    members.extend(range(start, end + 1, step))
                else:
                    members.extend(int(value) if value.isdigit() else value for value in fields)
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Invalid deck at line {number}: {exc}") from exc
    if part_names and (instances != part_names):
        raise ValueError("Expected exactly one untransformed instance of the mesh part")
    if not elements or not nodes:
        raise ValueError("No CPS3 mesh found")

    def resolve_set(name, stack=()):
        if name not in sets or name in stack:
            raise ValueError(f"Missing or cyclic elset: {name}")
        result = set()
        for member in sets[name]:
            if isinstance(member, int):
                if member not in elements:
                    raise ValueError(f"Elset {name} references missing element {member}")
                result.add(member)
            else:
                result.update(resolve_set(member, stack + (name,)))
        return result

    phases = {}
    # Validate every part-level set, not just the section sets.
    for name in sets:
        resolve_set(name)
    for name, material in sections:
        if material not in MATERIAL_TO_PHASE or material not in materials:
            raise ValueError(f"Unknown or undeclared section material {material}")
        for label in resolve_set(name):
            if label in phases:
                raise ValueError(f"Overlapping/ambiguous material assignment for element {label}")
            phases[label] = MATERIAL_TO_PHASE[material]
    missing = set(elements) - set(phases)
    if missing:
        raise ValueError(f"Missing solid-section material mapping for {len(missing)} elements; first: {min(missing)}")
    triangles = {}
    for label, connectivity in elements.items():
        try:
            triangle = tuple(nodes[node] for node in connectivity)
        except KeyError as exc:
            raise ValueError(f"Element {label} references missing node {exc}") from exc
        area = _signed_area(triangle)
        if abs(area) <= 1e-20:
            raise ValueError(f"Degenerate triangle {label}")
        triangles[label] = triangle if area > 0 else tuple(reversed(triangle))
    _validate_nonoverlap(triangles)
    # Ignore orphan reference-point nodes when inferring the physical bounds.
    points = [point for triangle in triangles.values() for point in triangle]
    xs, ys = zip(*points)
    return Mesh(triangles, phases, (min(xs), max(xs), min(ys), max(ys)), str(path), hashlib.sha256(raw).hexdigest())


def default_roi_specs(mesh):
    """Exporter-compatible default geometry, including translated unit squares."""
    xmin, xmax, ymin, ymax = mesh.bounds
    if not math.isclose(xmax - xmin, 1., abs_tol=1e-10) or not math.isclose(ymax - ymin, 1., abs_tol=1e-10):
        raise ValueError("Default ROI geometry requires a unit-square mesh")
    return _export.build_edge_roi_specs(1., 1., radius=.1, count_per_side=9,
                                        vertical_spacing=.1, x_min=xmin, y_min=ymin)


def compute_area_fractions(mesh, roi_specs=None):
    """Return percentages over EXPECTED ROI area; missing area is never normalized.

    coverage_error is signed represented_area - expected_area (length units²).
    Overlap is independently rejected when the deck is read, preventing gaps
    from cancelling duplicate geometry in the aggregate area check.
    """
    specs = default_roi_specs(mesh) if roi_specs is None else list(roi_specs)
    if len({roi.name for roi in specs}) != len(specs):
        raise ValueError("Duplicate ROI names")
    xmin, xmax, ymin, ymax = mesh.bounds
    represented_domain = math.fsum(_signed_area(triangle) for triangle in mesh.triangles.values())
    if not math.isclose(represented_domain, (xmax - xmin) * (ymax - ymin), rel_tol=COVERAGE_REL_TOL, abs_tol=COVERAGE_ABS_TOL):
        raise ValueError("Mesh domain coverage is incomplete")
    rows = []
    for roi in specs:
        contributions = {phase: [] for phase in PHASE_NAMES}
        for label, triangle in mesh.triangles.items():
            # Bounding-box rejection only: never reject by centroid.
            if (max(p[0] for p in triangle) < roi.center[0] - roi.radius or
                min(p[0] for p in triangle) > roi.center[0] + roi.radius or
                max(p[1] for p in triangle) < roi.center[1] - roi.radius or
                min(p[1] for p in triangle) > roi.center[1] + roi.radius):
                continue
            contributions[mesh.phases[label]].append(triangle_semicircle_area(triangle, roi))
        areas = {phase: math.fsum(values) for phase, values in contributions.items()}
        represented = math.fsum(areas.values())
        expected = math.pi * roi.radius**2 / 2
        error = represented - expected
        if not math.isclose(represented, expected, rel_tol=COVERAGE_REL_TOL, abs_tol=COVERAGE_ABS_TOL):
            raise ValueError(f"ROI {roi.name} coverage error: represented={represented}, expected={expected}")
        rows.append(dict(roi_name=roi.name, **{phase: 100 * area / expected for phase, area in areas.items()},
                         represented_area=represented, expected_area=expected, coverage_error=error))
    return rows


def write_area_fractions(input_deck, output_csv):
    """Validate first, then write CSV and same-stem JSON provenance sidecar."""
    mesh = read_input_deck(input_deck)
    specs = default_roi_specs(mesh)
    rows = compute_area_fractions(mesh, specs)
    path = Path(output_csv)
    source = Path(input_deck).resolve()
    if path.resolve() == source or path.with_suffix(".json").resolve() == source:
        raise ValueError("Output must not overwrite the input deck")
    metadata = dict(method="analytic triangle-half-plane clipping and disk line/arc signed-area integration",
                    reference_configuration="undeformed", source_path=mesh.source_path,
                    source_sha256=mesh.source_sha256, element_type="CPS3", element_count=len(mesh.triangles),
                    material_to_phase=MATERIAL_TO_PHASE, bounds=mesh.bounds,
                    denominator="expected semicircle area (not represented mesh area)",
                    coverage_error_definition="represented_area - expected_area",
                    coverage_relative_tolerance=COVERAGE_REL_TOL, coverage_absolute_tolerance=COVERAGE_ABS_TOL,
                    units="area in input-deck coordinate units squared; fractions in percent",
                    rois=[dict(name=roi.name, side=roi.side, center=roi.center, radius=roi.radius) for roi in specs])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["roi_name"] + PHASE_NAMES + ["represented_area", "expected_area", "coverage_error"])
        writer.writeheader()
        writer.writerows(rows)
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-deck", required=True, help="FINAL self-contained Abaqus .inp with solid sections and materials")
    parser.add_argument("--output-csv", required=True, help="ROI phase-area CSV (a same-stem .json records provenance)")
    args = parser.parse_args()
    print(f"Wrote ROI phase-area fractions: {write_area_fractions(args.input_deck, args.output_csv)}")


if __name__ == "__main__":
    main()
