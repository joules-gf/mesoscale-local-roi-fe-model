from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
REF_CSV = REPO_ROOT / '00_Main_Scripts' / 'material_reference_curves' / 'aa7075-T6_monotonic_ROM_cyclic_parameters.csv'
OUTPUT_ROOT = REPO_ROOT / 'simulation_outputs'
GROUPS = [
    ('plastic_stress_sensitivity', 'Plastic Stress Sensitivity - Corrected no-zip extraction'),
    ('plastic_stress_sensitivity_mesh00328_backup_20260624_144408', 'Plastic Stress Sensitivity mesh 0.00328 backup - Corrected no-zip extraction'),
]


def load_numeric_csv(path, strain_col, stress_col):
    strain, stress = [], []
    with open(path, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            try:
                strain.append(float(row[strain_col]))
                stress.append(float(row[stress_col]))
            except (ValueError, IndexError):
                continue
    return strain, stress


def area(x, y):
    total = 0.0
    for i in range(1, len(x)):
        total += (x[i] - x[i-1]) * (y[i] + y[i-1]) / 2.0
    return total


def final_value(x, y):
    return (x[-1], y[-1]) if x and y else ('', '')


def plot_group(group, title):
    group_dir = OUTPUT_ROOT / group
    ref_x, ref_y = load_numeric_csv(REF_CSV, 0, 1)
    ref_area = area(ref_x, ref_y)

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(ref_x, ref_y, 'k--', linewidth=4, label=f'AA7075-T6 cyclic ROM (Area = {ref_area:.3f})')

    summary_rows = [[
        'group', 'case', 'old_csv', 'corrected_csv', 'old_final_strain', 'old_final_force',
        'corrected_final_strain', 'corrected_final_force', 'old_area', 'corrected_area',
        'force_delta', 'force_ratio_corrected_over_old', 'area_delta', 'area_ratio_corrected_over_old',
        'bottom_node_count', 'upper_node_count'
    ]]

    corrected_files = sorted(group_dir.glob('bp_plastic_stress_case_*/bp_plastic_stress_case_*_corrected_nozip.csv'))
    for csv_path in corrected_files:
        case_dir = csv_path.parent
        case_name = case_dir.name
        old_csv = case_dir / f'{case_name}.csv'

        cx, cy = load_numeric_csv(csv_path, 1, 2)
        if cx and cy:
            ax.plot(cx, cy, linewidth=1.4, alpha=0.78)
        ox, oy = load_numeric_csv(old_csv, 1, 2) if old_csv.exists() else ([], [])
        _, old_final_force = final_value(ox, oy)
        old_final_strain, _ = final_value(ox, oy)
        corr_final_strain, corr_final_force = final_value(cx, cy)
        old_area = area(ox, oy) if ox and oy else ''
        corr_area = area(cx, cy) if cx and cy else ''
        bottom_count = upper_count = ''
        with open(csv_path, newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0] == 'Step Time':
                    continue
                try:
                    bottom_count = int(float(row[3]))
                    upper_count = int(float(row[4]))
                    break
                except (ValueError, IndexError):
                    continue
        force_delta = corr_final_force - old_final_force if isinstance(corr_final_force, float) and isinstance(old_final_force, float) else ''
        force_ratio = corr_final_force / old_final_force if isinstance(corr_final_force, float) and isinstance(old_final_force, float) and old_final_force else ''
        area_delta = corr_area - old_area if isinstance(corr_area, float) and isinstance(old_area, float) else ''
        area_ratio = corr_area / old_area if isinstance(corr_area, float) and isinstance(old_area, float) and old_area else ''
        summary_rows.append([
            group, case_name, str(old_csv), str(csv_path), old_final_strain, old_final_force,
            corr_final_strain, corr_final_force, old_area, corr_area,
            force_delta, force_ratio, area_delta, area_ratio, bottom_count, upper_count
        ])

    ax.set_xlabel('Strain', fontsize=15)
    ax.set_ylabel('Stress / total RF over unit area (MPa)', fontsize=15)
    ax.set_title(title, fontsize=16)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=11)
    fig.tight_layout()
    out_png = group_dir / 'stress_strain_all_curves_corrected_nozip.png'
    fig.savefig(out_png, dpi=300)
    plt.close(fig)

    summary_csv = group_dir / 'corrected_nozip_vs_old_summary.csv'
    with open(summary_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(summary_rows)
    return out_png, summary_csv, len(corrected_files)


if __name__ == '__main__':
    for group, title in GROUPS:
        out_png, summary_csv, count = plot_group(group, title)
        print(f'{group}: plotted {count} corrected curves')
        print(f'  {out_png}')
        print(f'  {summary_csv}')
