"""Plot the 20 uniform lower-bound sweep cases plus four midpoint cases as one series.

Reads existing resolved XMLs and response CSVs only; never runs simulations.
"""
from pathlib import Path
import csv
import math
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'reference_outputs/Uniform Distribution/Sensitivity Study/lower-bound-diameter-equal-4all-phases'
OUTPUT = STUDY / 'phase_lower_bound_vs_stress_at_1pct_strain_all_cases.png'
DATA = OUTPUT.with_suffix('.csv')
MIDPOINTS = (
    'bp_same_size_case_07_08_mid_070um',
    'bp_same_size_case_08_09_mid_080um',
    'bp_same_size_case_15_16_mid_150um',
    'bp_same_size_case_16_17_mid_160um',
)


def read_lower_bound_microns(path):
    materials = ET.parse(path).getroot().findall('material')
    if len(materials) != 4:
        raise ValueError(f'Expected four phases: {path}')
    lower_bounds = []
    for material in materials:
        if material.findtext('size/dist_type', '').strip() != 'uniform':
            raise ValueError(f'Not a uniform-distribution input: {path}')
        lower_bounds.append(float(material.findtext('size/loc', 'nan')))
    if not all(math.isfinite(a) and math.isclose(a, lower_bounds[0], rel_tol=1e-13) for a in lower_bounds):
        raise ValueError(f'Phase lower bounds differ: {path}')
    return lower_bounds[0] * 1000.0  # Existing model's mm -> microns, NOT uniform mean.


def read_stress(path, target=0.01):
    points = []
    with path.open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.reader(stream):
            try:
                strain, stress = float(row[1]), float(row[2])
            except (IndexError, ValueError):
                continue
            if math.isfinite(strain) and math.isfinite(stress):
                points.append((strain, stress))
    points.sort(key=lambda p: p[0])
    for strain, stress in points:
        if abs(strain - target) < 1e-8:
            return stress
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= target <= x1 and x1 > x0:
            return y0 + (target - x0) * (y1 - y0) / (x1 - x0)
    raise ValueError(f'Target strain not covered: {path}')


def collect_rows():
    cases = [(STUDY / 'Simulations' / f'bp_same_size_case_{i:02d}', 'original') for i in range(1, 21)]
    cases.extend((ROOT / 'simulation_outputs' / case, 'midpoint') for case in MIDPOINTS)
    rows = []
    for folder, group in cases:
        case = folder.name
        xml, curve = folder / (case + '_resolved_input.xml'), folder / (case + '.csv')
        rows.append({'case': case, 'phase_lower_bound_microns': read_lower_bound_microns(xml), 'stress_at_1pct_MPa': read_stress(curve), 'group': group, 'source_xml': str(xml.relative_to(ROOT)), 'source_csv': str(curve.relative_to(ROOT))})
    rows.sort(key=lambda r: r['phase_lower_bound_microns'])
    if len(rows) != 24 or len({r['case'] for r in rows}) != 24 or len({r['phase_lower_bound_microns'] for r in rows}) != 24:
        raise ValueError('Expected 24 unique cases/lower bounds')
    if sum(r['group'] == 'original' for r in rows) != 20 or sum(r['group'] == 'midpoint' for r in rows) != 4:
        raise ValueError('Original/midpoint count mismatch')
    return rows


def main():
    rows = collect_rows()
    # Match the source midpoint plot: 8x6 in, 300 dpi, regular 18/16 pt text,
    # blue solid line, circular markers, and the same major-grid appearance.
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot([r['phase_lower_bound_microns'] for r in rows], [r['stress_at_1pct_MPa'] for r in rows], color='tab:blue', linestyle='-', marker='o', linewidth=2, markersize=6, label='All sensitivity cases')
    ax.set_xlabel('Phase Lower Bound (microns)', fontsize=16)
    ax.set_ylabel('Stress at 1% strain (MPa)', fontsize=16)
    ax.set_title('Phase Lower Bound vs Stress at 1% Strain', fontsize=18)
    ax.tick_params(axis='both', labelsize=16)
    ax.grid(True, alpha=0.35)
    ax.legend(fontsize=16, loc='upper right')
    fig.tight_layout()
    fig.canvas.draw()
    if len(ax.lines) != 1 or len(ax.lines[0].get_xdata()) != 24 or ax.lines[0].get_linestyle() != '-' or ax.lines[0].get_marker() != 'o':
        raise AssertionError('Unexpected plotted series/point count/style')
    renderer = fig.canvas.get_renderer()
    for text in (ax.title, ax.xaxis.label, ax.yaxis.label):
        bbox = text.get_window_extent(renderer)
        if not (0 <= bbox.x0 <= bbox.x1 <= fig.bbox.width and 0 <= bbox.y0 <= bbox.y1 <= fig.bbox.height):
            raise AssertionError('Figure text exceeds canvas')
    fig.savefig(OUTPUT, dpi=300)
    plt.close(fig)
    with DATA.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print('Verified one solid blue circle-marker series: 24 points (20 original + 4 midpoint).')
    print('Figure:', OUTPUT)
    print('Source-point CSV:', DATA)


if __name__ == '__main__':
    main()
