from pathlib import Path
import csv
import os
import sys

REPO = Path('/home/joules_gf/projects/dr-irwin-hermes/workspace/microstructure_fatigue_simulation')
CASE = 'aa2024-vf15-10-30-45-p325-400-500-600'
INPUT_XML = REPO / 'simulation_inputs' / 'AL2024-T351' / f'{CASE}.xml'
CASE_DIR = REPO / 'simulation_outputs' / CASE
ABAQUS_DIR = CASE_DIR / 'abaqus_files'
REF_CSV = REPO / '00_Main_Scripts' / 'material_reference_curves' / 'aa2024-T351_monotonic_ROM_1pct_strain.csv'

os.environ['MPLBACKEND'] = 'Agg'
os.environ['MICROSTRUCTURE_NONINTERACTIVE'] = '1'
sys.path.insert(0, str(REPO / '00_Main_Scripts'))


def read_xy(path, xcol, ycol):
    xs, ys = [], []
    with open(path, newline='') as f:
        for row in csv.reader(f):
            try:
                xs.append(float(row[xcol]))
                ys.append(float(row[ycol]))
            except Exception:
                continue
    return xs, ys


def area(xs, ys):
    return sum((xs[i] - xs[i - 1]) * (ys[i] + ys[i - 1]) / 2 for i in range(1, len(xs)))


def make_plots(result_csv):
    import pandas as pd
    import matplotlib.pyplot as plt
    from PIL import Image

    ref_x, ref_y = read_xy(REF_CSV, 0, 1)
    sim_x, sim_y = read_xy(result_csv, 1, 2)
    ref_area = area(ref_x, ref_y)
    sim_area = area(sim_x, sim_y)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.plot(ref_x, ref_y, label=f'AA2024-T351 R-O reference (Area = {ref_area:.3f})', linewidth=3, linestyle='--', color='black')
    ax.plot(sim_x, sim_y, label=f'{CASE} (Area = {sim_area:.3f})', linewidth=2, color='red')
    ax.set_xlabel('Strain')
    ax.set_ylabel('Stress (MPa)')
    ax.set_title(f'{CASE} vs AA2024-T351 Reference')
    ax.grid(True)
    ax.legend(fontsize=8)
    fig.tight_layout()
    comparison_png = CASE_DIR / f'stress_strain_{CASE}_AA2024_T351_reference.png'
    fig.savefig(comparison_png)
    plt.close(fig)

    df = pd.read_csv(result_csv, skiprows=1)
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.plot(df['Step Time'], df['U_Y'], marker='o', linestyle='-')
    ax.set_xlabel('Step Time (s)')
    ax.set_ylabel('Displacement (mm)')
    ax.set_title(f"Simulation '{CASE}' Displacement vs Step Time")
    ax.grid(True)
    fig.tight_layout()
    cycles_png = CASE_DIR / f'cycles_{CASE}.png'
    fig.savefig(cycles_png)
    plt.close(fig)

    comparison_size = Image.open(comparison_png).size
    cycles_size = Image.open(cycles_png).size
    return comparison_png, cycles_png, comparison_size, cycles_size, ref_area, sim_area, len(df), df.iloc[-1].to_dict()


def main():
    from full_simulation_runner import run_full_simulation
    from postprocessing_abaqus_sim_v01 import extract_force_displacement

    print('AA2024 requested VF/yield case start', flush=True)
    print(f'Input XML: {INPUT_XML}', flush=True)
    print('VF: [0.15, 0.10, 0.30, 0.45]', flush=True)
    print('Yield MPa: [325, 400, 500, 600]', flush=True)
    print('Reference material: AA2024-T351', flush=True)

    if not INPUT_XML.exists():
        raise RuntimeError(f'Missing input XML: {INPUT_XML}')

    sta = ABAQUS_DIR / f'{CASE}.sta'
    odb = ABAQUS_DIR / f'{CASE}.odb'
    result_csv = CASE_DIR / f'{CASE}.csv'

    if not (sta.exists() and odb.exists() and 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in sta.read_text(errors='ignore')):
        run_full_simulation(
            input_files_folder=str(INPUT_XML.parent),
            input_file=str(INPUT_XML),
            run_abaqus=True,
            run_postprocessing=False,
        )
    else:
        print('Abaqus run already complete; skipping solver.', flush=True)

    if not sta.exists() or 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta.read_text(errors='ignore'):
        raise RuntimeError(f'Abaqus did not complete successfully. Check {sta}')
    if not odb.exists():
        raise RuntimeError(f'Missing ODB: {odb}')

    extract_force_displacement(str(ABAQUS_DIR), CASE)
    if not result_csv.exists():
        raise RuntimeError(f'Missing extracted CSV: {result_csv}')

    comparison_png, cycles_png, comparison_size, cycles_size, ref_area, sim_area, rows, final_row = make_plots(result_csv)

    print('AA2024 requested VF/yield case complete', flush=True)
    print(f'Case: {CASE}', flush=True)
    print(f'STA: {sta}', flush=True)
    print(f'ODB: {odb} ({odb.stat().st_size} bytes)', flush=True)
    print(f'CSV: {result_csv}', flush=True)
    print(f'CSV rows: {rows}', flush=True)
    print(f'Final row: {final_row}', flush=True)
    print(f'AA2024 reference area: {ref_area:.6f}', flush=True)
    print(f'Simulation area: {sim_area:.6f}', flush=True)
    print(f'Delta vs reference: {sim_area - ref_area:+.6f} ({((sim_area - ref_area) / ref_area) * 100:+.2f}%)', flush=True)
    print(f'Plot dimensions: comparison={comparison_size}, cycles={cycles_size}', flush=True)
    print(f'MEDIA:{comparison_png}', flush=True)
    print(f'MEDIA:{cycles_png}', flush=True)


if __name__ == '__main__':
    main()
