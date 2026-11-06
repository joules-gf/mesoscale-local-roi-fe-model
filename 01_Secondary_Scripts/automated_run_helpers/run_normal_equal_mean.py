"""Run the 21 normal equal-mean inputs largest-to-smallest, one at a time."""
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

# Support direct execution and importlib standalone loading.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from normal_result_paths import resolve_case_folder

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / 'simulation_inputs/Normal Distribution/bp-equal-mean-4all-phases'
BATCH = ROOT / 'simulation_outputs/normal_equal_mean_batch'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases():
    files = list(INPUTS.glob('*.xml'))
    expected = {f'bp_same_size_case_{i:02d}' for i in range(1, 21)} | {'bp_same_size_baseline_0p050'}
    if {p.stem for p in files} != expected:
        raise RuntimeError('Expected precisely 20 cases and the 0.050 baseline')
    rows = []
    for path in files:
        root = ET.parse(path).getroot()
        sizes = root.findall('material/size')
        if len(sizes) != 4 or any(s.findtext('dist_type', '').strip() != 'norm' or s.find('scale') is not None for s in sizes):
            raise RuntimeError(f'Expected four normal distributions with automatic scale: {path}')
        means = [float(s.findtext('loc')) for s in sizes]
        if len(set(means)) != 1 or not math.isfinite(means[0]) or means[0] <= 0:
            raise RuntimeError(f'Invalid common mean: {path}')
        rows.append({'case': path.stem, 'input': str(path.relative_to(ROOT)), 'mean_mm': means[0], 'input_sha256': digest(path)})
    return sorted(rows, key=lambda r: r['mean_mm'], reverse=True)


def configure_plotting():
    import matplotlib
    matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt
    # Legacy postprocessing shows BEFORE saving; do not close in this replacement.
    plt.show = lambda *args, **kwargs: None
    return plt


def verify_inputs(rows):
    sys.path.insert(0, str(ROOT / '00_Main_Scripts'))
    from abaqus_input_generation_v02 import complete_input_data
    plt = configure_plotting()
    for row in rows:
        result = complete_input_data(str(ROOT / row['input']))
        try:
            _, phases, settings, _ = result[0]
            assert result[1] == row['case']
            for phase in phases:
                distribution = phase['size']
                assert distribution.dist.name == 'norm'
                assert math.isclose(distribution.mean(), row['mean_mm'])
                assert math.isclose(distribution.std(), 0.2 * row['mean_mm'])
            assert settings['rng_seeds']['size'] == 1000
        finally:
            Path(result[-1]).unlink(missing_ok=True)
    figure = plt.figure()
    plt.show()
    assert plt.fignum_exists(figure.number), 'Suppressed show must preserve figures for saving'
    plt.close('all')
    print(f'[OK] All {len(rows)} runtime inputs verified: norm, original means, std=0.2*mean, size RNG=1000; nonblocking plot guard verified.', flush=True)


def run_child(path):
    sys.path.insert(0, str(ROOT / '00_Main_Scripts'))
    plt = configure_plotting()
    from full_simulation_runner import run_full_simulation
    try:
        run_full_simulation(input_file=str(path))
    finally:
        plt.close('all')


def artifacts_ok(case):
    dest = resolve_case_folder(ROOT, case)
    sta = dest / 'abaqus_files' / (case + '.sta')
    curve = dest / (case + '.csv')
    if not sta.is_file() or 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta.read_text(errors='replace').upper() or not curve.is_file():
        return False
    numeric = 0
    with curve.open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.reader(stream):
            try:
                values = [float(row[i]) for i in (0, 1, 2)]
            except (ValueError, IndexError):
                continue
            if not all(math.isfinite(x) for x in values):
                return False
            numeric += 1
    resolved = dest / (case + '_resolved_input.xml')
    if not resolved.is_file():
        return False
    sizes = ET.parse(resolved).findall('material/size')
    return numeric >= 2 and len(sizes) == 4 and all(s.findtext('dist_type', '').strip() == 'norm' for s in sizes)


