"""Plot all 21 completed normal equal-mean cases; read-only simulation inputs.

X: prescribed normal mean diameter, mm converted to microns (not realized seed mean).
Y: stress at engineering strain 0.01, MPa. The 1 mm square, unit-thickness
model maps U_Y in mm to strain and total reaction in N to stress in MPa.
Use a saved increment matching 0.01 within float32 tolerance, otherwise interpolate.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import sys

# Support direct execution and importlib standalone loading.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from normal_result_paths import resolve_case_folder
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'simulation_outputs/normal_equal_mean_batch'
OUTPUT = BATCH / 'mean_diameter_vs_stress_at_1pct_strain.png'
DATA = OUTPUT.with_suffix('.csv')
MM_TO_MICRONS = 1000.0


def read_stress(path, target=0.01):
    points = []
    with path.open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.reader(stream):
            try:
                strain, stress = float(row[1]), float(row[2])
            except (ValueError, IndexError):
                continue
            if not (math.isfinite(strain) and math.isfinite(stress)):
                raise ValueError(f'Nonfinite curve data: {path}')
            points.append((strain, stress))
    points.sort()
    for strain, stress in points:
        if math.isclose(strain, target, rel_tol=0, abs_tol=1e-8):
            return stress, strain, 'saved increment (float32 tolerance)'
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= target <= x1 and x1 > x0:
            return y0 + (target-x0)*(y1-y0)/(x1-x0), target, 'linear interpolation'
    raise ValueError(f'No strain=0.01 coverage: {path}')


def collect_rows(manifest_path=None, expected_cases=None):
    manifest_path = Path(manifest_path) if manifest_path else BATCH / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    expected = expected_cases if expected_cases is not None else {f'bp_same_size_case_{i:02d}' for i in range(1, 21)} | {'bp_same_size_baseline_0p050'}
    assert len(manifest) == len(expected) and {r['case'] for r in manifest} == expected
    rows = []
    for entry in manifest:
        case = entry['case']
        folder = resolve_case_folder(ROOT, case)
        xml = folder / (case + '_resolved_input.xml')
        curve = folder / (case + '.csv')
        marker = json.loads((manifest_path.parent / (case + '.completed.json')).read_text())
        source = ROOT / entry['input'].replace('\\', '/')
        assert marker['returncode'] == 0
        assert marker['input_sha256'] == entry['input_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in (folder/'abaqus_files'/(case+'.sta')).read_text(errors='replace').upper()
        root = ET.parse(xml).getroot()
        assert math.isclose(float(root.findtext('domain/side_length')), 1.0)
        sizes = root.findall('material/size')
        assert len(sizes) == 4
        means = []
        for size in sizes:
            assert size.findtext('dist_type').strip() == 'norm'
            means.append(float(size.findtext('loc')))
        assert all(math.isfinite(m) and math.isclose(m, means[0]) for m in means)
        assert math.isclose(means[0], entry['mean_mm'])
        stress, strain, method = read_stress(curve)
        rows.append({'case': case, 'mean_diameter_microns': means[0]*MM_TO_MICRONS,
                     'stress_at_1pct_MPa': stress, 'sampled_strain': strain, 'extraction': method,
                     'source_xml': str(xml.relative_to(ROOT)), 'source_csv': str(curve.relative_to(ROOT))})
    rows.sort(key=lambda r: r['mean_diameter_microns'])
    assert len({r['mean_diameter_microns'] for r in rows}) == len(expected)
    return rows


def main():
    rows = collect_rows()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot([r['mean_diameter_microns'] for r in rows], [r['stress_at_1pct_MPa'] for r in rows],
            color='tab:blue', linestyle='-', marker='o', linewidth=2, markersize=6)
    ax.set_xlabel('Mean Diameter (microns)', fontsize=16)
    ax.set_ylabel('Stress at 1% Strain (MPa)', fontsize=16)
    ax.set_title('Mean Diameter vs Stress at 1% Strain\nNormal Distribution', fontsize=18)
    ax.tick_params(axis='both', labelsize=14)
    ax.grid(True, alpha=0.35)
    fig.tight_layout()
    fig.canvas.draw()
    assert len(ax.lines) == 1 and len(ax.lines[0].get_xdata()) == 21
    renderer = fig.canvas.get_renderer()
    for text in (ax.title, ax.xaxis.label, ax.yaxis.label):
        box = text.get_window_extent(renderer)
        assert 0 <= box.x0 <= box.x1 <= fig.bbox.width and 0 <= box.y0 <= box.y1 <= fig.bbox.height
    fig.savefig(OUTPUT, dpi=300)
    plt.close(fig)
    with DATA.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'[OK] Verified and plotted {len(rows)} cases, including the 50-micron baseline.')
    print('Diameter range (microns):', rows[0]['mean_diameter_microns'], rows[-1]['mean_diameter_microns'])
    print('Stress range (MPa):', min(r['stress_at_1pct_MPa'] for r in rows), max(r['stress_at_1pct_MPa'] for r in rows))
    print('Figure:', OUTPUT)
    print('Data:', DATA)


if __name__ == '__main__':
    main()
