"""Two new all-blue copies of the selected 21-point replacement figure.

First uses the selected-data scale; second changes only the axis scale/ticks
back to those of the full original+round2 stress-only figure. No simulations.
"""
import csv
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from plot_normal_stress_and_mesh_quality import study_rows, OUT

NAME = 'stress_vs_mean_diameter_replacement_all_blue'


def label_axes(ax, title):
    ax.set_xlabel('Mean Diameter (microns)', fontsize=16)
    ax.set_ylabel('Stress at 1% Strain (MPa)', fontsize=16)
    ax.set_title(title, fontsize=18)
    ax.tick_params(labelsize=13)
    ax.grid(alpha=0.3)


def main():
    available = study_rows(include_round2=True)
    rows = [r for r in available if
            (r['round']==1 and r['mean_diameter_microns'] not in (125.0,135.0)) or
            (r['round']==2 and r['mean_diameter_microns'] in (120.0,140.0))]
    rows.sort(key=lambda r:r['mean_diameter_microns'])
    assert len(rows)==21 and not ({125.0,130.0,135.0} & {r['mean_diameter_microns'] for r in rows})
    source = OUT/'stress_vs_mean_diameter_replace_125_135_with_120_140.csv'
    with source.open(newline='',encoding='utf-8') as stream:
        previous=list(csv.DictReader(stream))
    assert [r['case'] for r in rows]==[r['case'] for r in previous]
    np.testing.assert_array_equal([r['stress_at_1pct_MPa'] for r in rows], [float(r['stress_at_1pct_MPa']) for r in previous])

    # Reproduce the exact full-data plotting recipe to recover its autoscale,
    # rather than estimating limits from PNG tick labels.
    reference_fig, reference_ax = plt.subplots(figsize=(10,6))
    for round_number, color in ((1,'tab:blue'),(2,'tab:orange')):
        group=[r for r in available if r['round']==round_number]
        reference_ax.plot([r['mean_diameter_microns'] for r in group], [r['stress_at_1pct_MPa'] for r in group],
                          'o-' if round_number==1 else 'o', color=color, linewidth=2, markersize=7,
                          label='Round 1: existing simulations' if round_number==1 else 'Round 2: 120, 130, 140 microns')
    label_axes(reference_ax,'Normal Distribution: Stress vs Mean Diameter')
    reference_ax.legend(fontsize=11,loc='lower left')
    reference_fig.tight_layout()
    reference_fig.canvas.draw()
    reference_limits={'xlim':list(reference_ax.get_xlim()), 'ylim':list(reference_ax.get_ylim()),
                      'xticks':reference_ax.get_xticks().tolist(), 'yticks':reference_ax.get_yticks().tolist()}
    plt.close(reference_fig)

    fig, ax=plt.subplots(figsize=(10,6))
    x=[r['mean_diameter_microns'] for r in rows]
    y=[r['stress_at_1pct_MPa'] for r in rows]
    line,=ax.plot(x,y,'o-',color='tab:blue',linewidth=2,markersize=7)
    label_axes(ax,'Stress vs Mean Diameter')
    fig.tight_layout()
    original_position=ax.get_position().bounds
    first_limits={'xlim':list(ax.get_xlim()),'ylim':list(ax.get_ylim())}
    assert len(line.get_xdata())==21 and line.get_markerfacecolor()=='tab:blue'
    assert len(ax.collections)==0 and ax.get_legend() is None and not ax.texts
    outputs=[]
    for variant in ('current_scale','previous_full_scale'):
        if variant=='previous_full_scale':
            ax.set_xticks(reference_limits['xticks'])
            ax.set_yticks(reference_limits['yticks'])
            ax.set_xlim(reference_limits['xlim'])
            ax.set_ylim(reference_limits['ylim'])
        np.testing.assert_array_equal(line.get_xdata(),x)
        np.testing.assert_array_equal(line.get_ydata(),y)
        np.testing.assert_array_equal(ax.get_position().bounds,original_position)
        assert ax.get_title()=='Stress vs Mean Diameter' and ax.get_legend() is None
        target=OUT/(NAME+'_'+variant+'.png')
        fig.savefig(target,dpi=300)
        fig.savefig(target.with_suffix('.pdf'))
        fig.savefig(target.with_name(target.stem+'_preview.png'),dpi=100)
        outputs.append({'file':str(target),'xlim':list(ax.get_xlim()),'ylim':list(ax.get_ylim())})
    np.testing.assert_array_equal(ax.get_ylim(),reference_limits['ylim'])
    np.testing.assert_array_equal(ax.get_xlim(),reference_limits['xlim'])
    plt.close(fig)
    with (OUT/(NAME+'.csv')).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    verification={'point_count':len(rows),'all_markers_blue':True,'identical_data_to_previous_selected_figure':True,
                  'title':'Stress vs Mean Diameter','legend':False,'current_scale':first_limits,
                  'reference_full_24_case_scale':reference_limits,'outputs':outputs}
    (OUT/(NAME+'_verification.json')).write_text(json.dumps(verification,indent=2),encoding='utf-8')
    print(json.dumps(verification,indent=2))


if __name__=='__main__':
    main()
