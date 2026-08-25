from pathlib import Path
import csv
import json
import os
import random
import re
import shutil
import sys
from datetime import datetime

REPO = Path('/home/joules_gf/projects/dr-irwin-hermes/workspace/microstructure_fatigue_simulation')
STATE_PATH = REPO / 'simulation_outputs' / 'aa2024_adaptive_yield_loop_state.json'
INPUT_FOLDER = REPO / 'simulation_inputs' / 'AL2024-T351'
REF_CSV = REPO / '00_Main_Scripts' / 'material_reference_curves' / 'aa2024-T351_monotonic_ROM_1pct_strain.csv'
TEMPLATE_INP = REPO / 'simulation_outputs' / 'aa2024-t351-p350-375-410-460-vf10-10-40-40' / 'abaqus_files' / 'aa2024-t351-p350-375-410-460-vf10-10-40-40.inp'
PHASE0 = 350
FRACTIONS = [0.10, 0.10, 0.40, 0.40]
MAX_ITERATIONS = 10
LOWER_BOUNDS = [PHASE0, 300, 300, 300]
UPPER_BOUNDS = [PHASE0, 650, 650, 650]

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


def reference_area():
    xs, ys = read_xy(REF_CSV, 0, 1)
    return area(xs, ys)


def load_state(ref_area):
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    # Starts from the manually verified simulation already sent in chat.
    return {
        'iteration': 0,
        'reference_area': ref_area,
        'previous_values': [350, 375, 410, 460],
        'previous_area': 2.882517,
        'history': [
            {
                'iteration': 0,
                'case': 'aa2024-t351-p350-375-410-460-vf10-10-40-40',
                'values': [350, 375, 410, 460],
                'area': 2.882517,
                'note': 'seed case completed before adaptive loop'
            }
        ]
    }


def choose_next_values(previous_values, previous_area, ref_area):
    direction = 1 if previous_area < ref_area else -1
    gap = abs(ref_area - previous_area)
    # Keep jumps modest near the target; use larger random moves when clearly below/above.
    if gap > 0.08:
        lo, hi = 10, 28
    elif gap > 0.035:
        lo, hi = 5, 18
    else:
        lo, hi = 2, 10
    values = [PHASE0]
    for phase_idx in [1, 2, 3]:
        delta = random.randint(lo, hi)
        proposed = int(previous_values[phase_idx] + direction * delta)
        proposed = max(LOWER_BOUNDS[phase_idx], min(UPPER_BOUNDS[phase_idx], proposed))
        # Enforce strictly higher/lower than previous unless at the bound.
        if direction > 0 and proposed <= previous_values[phase_idx] and previous_values[phase_idx] < UPPER_BOUNDS[phase_idx]:
            proposed = previous_values[phase_idx] + 1
        if direction < 0 and proposed >= previous_values[phase_idx] and previous_values[phase_idx] > LOWER_BOUNDS[phase_idx]:
            proposed = previous_values[phase_idx] - 1
        values.append(proposed)
    return values, ('higher' if direction > 0 else 'lower')


def case_name(iteration, values):
    return f'aa2024-adaptive-{iteration:02d}-p{values[0]}-{values[1]}-{values[2]}-{values[3]}'


