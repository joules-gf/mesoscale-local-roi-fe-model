"""Portable sequential 20-case matched-normal size-RNG batch with archive-aware resume."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from rng_result_locations import case_directory

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / 'simulation_inputs/Normal Distribution/size-rng-position1000-matched-uniform'
UNIFORM = ROOT / 'simulation_inputs/Uniform Distribution/size-rng-position1000'
BATCH = ROOT / 'simulation_outputs/normal_matched_size_rng_position1000_batch'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def controls(root):
    values = []
    def walk(element, prefix=''):
        path = prefix + '/' + element.tag
        if path == '/input/material/size':
            return
        values.append((path, (element.text or '').strip(), sorted(element.attrib.items())))
        for child in element:
            walk(child, path)
    walk(root)
    return values


def load_cases():
    with (INPUTS / 'manifest.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 20 or [r['size_seed'] for r in rows] != [str(i) for i in range(1, 21)]:
        raise ValueError('Require exactly 20 ordered size seeds, 1-20')
    if {p.name for p in INPUTS.glob('*.xml')} != {r['input_file'] for r in rows}:
        raise ValueError('Manifest/XML set mismatch')
    for seed, row in enumerate(rows, 1):
        case = f'normal_matched_size_rng_{seed:04d}_pos1000'
        original = f'uniform_size_rng_{seed:04d}_pos1000'
        if row['case'] != case or row['input_file'] != case + '.xml' or row['source_uniform_case'] != original or row['position_seed'] != '1000':
            raise ValueError('Invalid case/seed identity')
        root = ET.parse(INPUTS / row['input_file']).getroot()
        source = ET.parse(UNIFORM / (original + '.xml')).getroot()
        if controls(root) != controls(source):
            raise ValueError('Non-distribution controls differ from uniform counterpart')
        if root.findtext('settings/restart', '').strip().lower() != 'false':
            raise ValueError('Require fresh restart=False')
        rng = root.find('settings/rng_seeds')
        if rng is None or {e.tag: (e.text or '').strip() for e in rng} != {'position': '1000', 'size': str(seed)}:
            raise ValueError('Unexpected RNG settings')
        phases, original_phases = root.findall('material'), source.findall('material')
        if len(phases) != 4 or len(original_phases) != 4:
            raise ValueError('Require four phases')
        for phase, old in zip(phases, original_phases):
            a = float(old.findtext('size/loc', 'nan'))
            w = float(old.findtext('size/scale')) if old.find('size/scale') is not None else .2 * a
            mu, sigma = a + w / 2, w / math.sqrt(12)
            if old.findtext('size/dist_type', '').strip() != 'uniform' or not math.isclose(a, .05) or not math.isclose(w, .01):
                raise ValueError('Unexpected source uniform parameters')
            if phase.findtext('size/dist_type', '').strip() != 'norm' or not math.isclose(float(phase.findtext('size/loc', 'nan')), mu, rel_tol=1e-13) or not math.isclose(float(phase.findtext('size/scale', 'nan')), sigma, rel_tol=1e-13):
                raise ValueError('Normal moments do not match uniform')
            for key, expected in [('uniform_lower_bound_mm', a), ('uniform_width_mm', w), ('normal_mean_mm', mu), ('normal_std_mm', sigma)]:
                if not math.isclose(float(row[key]), expected, rel_tol=1e-13):
                    raise ValueError('Manifest parameter mismatch: ' + key)
    return rows


def artifacts_ok(case):
    dest = case_directory(ROOT, case)
    sta, curve = dest / 'abaqus_files' / (case + '.sta'), dest / (case + '.csv')
    if not sta.exists() or 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta.read_text(errors='replace').upper() or not curve.exists():
        return False
    numeric_rows = 0
    with curve.open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.reader(stream):
            try:
                strain, stress = float(row[1]), float(row[2])
            except (ValueError, IndexError):
                continue
            numeric_rows += math.isfinite(strain) and math.isfinite(stress)
    return numeric_rows >= 2


def verify_inputs(rows):
    sys.path.insert(0, str(ROOT / '00_Main_Scripts'))
    from abaqus_input_generation_v02 import complete_input_data
    for row in rows:
        completed = []
        try:
            for path in (UNIFORM / (row['source_uniform_case'] + '.xml'), INPUTS / row['input_file']):
                completed.append(complete_input_data(str(path)))
            old, new = [result[0] for result in completed]
            assert old[2]['rng_seeds'] == new[2]['rng_seeds'] == {'position': 1000, 'size': int(row['size_seed'])}
            for u, n in zip(old[1], new[1]):
                assert u['size'].dist.name == 'uniform' and n['size'].dist.name == 'norm'
                assert math.isclose(u['size'].mean(), n['size'].mean(), rel_tol=1e-13)
                assert math.isclose(u['size'].std(), n['size'].std(), rel_tol=1e-13)
            print('[VERIFIED]', row['case'], 'size seed', row['size_seed'], flush=True)
        finally:
            for result in completed:
                Path(result[-1]).unlink(missing_ok=True)
    print('[OK] Runtime distributions verified for all 20 cases; no mesh/solver launched.', flush=True)


def run_case(row):
    """Child-only pipeline; force batch plotting even with older tracked postprocessing."""
    os.environ.update(MPLBACKEND='Agg', MICROSTRUCTURE_NONINTERACTIVE='1', PYTHONIOENCODING='utf-8')
    import matplotlib
    matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt
    # Legacy postprocessing may call show() before savefig(). Do not close here:
    # suppress show for this child process, then close after all figures save.
    plt.show = lambda *args, **kwargs: None
    sys.path.insert(0, str(ROOT / '00_Main_Scripts'))
    from full_simulation_runner import run_full_simulation
    try:
        run_full_simulation(input_files_folder=str(INPUTS), input_file=str(INPUTS / row['input_file']))
    finally:
        plt.close('all')


def run_batch(rows):
    BATCH.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(MPLBACKEND='Agg', MICROSTRUCTURE_NONINTERACTIVE='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    fields = ['case', 'size_seed', 'position_seed', 'normal_mean_mm', 'normal_std_mm', 'started_utc', 'elapsed_seconds', 'status', 'returncode', 'log']
    for row in rows:
        case = row['case']
        fingerprint = digest(INPUTS / row['input_file'])
        marker = BATCH / (case + '.completed.json')
        if marker.exists():
            saved = json.loads(marker.read_text(encoding='utf-8'))
            if saved.get('input_sha256') != fingerprint or saved.get('status') != 'completed' or not artifacts_ok(case):
                raise RuntimeError('Completion record/artifacts mismatch: ' + case)
            print('[SKIP]', case, flush=True)
            continue
        if (ROOT / 'simulation_outputs' / case).exists():
            raise RuntimeError('Unrecorded output already exists; inspect/archive it manually before retrying: ' + case)
        log = BATCH / (case + '.log')
        command = [sys.executable, '-u', str(Path(__file__).resolve().relative_to(ROOT)), '--run-case', row['input_file']]
        start, clock = datetime.now(timezone.utc).isoformat(), time.perf_counter()
        print('[START]', case, 'log:', log, flush=True)
        with log.open('w', encoding='utf-8') as stream:
            with subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1) as process:
                assert process.stdout is not None
                for line in process.stdout:
                    stream.write(line)
                    stream.flush()
                    print(line, end='', flush=True)
                returncode = process.wait()
        success = returncode == 0 and artifacts_ok(case)
        report = {key: row[key] for key in fields[:5]}
        report.update(started_utc=start, elapsed_seconds=round(time.perf_counter() - clock, 3), status='completed' if success else 'failed', returncode=returncode, log=str(log.relative_to(ROOT)))
        summary = BATCH / 'runtime_summary.csv'
        exists = summary.exists()
        with summary.open('a', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            if not exists:
                writer.writeheader()
            writer.writerow(report)
        if not success:
            raise RuntimeError(f'Batch stopped at {case}; inspect {log}')
        marker.write_text(json.dumps({'input_sha256': fingerprint, **report}, indent=2) + '\n', encoding='utf-8')
        print('[DONE]', case, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--dry-run', action='store_true')
    modes.add_argument('--verify-inputs', action='store_true', help='Exercise runtime input completion only; no meshing/solver')
    modes.add_argument('--run-case', help=argparse.SUPPRESS)
    args = parser.parse_args()
    rows = load_cases()
    if args.run_case:
        selected = [r for r in rows if r['input_file'] == args.run_case]
        if len(selected) != 1:
            parser.error('Case must be one of the 20 manifest input filenames')
        run_case(selected[0])
        return
    if args.verify_inputs:
        verify_inputs(rows)
        return
    for index, row in enumerate(rows, 1):
        print(f"{index:02d}: {row['case']} size={row['size_seed']} position={row['position_seed']}", flush=True)
    if args.dry_run:
        print('[OK] 20 inputs validated; no output writes or solver launch.', flush=True)
        return
    BATCH.mkdir(parents=True, exist_ok=True)
    lock = BATCH / 'RUNNING.lock'
    try:
        with lock.open('x', encoding='utf-8') as stream:
            stream.write(str(os.getpid()))
    except FileExistsError:
        raise RuntimeError('Batch lock exists; inspect active/stale batch before retrying') from None
    try:
        run_batch(rows)
        (BATCH / 'COMPLETED.txt').write_text('All 20 matched-normal size-RNG cases verified completed.\n', encoding='utf-8')
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
