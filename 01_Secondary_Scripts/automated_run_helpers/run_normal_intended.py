"""Run intended-normal cases, optionally gated on verified matched-batch success."""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import run_uniform_size_rng as engine
from verify_normal_matched_uniform_inputs import ROOT, UNIFORM, controls

INPUTS = ROOT / 'simulation_inputs/Normal Distribution/sensitivity-study-AA7075-T651/equal-mean-original-intent'
MATCHED_INPUTS = INPUTS.with_name('equal-mean-matched-uniform')
BATCH = ROOT / 'simulation_outputs/normal_intended_batch'
PREVIOUS = ROOT / 'simulation_outputs/normal_matched_uniform_batch'
EXTRA_FIELDS = ('kind', 'source_uniform_case', 'normal_mean_mm', 'normal_std_mm')


def load_plan():
    with (INPUTS / 'manifest.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 21 or len({row['case'] for row in rows}) != 21:
        raise ValueError('Expected 21 unique intended-normal cases')
    if sum(r['kind'] == 'sweep' for r in rows) != 20 or sum(r['kind'] == 'baseline' for r in rows) != 1:
        raise ValueError('Expected 20 sweep cases and one baseline')
    if {p.name for p in INPUTS.glob('*.xml')} != {r['input_file'] for r in rows}:
        raise ValueError('Manifest and XML set differ')
    for row in rows:
        path = INPUTS / row['input_file']
        source = UNIFORM / (row['source_uniform_case'] + '.xml')
        if path.parent != INPUTS or path.stem != row['case'] or source.parent != UNIFORM:
            raise ValueError('Invalid manifest path')
        root, old = ET.parse(path).getroot(), ET.parse(source).getroot()
        if controls(root) != controls(old):
            raise ValueError('Non-distribution controls differ')
        if root.findall('.//scale'):
            raise ValueError('Intended normal requires omitted scale and existing 20% calculation')
        if root.findtext('settings/verbose', '').strip().lower() != 'true' or root.findtext('settings/restart', '').strip().lower() != 'false':
            raise ValueError('Require verbose=True and restart=False')
        mean, std = float(row['normal_mean_mm']), float(row['normal_std_mm'])
        if mean <= 0 or not math.isclose(std, .2 * mean, rel_tol=1e-13):
            raise ValueError('Expected std=20% of mean')
        phases, originals = root.findall('material'), old.findall('material')
        if len(phases) != 4 or len(originals) != 4:
            raise ValueError('Expected four phases')
        for phase, original in zip(phases, originals):
            if phase.findtext('size/dist_type', '').strip() != 'norm' or not math.isclose(float(phase.findtext('size/loc', 'nan')), mean, rel_tol=1e-13) or float(original.findtext('size/loc', 'nan')) != mean:
                raise ValueError('Intended mean does not match original setting')
        rng = root.find('settings/rng_seeds')
        if rng is None or {e.tag: (e.text or '').strip() for e in rng} != {'size': '1000'}:
            raise ValueError('Original RNG settings changed')
        row.update(size_seed='1000', position_seed='omitted: original default')
    return sorted(rows, key=lambda r: float(r['normal_mean_mm']), reverse=True)


def predecessor_ready():
    """Return False while running; raise on stopped/incomplete/invalid predecessor."""
    if (PREVIOUS / 'RUNNING.lock').exists():
        return False
    if not (PREVIOUS / 'COMPLETED.txt').exists():
        raise RuntimeError('Matched-normal batch stopped without successful completion. Intended batch will NOT start.')
    with (MATCHED_INPUTS / 'manifest.csv').open(newline='', encoding='utf-8') as stream:
        expected = list(csv.DictReader(stream))
    with (PREVIOUS / 'runtime_summary.csv').open(newline='', encoding='utf-8') as stream:
        summary = list(csv.DictReader(stream))
    names = {r['case'] for r in expected}
    if len(expected) != 21 or len(names) != 21 or len(summary) != 21 or {r['case'] for r in summary} != names or any(r['status'] != 'completed' or r['returncode'] != '0' for r in summary):
        raise RuntimeError('Predecessor summary does not verify exactly 21 successful cases')
    if {p.name for p in PREVIOUS.glob('*.completed.json')} != {name + '.completed.json' for name in names}:
        raise RuntimeError('Predecessor completion-record set mismatch')
    for row in expected:
        case = row['case']
        if Path(row['input_file']).name != row['input_file'] or Path(case).name != case:
            raise ValueError('Invalid predecessor manifest path')
        saved = json.loads((PREVIOUS / (case + '.completed.json')).read_text(encoding='utf-8'))
        if saved.get('input_sha256') != engine.digest(MATCHED_INPUTS / row['input_file']) or saved.get('status') != 'completed' or saved.get('returncode') != 0 or not engine.artifacts_ok(ROOT / 'simulation_outputs' / case, case):
            raise RuntimeError('Predecessor artifact/hash verification failed: ' + case)
    return True


def status(state, **details):
    record = {'state': state, 'updated_utc': datetime.now(timezone.utc).isoformat(), **details}
    temp = BATCH / 'handoff_status.tmp'
    temp.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    temp.replace(BATCH / 'handoff_status.json')
    print('[' + state.upper() + ']', json.dumps(details), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--after-matched', action='store_true', help='Wait for verified predecessor completion before running')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    rows = load_plan()
    for i, row in enumerate(rows, 1):
        print(f"{i:02d}: {row['case']} mean={float(row['normal_mean_mm']):g} std={float(row['normal_std_mm']):g} mm", flush=True)
    if args.dry_run:
        print('[OK] 21 intended inputs validated; no waiting, outputs, or solver launch.', flush=True)
        return
    BATCH.mkdir(parents=True, exist_ok=True)
    lock = BATCH / 'RUNNING.lock'
    try:
        with lock.open('x', encoding='utf-8') as stream:
            stream.write(str(os.getpid()))
    except FileExistsError:
        raise RuntimeError('Intended batch/queue lock already exists; refusing duplicate launch') from None
    try:
        fingerprints = {r['input_file']: engine.digest(INPUTS / r['input_file']) for r in rows}
        if args.after_matched:
            status('waiting', predecessor=str(PREVIOUS), condition='21 verified successes and predecessor lock released')
            while not predecessor_ready():
                time.sleep(60)
        elif (PREVIOUS / 'RUNNING.lock').exists():
            raise RuntimeError('Matched batch is still active; use --after-matched to avoid concurrent simulations')
        rows = load_plan()
        if {r['input_file']: engine.digest(INPUTS / r['input_file']) for r in rows} != fingerprints:
            raise RuntimeError('Intended inputs changed while queued; refusing unreviewed run')
        engine.ROOT, engine.INPUTS, engine.BATCH = ROOT, INPUTS, BATCH
        status('running', case_count=21, order='largest-to-smallest', verbose=True, popup_figures=False)
        engine.run_batch(rows, stream_output=True, extra_fields=EXTRA_FIELDS)
        (BATCH / 'COMPLETED.txt').write_text('All 21 intended-normal cases verified completed.\n', encoding='utf-8')
        status('completed', case_count=21)
    except BaseException as exc:
        status('blocked', error=str(exc))
        raise
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