def write_provenance_xml(case, values):
    mesh_xml = INPUT_FOLDER / f'{case}_mesh.xml'
    input_xml = INPUT_FOLDER / f'{case}.xml'
    mesh_xml.write_text(f'''<input>
    <domain>
        <shape> square </shape>
        <side_length> 1 </side_length>
    </domain>

    <material>
        <name> Phase-0 </name>
        <shape> circle </shape>
        <fraction> 0.10 </fraction>
        <size><dist_type> uniform </dist_type><loc> 0.05 </loc></size>
    </material>
    <material>
        <name> Phase-1 </name>
        <shape> circle </shape>
        <fraction> 0.10 </fraction>
        <size><dist_type> uniform </dist_type><loc> 0.05 </loc></size>
    </material>
    <material>
        <name> Phase-2 </name>
        <shape> circle </shape>
        <fraction> 0.40 </fraction>
        <size><dist_type> uniform </dist_type><loc> 0.05 </loc></size>
    </material>
    <material>
        <name> Phase-3 </name>
        <shape> circle </shape>
        <fraction> 0.40 </fraction>
        <size><dist_type> uniform </dist_type><loc> 0.05 </loc></size>
    </material>
</input>
''')
    input_xml.write_text(f'''<input>
    <include> {case}_mesh.xml </include>

    <abaqus>
        <E> 73100 </E>
        <nu> 0.33 </nu>
        <displacement_yy> 0.01 </displacement_yy>
        <plastic_stresses> {values[0]}, {values[1]}, {values[2]}, {values[3]} </plastic_stresses>
    </abaqus>

    <settings>
        <verbose> False </verbose>
        <restart> False </restart>
        <mesh_min_angle> 25 </mesh_min_angle>
        <mesh_max_edge_length> 0.00328 </mesh_max_edge_length>
        <rng_seeds><size> 1000 </size></rng_seeds>
        <filetypes><seeds> txt </seeds><poly> txt </poly><tri> txt </tri></filetypes>
    </settings>
</input>
''')
    return input_xml, mesh_xml


def make_case_inp(case, values):
    if not TEMPLATE_INP.exists():
        raise RuntimeError(f'Missing template INP: {TEMPLATE_INP}')
    case_dir = REPO / 'simulation_outputs' / case
    abaqus_dir = case_dir / 'abaqus_files'
    if case_dir.exists():
        shutil.rmtree(case_dir)
    abaqus_dir.mkdir(parents=True)
    text = TEMPLATE_INP.read_text(errors='ignore')
    # Replace the four plastic values in order, preserving the rest of the fixed mesh/input deck.
    parts = text.splitlines()
    plastic_count = 0
    for i, line in enumerate(parts):
        if line.strip().lower() == '*plastic':
            parts[i + 1] = f' {values[plastic_count]}, 0.0'
            plastic_count += 1
    if plastic_count != 4:
        raise RuntimeError(f'Expected 4 *Plastic blocks, found {plastic_count}')
    out_inp = abaqus_dir / f'{case}.inp'
    out_inp.write_text('\n'.join(parts) + '\n')
    return case_dir, abaqus_dir, out_inp


def make_plots(case, case_dir, result_csv):
    import pandas as pd
    import matplotlib.pyplot as plt
    from PIL import Image

    ref_x, ref_y = read_xy(REF_CSV, 0, 1)
    sim_x, sim_y = read_xy(result_csv, 1, 2)
    ref_area = area(ref_x, ref_y)
    sim_area = area(sim_x, sim_y)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.plot(ref_x, ref_y, label=f'AA2024-T351 R-O reference (Area = {ref_area:.3f})', linewidth=3, linestyle='--', color='black')
    ax.plot(sim_x, sim_y, label=f'{case} (Area = {sim_area:.3f})', linewidth=2, color='red')
    ax.set_xlabel('Strain')
    ax.set_ylabel('Stress (MPa)')
    ax.set_title(f'{case} vs AA2024-T351 Reference')
    ax.grid(True)
    ax.legend(fontsize=8)
    fig.tight_layout()
    comparison_png = case_dir / f'stress_strain_{case}_AA2024_T351_reference.png'
    fig.savefig(comparison_png)
    plt.close(fig)

    df = pd.read_csv(result_csv, skiprows=1)
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.plot(df['Step Time'], df['U_Y'], marker='o', linestyle='-')
    ax.set_xlabel('Step Time (s)')
    ax.set_ylabel('Displacement (mm)')
    ax.set_title(f"Simulation '{case}' Displacement vs Step Time")
    ax.grid(True)
    fig.tight_layout()
    cycles_png = case_dir / f'cycles_{case}.png'
    fig.savefig(cycles_png)
    plt.close(fig)

    # Verify image readability/dimensions.
    dims = {}
    for png in (comparison_png, cycles_png):
        with Image.open(png) as im:
            dims[str(png)] = im.size
    return comparison_png, cycles_png, sim_area, ref_area, len(df), df.iloc[-1].to_dict(), dims