def preflight(rows):
    for row in rows:
        marker = BATCH / (row['case'] + '.completed.json')
        dest = resolve_case_folder(ROOT, row['case'])
        if marker.exists():
            saved = json.loads(marker.read_text())
            if saved.get('input_sha256') != row['input_sha256'] or saved.get('returncode') != 0 or not artifacts_ok(row['case']):
                raise RuntimeError('Invalid previous completion: ' + row['case'])
        elif dest.exists():
            raise RuntimeError('Refusing existing unrecorded output: ' + str(dest))


def run_batch(rows):
    BATCH.mkdir(parents=True, exist_ok=True)
    lock = BATCH / 'RUNNING.lock'
    with lock.open('x') as stream:
        stream.write(str(os.getpid()))
    try:
        preflight(rows)
        (BATCH / 'manifest.json').write_text(json.dumps(rows, indent=2))
        env = dict(os.environ, MPLBACKEND='Agg', MICROSTRUCTURE_NONINTERACTIVE='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
        fields = ['case', 'mean_mm', 'input_sha256', 'started_utc', 'ended_utc', 'elapsed_seconds', 'status', 'returncode', 'log']
        for row in rows:
            case = row['case']
            marker = BATCH / (case + '.completed.json')
            if digest(ROOT / row['input']) != row['input_sha256']:
                raise RuntimeError('Input changed after preflight: ' + case)
            if marker.exists():
                print('[SKIP]', case, flush=True)
                continue
            started = datetime.now(timezone.utc).isoformat()
            clock = time.perf_counter()
            log = BATCH / (case + '.log')
            (BATCH / 'status.json').write_text(json.dumps({'state': 'running', 'case': case, 'started_utc': started}, indent=2))
            print('[START]', case, 'mean_mm=', row['mean_mm'], started, flush=True)
            command = [sys.executable, '-u', str(Path(__file__).resolve()), '--child', row['input']]
            with log.open('w', encoding='utf-8') as stream:
                with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1) as process:
                    for line in process.stdout:
                        stream.write(line)
                        stream.flush()
                        print(line, end='', flush=True)
                    code = process.wait()
            success = code == 0 and digest(ROOT / row['input']) == row['input_sha256'] and artifacts_ok(case)
            report = {k: row[k] for k in ('case', 'mean_mm', 'input_sha256')}
            report.update(started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=round(time.perf_counter()-clock, 3), status='completed' if success else 'failed', returncode=code, log=str(log.relative_to(ROOT)))
            summary = BATCH / 'runtime_summary.csv'
            exists = summary.exists()
            with summary.open('a', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                if not exists:
                    writer.writeheader()
                writer.writerow(report)
            if not success:
                raise RuntimeError('Batch stopped at ' + case + '; inspect ' + str(log))
            marker.write_text(json.dumps(report, indent=2))
            print('[DONE]', case, flush=True)
        (BATCH / 'status.json').write_text(json.dumps({'state': 'completed', 'cases': len(rows)}, indent=2))
        print('[BATCH COMPLETED]', len(rows), flush=True)
    except BaseException as exc:
        (BATCH / 'status.json').write_text(json.dumps({'state': 'blocked', 'error': str(exc)}, indent=2))
        raise
    finally:
        lock.unlink(missing_ok=True)


def configure_console():
    # WSL exports need not reach Windows Python; configure the parent AND child.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')


def main():
    configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verify-inputs', action='store_true')
    parser.add_argument('--child')
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.child:
        run_child(args.child)
        return
    rows = load_cases()
    for index, row in enumerate(rows, 1):
        print(f"{index:02d}: {row['case']} mean={row['mean_mm']} mm", flush=True)
    preflight(rows)
    if args.verify_inputs:
        verify_inputs(rows)
    elif not args.dry_run:
        run_batch(rows)


if __name__ == '__main__':
    main()
