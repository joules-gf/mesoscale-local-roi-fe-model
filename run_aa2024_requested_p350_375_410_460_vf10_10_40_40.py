from pathlib import Path
import os
import sys
import csv

REPO = Path('/home/joules_gf/projects/dr-irwin-hermes/workspace/microstructure_fatigue_simulation')
CASE = 'aa2024-t351-p350-375-410-460-vf10-10-40-40'
INPUT_FOLDER = REPO / 'simulation_inputs' / 'AL2024-T351'
INPUT_FILE = INPUT_FOLDER / f'{CASE}.xml'
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


def make_aa2024_plots(case_dir, result_csv):
    import pandas as pd
    import matplotlib.pyplot as plt

    ref_strain, ref_stress = read_csv_xy(REF_CSV, 0, 1)
    sim_strain, sim_stress = read_csv_xy(result_csv, 1, 2)
    if not ref_strain or not sim_strain:
        raise RuntimeError('Could not load reference or simulation CSV data for plotting')

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
    aa2024_plot = case_dir / f'stress_strain_{CASE}_AA2024_T351_reference.png'
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
    cycles_plot = case_dir / f'cycles_{CASE}.png'
    fig.savefig(cycles_plot)
    plt.close(fig)

    return aa2024_plot, cycles_plot, sim_area, ref_area, len(df), df.iloc[-1].to_dict()


def main():
    from abaqus_input_generation_v02 import generate_input
    from run_abaqus_sim import run_simulation
    from postprocessing_abaqus_sim_v01 import extract_force_displacement

    print('REQUESTED AA2024 FULL CYCLE START', flush=True)
    print('Parameters: Phase 0 350 MPa 10%; Phase 1 375 MPa 10%; Phase 2 410 MPa 40%; Phase 3 460 MPa 40%', flush=True)
    print(f'Input file: {INPUT_FILE}', flush=True)
    abaqus_dir_str, sim_name = generate_input(str(INPUT_FOLDER), input_file=str(INPUT_FILE))
    if sim_name != CASE:
        raise RuntimeError(f'Unexpected simulation name {sim_name}, expected {CASE}')
    abaqus_dir = Path(abaqus_dir_str)
    case_dir = abaqus_dir.parent
    print(f'Generated Abaqus directory: {abaqus_dir}', flush=True)

    run_simulation(str(abaqus_dir), CASE)
    print('Abaqus run finished; verifying .sta/.odb', flush=True)
    sta = abaqus_dir / f'{CASE}.sta'
    odb = abaqus_dir / f'{CASE}.odb'
    if not sta.exists() or not odb.exists():
        raise RuntimeError(f'Missing Abaqus artifacts: sta={sta.exists()} odb={odb.exists()}')
    sta_text = sta.read_text(errors='ignore')
    if 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta_text:
        raise RuntimeError('Abaqus .sta did not contain successful completion line')

    print('Extracting force-displacement from ODB', flush=True)
    extract_force_displacement(str(abaqus_dir), CASE)
    result_csv = case_dir / f'{CASE}.csv'
    if not result_csv.exists():
        raise RuntimeError(f'Missing extracted CSV: {result_csv}')

    aa2024_plot, cycles_plot, sim_area, ref_area, rows, last = make_aa2024_plots(case_dir, result_csv)
    print('REQUESTED AA2024 FULL CYCLE COMPLETE', flush=True)
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
