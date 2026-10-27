"""Four aligned panels for the completed normal-distribution diameter sweep.

Read saved solved CPS3 meshes only: never remesh or invoke Abaqus.
Each violin includes every triangle of its case, equal maximum violin widths.
User-specified quality guides are descriptive screens, not convergence criteria.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from plot_normal_mean_diameter_vs_stress_1pct import collect_rows, ROOT, BATCH
sys.path.insert(0, str(ROOT / '01_Secondary_Scripts/automated_run_helpers'))
from mesh_angle30_quality import parse_mesh, triangle_quality

OUT = BATCH / 'stress_and_mesh_quality'
PNG = OUT / 'normal_mean_diameter_stress_mesh_quality_4panels.png'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def metrics(points):
    """Vectorized r/R, maximum/minimum edge, minimum angle; points=(N,3,2)."""
    vectors = np.roll(points, -1, axis=1) - points
    lengths = np.linalg.norm(vectors, axis=2)
    twice_area = np.abs(vectors[:, 0, 0]*(-vectors[:, 2, 1]) - vectors[:, 0, 1]*(-vectors[:, 2, 0]))
    if not np.all(np.isfinite(points)) or np.any(lengths <= 0) or np.any(twice_area <= 0):
        raise ValueError('Nonfinite or degenerate triangle')
    semiperimeter = lengths.sum(axis=1)/2
    r_over_R = twice_area**2 / (semiperimeter*np.prod(lengths, axis=1))
    edge_ratio = lengths.max(axis=1)/lengths.min(axis=1)
    angles = []
    for vertex in range(3):
        u = points[:, (vertex+1)%3] - points[:, vertex]
        v = points[:, (vertex+2)%3] - points[:, vertex]
        cross = np.abs(u[:, 0]*v[:, 1]-u[:, 1]*v[:, 0])
        angles.append(np.degrees(np.arctan2(cross, np.sum(u*v, axis=1))))
    min_angle = np.min(angles, axis=0)
    result = {'r_over_R': r_over_R, 'edge_ratio': edge_ratio, 'min_angle_deg': min_angle}
    assert all(np.isfinite(a).all() for a in result.values())
    assert np.all((r_over_R > 0) & (r_over_R <= 0.5+1e-12))
    assert np.all(edge_ratio >= 1) and np.all((min_angle > 0) & (min_angle <= 60+1e-10))
    return result


def verify_metrics():
    examples = np.array([[[0,0],[1,0],[0.5,np.sqrt(3)/2]], [[0,0],[1,0],[0,1]]], dtype=float)
    q = metrics(examples)
    np.testing.assert_allclose(q['r_over_R'], [0.5, np.sqrt(2)-1])
    np.testing.assert_allclose(q['edge_ratio'], [1, np.sqrt(2)])
    np.testing.assert_allclose(q['min_angle_deg'], [60, 45])
    # Reversing orientation must not change the metrics.
    for key, value in metrics(examples[:, ::-1, :]).items():
        np.testing.assert_allclose(value, q[key])


def audit(row):
    case = row['case']
    folder = ROOT / 'simulation_outputs' / case
    mesh = folder / 'abaqus_files' / (case+'.inp')
    fingerprint = sha(mesh)
    nodes, elements = parse_mesh(mesh)
    assert all(typ == 'CPS3' for typ, ids in elements.values())
    coordinates = np.full((max(nodes)+1, 2), np.nan)
    for nid, xy in nodes.items():
        coordinates[nid] = xy
    ids = np.fromiter(elements.keys(), dtype=np.int64, count=len(elements))
    connectivity = np.array([item[1] for item in elements.values()], dtype=np.int64)
    points = coordinates[connectivity]
    values = metrics(points)
    # Independently cross-check the vectorized formulas with the scalar audit.
    for index in np.unique(np.linspace(0, len(points)-1, 31).astype(int)):
        independent = triangle_quality(points[index].tolist())
        for key in values:
            np.testing.assert_allclose(values[key][index], independent[key], rtol=1e-11, atol=1e-11)
    assert sha(mesh) == fingerprint, 'Mesh changed during analysis'
    cache = OUT / (case+'_triangle_quality.npz')
    np.savez_compressed(cache, element_id=ids, **values)
    summary = dict(row, triangle_count=len(elements), node_count=len(nodes), source_mesh=str(mesh.relative_to(ROOT)), source_mesh_sha256=fingerprint)
    for key, array in values.items():
        summary[key+'_mean'] = float(np.mean(array))
        for label, quantile in zip(('min', 'p05', 'median', 'p95', 'max'), np.percentile(array, [0,5,50,95,100])):
            summary[key+'_'+label] = float(quantile)
    summary['fraction_r_over_R_below_0p2'] = float(np.mean(values['r_over_R'] < 0.2))
    summary['fraction_r_over_R_below_0p3'] = float(np.mean(values['r_over_R'] < 0.3))
    summary['fraction_min_angle_below_30'] = float(np.mean(values['min_angle_deg'] < 30))
    print('[AUDIT]', case, len(elements), 'triangles;', 'max edge ratio=', summary['edge_ratio_max'], flush=True)
    return summary, values


def study_rows(include_round2=False):
    rows = [dict(row, round=1) for row in collect_rows()]
    if include_round2:
        manifest = ROOT/'simulation_outputs/normal_equal_mean_round2_batch/manifest.json'
        expected = {f'normal_round2_mean_{d:03d}um' for d in (120,130,140)}
        rows.extend(dict(row, round=2) for row in collect_rows(manifest, expected))
    rows.sort(key=lambda r:r['mean_diameter_microns'])
    expected_count = 24 if include_round2 else 21
    assert len(rows) == expected_count and len({r['mean_diameter_microns'] for r in rows}) == expected_count
    return rows


def draw_violins(ax, data, positions, color):
    violin = ax.violinplot(data, positions=positions, widths=3.5, showmeans=True, showmedians=False, showextrema=True, points=150)
    for body in violin['bodies']:
        body.set_facecolor(color)
        body.set_edgecolor(color)
        body.set_alpha(0.65)
    for name in ('cmeans', 'cmins', 'cmaxes', 'cbars'):
        violin[name].set_color('black')
        violin[name].set_linewidth(0.7 if name != 'cmeans' else 1.8)
    assert 'cmedians' not in violin
    np.testing.assert_allclose([segment[0,1] for segment in violin['cmeans'].get_segments()], [np.mean(a) for a in data])
    return len(violin['bodies'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-round2', action='store_true', help='Require and include all three completed extra simulations')
    args = parser.parse_args()
    verify_metrics()
    rows = study_rows(args.include_round2)
    OUT.mkdir(parents=True, exist_ok=True)
    summaries, distributions = [], []
    for row in rows:
        summary, values = audit(row)
        summaries.append(summary)
        distributions.append(values)
        # Save incremental progress; expensive FE results are never modified.
        with (OUT/'case_quality_summary.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
            writer.writeheader()
            writer.writerows(summaries)
    x = np.array([r['mean_diameter_microns'] for r in rows])
    plt.rcParams.update({'font.size': 12, 'axes.labelsize': 14, 'axes.titlesize': 14})
    fig, axes = plt.subplots(4, 1, figsize=(16, 15), sharex=True)
    fig.subplots_adjust(left=0.10, right=0.975, top=0.93, bottom=0.09, hspace=0.22)
    fig.suptitle('Normal Distribution: Stress Response and Triangle Mesh Quality', fontsize=20, y=0.98)
    groups = [(1, 'tab:blue'), (2, 'tab:orange')]
    for round_number, color in groups:
        subset = [r for r in rows if r['round'] == round_number]
        if subset:
            axes[0].plot([r['mean_diameter_microns'] for r in subset], [r['stress_at_1pct_MPa'] for r in subset],
                         'o-' if round_number == 1 else 'o', color=color, linewidth=2, markersize=6, label=f'Round {round_number}')
    axes[0].set_ylabel('Stress at 1% Strain\n(MPa)')
    axes[0].set_title('(a) Stress response', loc='left')
    settings = [
        ('r_over_R', 'Inradius / Circumradius', '(b) Triangle radius ratio'),
        ('edge_ratio', 'Longest Edge / Shortest Edge', '(c) Triangle edge ratio'),
        ('min_angle_deg', 'Minimum Angle (degrees)', '(d) Triangle minimum angle'),
    ]
    body_counts = []
    for ax, (key, ylabel, title) in zip(axes[1:], settings):
        count = 0
        for round_number, color in groups:
            indices = [i for i, r in enumerate(rows) if r['round'] == round_number]
            if indices:
                count += draw_violins(ax, [distributions[i][key] for i in indices], x[indices], color)
        body_counts.append(count)
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc='left')
        if key == 'r_over_R':
            ax.axhline(0.2, color='#E6BE00', linestyle='--', linewidth=1.8, label='fair quality (0.2)')
            ax.axhline(0.3, color='green', linestyle='--', linewidth=1.8, label='good quality (0.3)')
            ax.set_ylim(0, 0.53)
            ax.legend(loc='lower right', fontsize=10, framealpha=0.95, ncol=2)
        if key == 'min_angle_deg':
            ax.axhline(30, color='green', linestyle='--', linewidth=1.8, label='good quality (30 degrees)')
            ax.set_ylim(0, 63)
            ax.legend(loc='lower right', fontsize=10, framealpha=0.95)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.set_axisbelow(True)
        ax.set_xlim(5, 205)
    axes[-1].set_xticks(x, [f'{v:g}' for v in x], rotation=45, ha='right')
    axes[-1].set_xlabel('Mean Diameter (microns)', labelpad=8)
    fig.text(0.5, 0.015, 'Black horizontal bars mark violin means.\nRound 1 (blue): existing simulations; Round 2 (orange): 120, 130, 140 microns.', ha='center', fontsize=11)
    assert body_counts == [len(rows)]*3 and sum(len(line.get_xdata()) for line in axes[0].lines) == len(rows)
    assert all(axes[0].get_shared_x_axes().joined(axes[0], ax) for ax in axes)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for ax in axes:
        for text in (ax.title, ax.xaxis.label, ax.yaxis.label):
            box = text.get_window_extent(renderer)
            assert box.x0 >= 0 and box.y0 >= 0 and box.x1 <= fig.bbox.width and box.y1 <= fig.bbox.height
    fig.savefig(PNG, dpi=240)
    fig.savefig(PNG.with_suffix('.pdf'))
    fig.savefig(OUT/'preview.png', dpi=90)
    plt.close(fig)
    verification = {'cases': len(rows), 'total_triangles': sum(r['triangle_count'] for r in summaries),
                    'round_counts': {str(n):sum(r['round']==n for r in rows) for n in (1,2)},
                    'violin_center': 'mean', 'round_colors': {'1':'tab:blue', '2':'tab:orange'},
                    'violins_per_quality_panel': body_counts, 'all_triangles_included': True,
                    'shared_numeric_diameter_axis_microns': True, 'scalar_crosschecks_per_case': 31,
                    'equilateral_right_and_orientation_tests': 'passed',
                    'radius_ratio_formula': 'r/R = 4*A^2/(s*a*b*c); equilateral=0.5',
                    'quality_thresholds': {'r_over_R_fair': 0.2, 'r_over_R_good': 0.3, 'min_angle_good_degrees': 30},
                    'figure': str(PNG), 'figure_sha256': sha(PNG)}
    (OUT/'verification.json').write_text(json.dumps(verification, indent=2), encoding='utf-8')
    print(json.dumps(verification, indent=2), flush=True)


if __name__ == '__main__':
    main()
