"""Sequential uniform size-RNG batch. Validate without solving with --dry-run."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from rng_result_locations import case_directory

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / 'simulation_inputs' / 'Uniform Distribution' / 'size-rng-position1000'
BATCH = ROOT / 'simulation_outputs' / 'uniform_size_rng_position1000_batch'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases():
    with (INPUTS / 'manifest.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 20 or [int(r['size_seed']) for r in rows] != list(range(1, 21)):
        raise ValueError('Expected exactly 20 ordered size seeds: 1-20')
    controls = []
    for row in rows:
        seed = int(row['size_seed'])
        expected = f'uniform_size_rng_{seed:04d}_pos1000'
        if row['case'] != expected or row['input_file'] != expected + '.xml' or row['position_seed'] != '1000':
            raise ValueError('Manifest case identity mismatch')
        path = INPUTS / row['input_file']
        root = ET.parse(path).getroot()
        rng = root.find('settings/rng_seeds')
        if rng is None:
            raise ValueError('Missing RNG settings')
        values = {e.tag: (e.text or '').strip() for e in rng}
        if values != {'position': '1000', 'size': str(seed)}:
            raise ValueError(f'Incorrect RNG controls: {path}')
        if root.findtext('settings/restart', '').strip().lower() != 'false':
            raise ValueError('Fresh study requires restart=False')
        materials = root.findall('material')
        if len(materials) != 4:
            raise ValueError('Expected four phases')
        for material in materials:
            size = material.find('size')
            if size is None:
                raise ValueError('Missing size distribution')
            if size.findtext('dist_type', '').strip() != 'uniform' or float(size.findtext('loc', 'nan')) != 0.05 or size.find('scale') is not None:
                raise ValueError('Uniform distribution parameters changed')
        # Canonical scalar controls: only size seed may differ between inputs.
        size_seed = rng.find('size')
        if size_seed is None:
            raise ValueError('Missing size seed')
        size_seed.text = 'VARIED'
        controls.append([(e.tag, (e.text or '').strip(), sorted(e.attrib.items())) for e in root.iter()])
    if any(control != controls[0] for control in controls):
        raise ValueError('A control other than size seed differs')
    if len(list(INPUTS.glob('*.xml'))) != 20:
        raise ValueError('Unexpected XML files in input folder')
    return rows


def artifacts_ok(dest, case):
    dest = case_directory(Path(dest).parent.parent, case)
    sta = dest / 'abaqus_files' / (case + '.sta')
    curve = dest / (case + '.csv')
    if not sta.exists() or 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta.read_text(errors='replace').upper():
        return False
    if not curve.exists():
        return False
    with curve.open(newline='', encoding='utf-8-sig') as stream:
        return sum(1 for line in csv.reader(stream) if line) >= 3


def run_batch(rows, stream_output=False, extra_fields=()):
    BATCH.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(MPLBACKEND='Agg', MICROSTRUCTURE_NONINTERACTIVE='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    fields = ['case', 'size_seed', 'position_seed', 'started_utc', 'elapsed_seconds', 'status', 'returncode', 'log']
    fields.extend(extra_fields)
    for row in rows:
        case = row['case']
        path = INPUTS / row['input_file']
        dest = ROOT / 'simulation_outputs' / case
        marker = BATCH / (case + '.completed.json')
        fingerprint = digest(path)
        if marker.exists():
            saved = json.loads(marker.read_text(encoding='utf-8'))
            if saved.get('input_sha256') != fingerprint or not artifacts_ok(dest, case):
                raise RuntimeError(f'Completion record/artifacts mismatch: {case}')
            print('[SKIP] verified completed case:', case, flush=True)
            continue
        # Never silently overwrite a partial run, or reuse unrelated cached geometry.
        if dest.exists():
            raise RuntimeError(f'Output already exists without completion record: {dest}. Inspect/recover or archive it manually before retrying.')
        relative = path.relative_to(ROOT)
        command = [sys.executable, '-u', str(Path('00_Main_Scripts') / 'full_simulation_runner.py'), '--input-file', str(relative)]
        log = BATCH / (case + '.log')
        started = datetime.now(timezone.utc).isoformat()
        clock = time.perf_counter()
        print('[START]', case, 'log:', log, flush=True)
        with log.open('w', encoding='utf-8') as stream:
            if stream_output:
                with subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1) as process:
                    assert process.stdout is not None
                    for line in process.stdout:
                        stream.write(line)
                        stream.flush()
                        print(line, end='', flush=True)
                    returncode = process.wait()
            else:
                result = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT)
                returncode = result.returncode
        success = returncode == 0 and artifacts_ok(dest, case)
        report = {**{k: row[k] for k in ('case', 'size_seed', 'position_seed')}, 'started_utc': started, 'elapsed_seconds': round(time.perf_counter() - clock, 3), 'status': 'completed' if success else 'failed', 'returncode': returncode, 'log': str(log.relative_to(ROOT))}
        report.update({key: row[key] for key in extra_fields})
        summary = BATCH / 'runtime_summary.csv'
        exists = summary.exists()
        with summary.open('a', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            if not exists:
                writer.writeheader()
            writer.writerow(report)
        if not success:
            raise RuntimeError(f'Batch stopped at {case}; inspect {log}. No later cases launched.')
        marker.write_text(json.dumps({'input_sha256': fingerprint, **report}, indent=2) + '\n', encoding='utf-8')
        print('[DONE]', case, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Validate all 20 files and list order; no solver or output writes')
    args = parser.parse_args()
    rows = load_cases()
    if args.dry_run:
        for index, row in enumerate(rows, 1):
            print(f"{index:02d}: {row['case']} size={row['size_seed']} position={row['position_seed']}")
        print('[OK] 20 inputs verified; only the size seed varies. No simulations launched.')
        return
    # Exclusive batch lock prevents accidental concurrent submissions.
    BATCH.mkdir(parents=True, exist_ok=True)
    lock = BATCH / 'RUNNING.lock'
    try:
        with lock.open('x', encoding='utf-8') as stream:
            stream.write(str(os.getpid()))
    except FileExistsError:
        raise RuntimeError(f'Batch lock exists: {lock}. Check for a running batch before removing a stale lock.') from None
    try:
        run_batch(rows)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
