"""Plot verified round-1 and round-2 normal results at 1% strain; no solver calls."""
import csv
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from plot_normal_stress_and_mesh_quality import study_rows, OUT, PNG, sha

OUTPUT = OUT / 'normal_stress_vs_mean_diameter_rounds_1_2.png'


def main():
    rows = study_rows(include_round2=True)
    # Verify the existing four-panel image and its point data before delivering it.
    verification = json.loads((OUT/'verification.json').read_text())
    assert verification['cases'] == 24
    assert verification['round_counts'] == {'1':21, '2':3}
    assert verification['violin_center'] == 'mean'
    assert verification['figure_sha256'] == sha(PNG)
    with (OUT/'case_quality_summary.csv').open(newline='', encoding='utf-8') as stream:
        summary = {r['case']:r for r in csv.DictReader(stream)}
    assert len(summary) == 24 and set(summary) == {r['case'] for r in rows}
    for row in rows:
        assert abs(float(summary[row['case']]['stress_at_1pct_MPa'])-row['stress_at_1pct_MPa']) < 1e-9
        assert abs(float(summary[row['case']]['mean_diameter_microns'])-row['mean_diameter_microns']) < 1e-9
    fig, ax = plt.subplots(figsize=(10,6))
    for round_number, color in ((1,'tab:blue'),(2,'tab:orange')):
        subset = [r for r in rows if r['round'] == round_number]
        ax.plot([r['mean_diameter_microns'] for r in subset], [r['stress_at_1pct_MPa'] for r in subset],
                'o-' if round_number == 1 else 'o', color=color, linewidth=2, markersize=7,
                label='Round 1: existing simulations' if round_number == 1 else 'Round 2: 120, 130, 140 microns')
    ax.set_xlabel('Mean Diameter (microns)', fontsize=16)
    ax.set_ylabel('Stress at 1% Strain (MPa)', fontsize=16)
    ax.set_title('Normal Distribution: Stress vs Mean Diameter', fontsize=18)
    ax.tick_params(labelsize=13)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=11, loc='lower left')
    fig.tight_layout()
    assert [len(line.get_xdata()) for line in ax.lines] == [21,3]
    fig.savefig(OUTPUT, dpi=300)
    fig.savefig(OUTPUT.with_suffix('.pdf'))
    fig.savefig(OUT/'stress_only_preview.png', dpi=110)
    plt.close(fig)
    with OUTPUT.with_suffix('.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    print('[OK] 24 verified cases: 21 blue round-1 points + 3 orange round-2 points.')
    print('[OK] Existing four-panel image hash and all 24 point values verified against saved results.')
    print('New cases (mean microns, stress MPa):', [(r['mean_diameter_microns'], r['stress_at_1pct_MPa']) for r in rows if r['round']==2])
    print('Stress-only figure:',OUTPUT)
    print('Four-panel figure:',PNG)


if __name__=='__main__':
    main()
