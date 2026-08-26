from pathlib import Path
import os
import time
import subprocess
import sys
import csv

REPO = Path('/home/joules_gf/projects/dr-irwin-hermes/workspace/mesoscale-local-roi-fe-model')
CASE = 'aa2024_t351_baseline_mel_0p00328'
RUNNER_PID = 42928
CASE_DIR = REPO / 'simulation_outputs' / CASE
ABAQUS_DIR = CASE_DIR / 'abaqus_files'
REF_CSV = REPO / '00_Main_Scripts' / 'material_reference_curves' / 'aa2024-T351_monotonic_ROM_1pct_strain.csv'
RESULT_CSV = CASE_DIR / f'{CASE}.csv'

os.environ['MPLBACKEND'] = 'Agg'
os.environ['MICROSTRUCTURE_NONINTERACTIVE'] = '1'
sys.path.insert(0, str(REPO / '00_Main_Scripts'))


def pid_alive(pid):
    return subprocess.run(['bash', '-lc', f'ps -p {pid} >/dev/null 2>&1']).returncode == 0


def wait_for_runner():
    start = time.time()
    while pid_alive(RUNNER_PID):
        elapsed = int(time.time() - start)
        if elapsed % 300 < 15:
            print(f'Runner still active after {elapsed}s; waiting...', flush=True)
        time.sleep(15)


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
    total = 0.0
    for i in range(1, len(xs)):
        total += (xs[i] - xs[i-1]) * (ys[i] + ys[i-1]) / 2
    return total


def make_plots():
    import pandas as pd
    import matplotlib.pyplot as plt

    ref_strain, ref_stress = read_csv_xy(REF_CSV, 0, 1)
    sim_strain, sim_stress = read_csv_xy(RESULT_CSV, 1, 2)
    if not ref_strain or not sim_strain:
        raise RuntimeError('Could not load reference or simulation CSV data for plotting')

    ref_area = area(ref_strain, ref_stress)
    sim_area = area(sim_strain, sim_stress)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.plot(ref_strain, ref_stress, label=f'AA2024-T351 R-O reference (Area = {ref_area:.3f})', linewidth=3, linestyle='--', color='black')
    ax.plot(sim_strain, sim_stress, label=f'{CASE} (Area = {sim_area:.3f})', linewidth=2, color='red')
    ax.set_xlabel('Strain')
    ax.set_ylabel('Stress (MPa)')
    ax.set_title('AA2024-T351 Simulation vs Reference')
    ax.grid(True)
    ax.legend()
    fig.tight_layout()
    aa2024_plot = CASE_DIR / f'stress_strain_{CASE}_AA2024_T351_reference.png'
    fig.savefig(aa2024_plot)
    plt.close(fig)

    df = pd.read_csv(RESULT_CSV, skiprows=1)
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
    print('Monitoring AA2024-T351 full run...', flush=True)
    wait_for_runner()
    print('Runner no longer active; checking Abaqus artifacts...', flush=True)

    sta = ABAQUS_DIR / f'{CASE}.sta'
    odb = ABAQUS_DIR / f'{CASE}.odb'
    inp = ABAQUS_DIR / f'{CASE}.inp'
    missing_after_run = [str(p) for p in [inp, sta, odb] if not p.exists()]
    if missing_after_run:
        print('AA2024-T351 run did not reach complete Abaqus artifacts.')
        print('Missing:', missing_after_run)
        print('Current files:')
        subprocess.run(['bash', '-lc', f"find {CASE_DIR} -maxdepth 4 -type f -printf '%TY-%Tm-%Td %TH:%TM %s %p\\n' | sort | tail -80"], cwd=str(REPO))
        raise SystemExit(1)

    sta_text = sta.read_text(errors='ignore')
    if 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta_text:
        print('Abaqus .sta exists but does not show successful completion:')
        print('\n'.join(sta_text.splitlines()[-40:]))
        raise SystemExit(1)

    print('Abaqus completed successfully; extracting force-displacement from ODB...', flush=True)
    from postprocessing_abaqus_sim_v01 import extract_force_displacement
    extract_force_displacement(str(ABAQUS_DIR), CASE)
    if not RESULT_CSV.exists():
        raise RuntimeError(f'Missing extracted CSV after postprocessing: {RESULT_CSV}')

    aa2024_plot, cycles_plot, sim_area, ref_area, rows, last = make_plots()

    print('AA2024-T351 simulation/postprocessing complete.')
    print(f'Case: {CASE}')
    print(f'Input folder: simulation_inputs/AL2024-T351')
    print(f'STA success: {sta}')
    print(f'ODB: {odb} ({odb.stat().st_size} bytes)')
    print(f'CSV: {RESULT_CSV} ({rows} rows)')
    print(f'Final row: {last}')
    print(f'AA2024 reference area: {ref_area:.6f}')
    print(f'Simulation area: {sim_area:.6f}')
    print(f'MEDIA:{aa2024_plot}')
    print(f'MEDIA:{cycles_plot}')

if __name__ == '__main__':
    main()
