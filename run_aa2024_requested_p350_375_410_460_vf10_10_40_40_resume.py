from pathlib import Path
import os
import sys
import csv

REPO = Path('/home/joules_gf/projects/dr-irwin-hermes/workspace/mesoscale-local-roi-fe-model')
CASE = 'aa2024-t351-p350-375-410-460-vf10-10-40-40'
CASE_DIR = REPO / 'simulation_outputs' / CASE
ABAQUS_DIR = CASE_DIR / 'abaqus_files'
REF_CSV = REPO / '00_Main_Scripts' / 'material_reference_curves' / 'aa2024-T351_monotonic_ROM_1pct_strain.csv'

os.environ['MPLBACKEND'] = 'Agg'
os.environ['MICROSTRUCTURE_NONINTERACTIVE'] = '1'
sys.path.insert(0, str(REPO / '00_Main_Scripts'))


def read_csv_xy(path, xcol, ycol):
    xs, ys = [], []
    with open(path, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            try:
                xs.append(float(row[xcol]))
                ys.append(float(row[ycol]))
            except (ValueError, IndexError):
                continue
    return xs, ys


def area(xs, ys):
    return sum((xs[i] - xs[i-1]) * (ys[i] + ys[i-1]) / 2 for i in range(1, len(xs)))


def make_aa2024_plots(result_csv):
    import pandas as pd
    import matplotlib.pyplot as plt

    ref_strain, ref_stress = read_csv_xy(REF_CSV, 0, 1)
    sim_strain, sim_stress = read_csv_xy(result_csv, 1, 2)
    ref_area = area(ref_strain, ref_stress)
    sim_area = area(sim_strain, sim_stress)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.plot(ref_strain, ref_stress, label=f'AA2024-T351 R-O reference (Area = {ref_area:.3f})', linewidth=3, linestyle='--', color='black')
    ax.plot(sim_strain, sim_stress, label=f'{CASE} (Area = {sim_area:.3f})', linewidth=2, color='red')
    ax.set_xlabel('Strain')
    ax.set_ylabel('Stress (MPa)')
    ax.set_title('Requested AA2024-T351 Simulation vs Reference')
    ax.grid(True)
    ax.legend(fontsize=8)
    fig.tight_layout()
    aa2024_plot = CASE_DIR / f'stress_strain_{CASE}_AA2024_T351_reference.png'
    fig.savefig(aa2024_plot)
    plt.close(fig)

    df = pd.read_csv(result_csv, skiprows=1)
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.plot(df['Step Time'], df['U_Y'], marker='o', linestyle='-')
    ax.set_xlabel('Step Time (s)')
    ax.set_ylabel('Displacement (mm)')
    ax.set_title(f"Simulation '{CASE}' Displacement vs Step Time")
    ax.grid(True)
    fig.tight_layout()
    cycles_plot = CASE_DIR / f'cycles_{CASE}.png'
    fig.savefig(cycles_plot)
    plt.close(fig)
    return aa2024_plot, cycles_plot, sim_area, ref_area, len(df), df.iloc[-1].to_dict()


def main():
    from run_abaqus_sim import run_simulation
    from postprocessing_abaqus_sim_v01 import extract_force_displacement

    print('REQUESTED AA2024 RESUME START', flush=True)
    inp = ABAQUS_DIR / f'{CASE}.inp'
    if not inp.exists():
        raise RuntimeError(f'Missing generated input: {inp}')
    print(f'Using existing Abaqus input: {inp}', flush=True)

    sta = ABAQUS_DIR / f'{CASE}.sta'
    odb = ABAQUS_DIR / f'{CASE}.odb'
    if not (sta.exists() and odb.exists() and 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in sta.read_text(errors='ignore')):
        print('Running Abaqus simulation...', flush=True)
        run_simulation(str(ABAQUS_DIR), CASE)
    else:
        print('Abaqus artifacts already complete; skipping solver run.', flush=True)

    if not sta.exists() or not odb.exists():
        raise RuntimeError(f'Missing Abaqus artifacts: sta={sta.exists()} odb={odb.exists()}')
    if 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta.read_text(errors='ignore'):
        raise RuntimeError('Abaqus .sta did not contain successful completion line')

    print('Extracting force-displacement...', flush=True)
    extract_force_displacement(str(ABAQUS_DIR), CASE)
    result_csv = CASE_DIR / f'{CASE}.csv'
    if not result_csv.exists():
        raise RuntimeError(f'Missing extracted CSV: {result_csv}')

    aa2024_plot, cycles_plot, sim_area, ref_area, rows, last = make_aa2024_plots(result_csv)
    print('REQUESTED AA2024 RESUME COMPLETE', flush=True)
    print(f'Case: {CASE}', flush=True)
    print(f'STA: {sta}', flush=True)
    print(f'ODB: {odb} ({odb.stat().st_size} bytes)', flush=True)
    print(f'CSV: {result_csv} ({rows} rows)', flush=True)
    print(f'Final row: {last}', flush=True)
    print(f'AA2024 reference area: {ref_area:.6f}', flush=True)
    print(f'Simulation area: {sim_area:.6f}', flush=True)
    print(f'MEDIA:{aa2024_plot}', flush=True)
    print(f'MEDIA:{cycles_plot}', flush=True)


if __name__ == '__main__':
    main()
