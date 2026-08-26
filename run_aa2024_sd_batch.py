from pathlib import Path
import os
import sys
import csv
import subprocess

REPO = Path('/home/joules_gf/projects/dr-irwin-hermes/workspace/mesoscale-local-roi-fe-model')
INPUT_FOLDER = REPO / 'simulation_inputs' / 'AL2024-T351'
CASES = ['aa2024-t351-2sd', 'aa2024-t351-3sd', 'aa2024-t351-1p5sd']
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
    total = 0.0
    for i in range(1, len(xs)):
        total += (xs[i] - xs[i - 1]) * (ys[i] + ys[i - 1]) / 2
    return total


def make_aa2024_plots(case, case_dir, result_csv):
    import pandas as pd
    import matplotlib.pyplot as plt

    ref_strain, ref_stress = read_csv_xy(REF_CSV, 0, 1)
    sim_strain, sim_stress = read_csv_xy(result_csv, 1, 2)
    if not ref_strain or not sim_strain:
        raise RuntimeError(f'Could not load reference or simulation CSV data for {case}')

    ref_area = area(ref_strain, ref_stress)
    sim_area = area(sim_strain, sim_stress)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.plot(ref_strain, ref_stress, label=f'AA2024-T351 R-O reference (Area = {ref_area:.3f})', linewidth=3, linestyle='--', color='black')
    ax.plot(sim_strain, sim_stress, label=f'{case} (Area = {sim_area:.3f})', linewidth=2, color='red')
    ax.set_xlabel('Strain')
    ax.set_ylabel('Stress (MPa)')
    ax.set_title(f'{case} vs AA2024-T351 Reference')
    ax.grid(True)
    ax.legend()
    fig.tight_layout()
    aa2024_plot = case_dir / f'stress_strain_{case}_AA2024_T351_reference.png'
    fig.savefig(aa2024_plot)
    plt.close(fig)

    df = pd.read_csv(result_csv, skiprows=1)
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.plot(df['Step Time'], df['U_Y'], marker='o', linestyle='-')
    ax.set_xlabel('Step Time (s)')
    ax.set_ylabel('Displacement (mm)')
    ax.set_title(f"Simulation '{case}' Displacement vs Step Time")
    ax.grid(True)
    fig.tight_layout()
    cycles_plot = case_dir / f'cycles_{case}.png'
    fig.savefig(cycles_plot)
    plt.close(fig)

    return aa2024_plot, cycles_plot, sim_area, ref_area, len(df), df.iloc[-1].to_dict()


def run_case(case):
    from abaqus_input_generation_v02 import generate_input
    from run_abaqus_sim import run_simulation
    from postprocessing_abaqus_sim_v01 import extract_force_displacement

    print(f'=== START {case} ===', flush=True)
    input_file = INPUT_FOLDER / f'{case}.xml'
    abaqus_dir_str, sim_name = generate_input(str(INPUT_FOLDER), input_file=str(input_file))
    if sim_name != case:
        raise RuntimeError(f'Unexpected simulation name {sim_name}, expected {case}')
    abaqus_dir = Path(abaqus_dir_str)
    case_dir = abaqus_dir.parent
    print(f'Generated Abaqus directory: {abaqus_dir}', flush=True)

    run_simulation(str(abaqus_dir), case)
    sta = abaqus_dir / f'{case}.sta'
    odb = abaqus_dir / f'{case}.odb'
    if not sta.exists() or not odb.exists():
        raise RuntimeError(f'Missing Abaqus artifacts for {case}: sta={sta.exists()} odb={odb.exists()}')
    if 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta.read_text(errors='ignore'):
        raise RuntimeError(f'Abaqus .sta did not contain successful completion line for {case}')

    extract_force_displacement(str(abaqus_dir), case)
    result_csv = case_dir / f'{case}.csv'
    if not result_csv.exists():
        raise RuntimeError(f'Missing extracted CSV for {case}: {result_csv}')

    aa2024_plot, cycles_plot, sim_area, ref_area, rows, last = make_aa2024_plots(case, case_dir, result_csv)
    print(f'=== COMPLETE {case} ===', flush=True)
    print(f'Case: {case}', flush=True)
    print(f'ODB: {odb} ({odb.stat().st_size} bytes)', flush=True)
    print(f'CSV: {result_csv} ({rows} rows)', flush=True)
    print(f'Final row: {last}', flush=True)
    print(f'AA2024 reference area: {ref_area:.6f}', flush=True)
    print(f'Simulation area: {sim_area:.6f}', flush=True)
    print(f'MEDIA:{aa2024_plot}', flush=True)
    print(f'MEDIA:{cycles_plot}', flush=True)
    return case


def main():
    print('AA2024 standard-deviation batch start', flush=True)
    completed = []
    for case in CASES:
        completed.append(run_case(case))
    print('AA2024 standard-deviation batch complete:', ', '.join(completed), flush=True)


if __name__ == '__main__':
    main()
