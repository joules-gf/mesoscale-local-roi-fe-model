"""Run all 21 moment-matched normal inputs, largest-to-smallest, with live logs."""
import argparse
import csv
import math
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import run_uniform_size_rng as engine
from verify_normal_matched_uniform_inputs import ROOT, NORMAL, UNIFORM, controls

BATCH = ROOT / 'simulation_outputs' / 'normal_matched_uniform_batch'
EXTRA_FIELDS = ('kind', 'source_uniform_case', 'uniform_lower_bound_mm', 'uniform_width_mm', 'normal_mean_mm', 'normal_std_mm')


def load_plan():
    with (NORMAL / 'manifest.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 21 or len({r['case'] for r in rows}) != 21:
        raise ValueError('Expected 21 unique normal cases')
    if sum(r['kind'] == 'sweep' for r in rows) != 20 or sum(r['kind'] == 'baseline' for r in rows) != 1:
        raise ValueError('Expected 20 sweep cases and one baseline')
    if {p.name for p in NORMAL.glob('*.xml')} != {r['input_file'] for r in rows}:
        raise ValueError('Manifest and XML set differ')
    for row in rows:
        path = NORMAL / row['input_file']
        if path.parent != NORMAL or path.stem != row['case']:
            raise ValueError('Invalid case path')
        source = UNIFORM / (row['source_uniform_case'] + '.xml')
        if source.parent != UNIFORM:
            raise ValueError('Invalid source path')
        root = ET.parse(path).getroot()
        if controls(root) != controls(ET.parse(source).getroot()):
            raise ValueError('Non-distribution controls differ from source')
        if root.findtext('settings/verbose', '').strip().lower() != 'true' or root.findtext('settings/restart', '').strip().lower() != 'false':
            raise ValueError('Require verbose=True and restart=False')
        a = float(row['uniform_lower_bound_mm'])
        width = float(row['uniform_width_mm'])
        mean, std = float(row['normal_mean_mm']), float(row['normal_std_mm'])
        if not math.isclose(mean, a + width / 2, rel_tol=1e-13) or not math.isclose(std, width / math.sqrt(12), rel_tol=1e-13):
            raise ValueError('Manifest moments are not matched')
        phases = root.findall('material')
        if len(phases) != 4:
            raise ValueError('Expected four phases')
        for phase in phases:
            if phase.findtext('size/dist_type', '').strip() != 'norm' or not math.isclose(float(phase.findtext('size/loc', 'nan')), mean, rel_tol=1e-13) or not math.isclose(float(phase.findtext('size/scale', 'nan')), std, rel_tol=1e-13):
                raise ValueError('XML does not match normal manifest')
        rng = root.find('settings/rng_seeds')
        if rng is None or {e.tag: (e.text or '').strip() for e in rng} != {'size': '1000'}:
            raise ValueError('RNG differs from original diameter sweep')
        row.update(size_seed='1000', position_seed='omitted: original default')
    return sorted(rows, key=lambda row: float(row['normal_mean_mm']), reverse=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    rows = load_plan()
    for index, row in enumerate(rows, 1):
        print(f"{index:02d}: {row['case']} mean={float(row['normal_mean_mm']):.9g} std={float(row['normal_std_mm']):.9g} mm", flush=True)
    print('verbose=True; plots saved with no GUI; postprocessing ENABLED', flush=True)
    if args.dry_run:
        print('[OK] validated 21 inputs; no simulations launched.', flush=True)
        return
    engine.ROOT, engine.INPUTS, engine.BATCH = ROOT, NORMAL, BATCH
    BATCH.mkdir(parents=True, exist_ok=True)
    lock = BATCH / 'RUNNING.lock'
    try:
        with lock.open('x', encoding='utf-8') as stream:
            stream.write(str(os.getpid()))
    except FileExistsError:
        raise RuntimeError(f'Batch lock exists: {lock}; check for an active batch before removing a stale lock.') from None
    try:
        engine.run_batch(rows, stream_output=True, extra_fields=EXTRA_FIELDS)
        (BATCH / 'COMPLETED.txt').write_text('All 21 cases verified completed.\n', encoding='utf-8')
        print('[COMPLETE] All 21 cases verified.', flush=True)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