def main():
    from run_abaqus_sim import run_simulation
    from postprocessing_abaqus_sim_v01 import extract_force_displacement

    random.seed(datetime.now().isoformat())
    ref_area = reference_area()
    state = load_state(ref_area)
    iteration = int(state['iteration']) + 1
    if iteration > MAX_ITERATIONS:
        print(f'AA2024 adaptive loop is already complete: {MAX_ITERATIONS} simulations recorded.')
        print(f'State file: {STATE_PATH}')
        return

    previous_values = state['previous_values']
    previous_area = float(state['previous_area'])
    values, direction_label = choose_next_values(previous_values, previous_area, ref_area)
    case = case_name(iteration, values)

    input_xml, mesh_xml = write_provenance_xml(case, values)
    case_dir, abaqus_dir, inp = make_case_inp(case, values)

    print(f'AA2024 adaptive yield loop — simulation {iteration}/{MAX_ITERATIONS}', flush=True)
    print(f'Previous area: {previous_area:.6f}; AA2024 ROM area: {ref_area:.6f}; choosing {direction_label} phase 1-3 values.', flush=True)
    print(f'Yield stresses MPa: Phase 0={values[0]}, Phase 1={values[1]}, Phase 2={values[2]}, Phase 3={values[3]}', flush=True)
    print(f'Input XML: {input_xml}', flush=True)
    print(f'Abaqus INP: {inp}', flush=True)

    run_simulation(str(abaqus_dir), case)
    sta = abaqus_dir / f'{case}.sta'
    odb = abaqus_dir / f'{case}.odb'
    msg = abaqus_dir / f'{case}.msg'
    if sta.exists():
        sta_text = sta.read_text(errors='ignore')
        success = 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in sta_text
    else:
        msg_text = msg.read_text(errors='ignore') if msg.exists() else ''
        success = 'THE ANALYSIS HAS BEEN COMPLETED' in msg_text
    if not success or not odb.exists():
        raise RuntimeError(f'Abaqus verification failed for {case}: success={success}, odb={odb.exists()}, sta={sta.exists()}')

    extract_force_displacement(str(abaqus_dir), case)
    result_csv = case_dir / f'{case}.csv'
    if not result_csv.exists():
        raise RuntimeError(f'Missing extracted CSV: {result_csv}')

    comparison_png, cycles_png, sim_area, ref_area, rows, last, dims = make_plots(case, case_dir, result_csv)
    delta = sim_area - ref_area
    pct = 100 * delta / ref_area
    state.update({
        'iteration': iteration,
        'reference_area': ref_area,
        'previous_values': values,
        'previous_area': sim_area,
    })
    state.setdefault('history', []).append({
        'iteration': iteration,
        'case': case,
        'values': values,
        'area': sim_area,
        'area_delta': delta,
        'area_delta_percent': pct,
        'csv': str(result_csv),
        'plot': str(comparison_png),
    })
    STATE_PATH.write_text(json.dumps(state, indent=2))

    relation = 'LESS THAN' if sim_area < ref_area else 'MORE THAN'
    next_direction = 'higher' if sim_area < ref_area else 'lower'
    print('\nAA2024 adaptive yield result', flush=True)
    print(f'Case: {case}', flush=True)
    print(f'Yield stresses MPa: P0={values[0]}, P1={values[1]}, P2={values[2]}, P3={values[3]}', flush=True)
    print(f'AA2024 ROM area: {ref_area:.6f}', flush=True)
    print(f'Simulation area: {sim_area:.6f}', flush=True)
    print(f'Delta vs ROM: {delta:+.6f} ({pct:+.2f}%) — simulation area is {relation} the AA2024 reference.', flush=True)
    print(f'Next adaptive direction: random but {next_direction} values for phases 1-3; phase 0 remains 350 MPa.', flush=True)
    print(f'Final row: {last}', flush=True)
    print(f'CSV rows: {rows}', flush=True)
    print(f'ODB: {odb} ({odb.stat().st_size} bytes)', flush=True)
    print(f'Plot dimensions: {dims[str(comparison_png)]}', flush=True)
    print(f'State file: {STATE_PATH}', flush=True)
    print(f'MEDIA:{comparison_png}', flush=True)
    print(f'MEDIA:{cycles_png}', flush=True)


if __name__ == '__main__':
    main()
