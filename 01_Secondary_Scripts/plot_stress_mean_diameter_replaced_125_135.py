"""Separate stress figure: original cases except 125/135, plus 120/140 microns.

Exclude the added 130-micron case. Preserve all earlier figures and result files.
No legend or point annotations; retain physical axis labels and units.
"""
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from plot_normal_stress_and_mesh_quality import study_rows, OUT

OUTPUT = OUT / 'stress_vs_mean_diameter_replace_125_135_with_120_140.png'


def main():
    available = study_rows(include_round2=True)
    rows = [r for r in available if
            (r['round'] == 1 and r['mean_diameter_microns'] not in (125.0,135.0)) or
            (r['round'] == 2 and r['mean_diameter_microns'] in (120.0,140.0))]
    rows.sort(key=lambda r:r['mean_diameter_microns'])
    expected = ({r['mean_diameter_microns'] for r in available if r['round']==1} - {125.0,135.0}) | {120.0,140.0}
    x = [r['mean_diameter_microns'] for r in rows]
    assert len(rows) == 21 and set(x) == expected
    assert not ({125.0,130.0,135.0} & set(x))
    assert sum(r['round']==1 for r in rows) == 19 and sum(r['round']==2 for r in rows) == 2
    fig, ax = plt.subplots(figsize=(10,6))
    ax.plot(x, [r['stress_at_1pct_MPa'] for r in rows], 'o-', color='tab:blue', linewidth=2, markersize=7)
    extra = [r for r in rows if r['round']==2]
    ax.scatter([r['mean_diameter_microns'] for r in extra], [r['stress_at_1pct_MPa'] for r in extra],
               color='tab:orange', s=49, zorder=4)
    ax.set_xlabel('Mean Diameter (microns)', fontsize=16)
    ax.set_ylabel('Stress at 1% Strain (MPa)', fontsize=16)
    ax.set_title('Stress vs Mean Diameter', fontsize=18)
    ax.tick_params(labelsize=13)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    assert ax.get_legend() is None and ax.get_title()=='Stress vs Mean Diameter'
    assert len(ax.lines[0].get_xdata())==21 and not ax.texts
    fig.savefig(OUTPUT,dpi=300)
    fig.savefig(OUTPUT.with_suffix('.pdf'))
    fig.savefig(OUTPUT.with_name(OUTPUT.stem+'_preview.png'),dpi=110)
    plt.close(fig)
    with OUTPUT.with_suffix('.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('[OK] 21 verified points: 19 original cases + 120/140 microns; 125/130/135 excluded; no legend or annotations.')
    print('Diameters:',x)
    print('Figure:',OUTPUT)


if __name__=='__main__':
    main()
