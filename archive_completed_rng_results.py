"""Archive verified completed size-RNG folders. Dry-run unless --apply; no solves."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
# Keep a preview free of helper-import __pycache__ writes as well as output writes.
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / '01_Secondary_Scripts/automated_run_helpers'))
from rng_result_locations import STUDIES, archived_directory, safe_path


def digest(path):
    value = hashlib.sha256()
    with safe_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def inventory(folder):
    """Stream every file, including ignored ODBs. Refuse links/special files."""
    safe_path(folder)
    if not folder.is_dir():
        raise ValueError(f'Missing result directory: {folder}')
    result = {}
    for parent, dirs, files in os.walk(folder, followlinks=False):
        for name in dirs + files:
            path = safe_path(Path(parent) / name)
            mode = path.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError(f'Nonregular result entry: {path}')
        for name in sorted(files):
            path = Path(parent) / name
            result[path.relative_to(folder).as_posix()] = {'size': path.stat().st_size, 'sha256': digest(path)}
    return dict(sorted(result.items()))


def receipt_path(root, case):
    return safe_path(archived_directory(root, case).parent / '.archival_receipts' / (case + '.json'))


def sync_directory(folder):
    # Windows does not support opening directories for fsync. Atomic replace still
    # provides crash-safe old/new JSON there; POSIX also flushes directory entries.
    if os.name != 'nt':
        fd = os.open(folder, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def write_receipt(path, data):
    """Durably publish pending intent before rename, then the completed receipt."""
    safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path):
    with safe_path(path).open(encoding='utf-8') as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return data


def validate_xml(path, study, seed):
    root = ET.parse(safe_path(path)).getroot()
    rng = root.find('settings/rng_seeds')
    if rng is None or len(rng) != 2 or {e.tag: (e.text or '').strip() for e in rng} != {'position': '1000', 'size': str(seed)}:
        raise ValueError(f'RNG seed mismatch: {path}')
    materials = root.findall('material')
    if len(materials) != 4:
        raise ValueError(f'Expected four material phases: {path}')
    for material in materials:
        size = material.find('size')
        if size is None:
            raise ValueError(f'Missing size distribution: {path}')
        family = size.findtext('dist_type', '').strip()
        loc = float(size.findtext('loc', 'nan'))
        if study == 'uniform':
            width = float(size.findtext('scale')) if size.find('scale') is not None else .2 * loc
            valid = family == 'uniform' and math.isclose(loc, .05, rel_tol=1e-13) and math.isclose(width, .01, rel_tol=1e-13)
        else:
            scale = float(size.findtext('scale', 'nan'))
            valid = family == 'norm' and math.isclose(loc, .055, rel_tol=1e-13) and math.isclose(scale, .01 / math.sqrt(12), rel_tol=1e-13)
        if not valid:
            raise ValueError(f'Distribution family/moments mismatch: {path}')


def validate_artifacts(folder, case, study, seed):
    sta = safe_path(folder / 'abaqus_files' / (case + '.sta'))
    if not sta.is_file() or 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta.read_text(errors='replace').upper():
        raise ValueError(f'Missing/unsuccessful Abaqus status: {case}')
    curve = safe_path(folder / (case + '.csv'))
    numeric = 0
    with curve.open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.reader(stream):
            try:
                numeric += math.isfinite(float(row[1])) and math.isfinite(float(row[2]))
            except (IndexError, ValueError):
                continue
    if numeric < 2:
        raise ValueError(f'Need two finite numeric strain/stress rows: {curve}')
    validate_xml(folder / (case + '_resolved_input.xml'), study, seed)


def nearest_existing(path):
    while not path.exists():
        path = path.parent
    return path


def preflight(root, study='all', normal_through=20):
    if study not in ('all', *STUDIES) or not 1 <= normal_through <= 20:
        raise ValueError('Invalid study or --normal-through (must be 1..20)')
    safe_path(root)
    plans, messages = [], []
    for label, config in STUDIES.items():
        if study != 'all' and study != label:
            continue
        for seed in range(1, (normal_through if label == 'normal-matched' else 20) + 1):
            case = f'{config["prefix"]}_{seed:04d}_pos1000'
            source = safe_path(root / 'simulation_outputs' / case)
            target = archived_directory(root, case)
            marker = safe_path(root / config['batch'] / (case + '.completed.json'))
            receipt = receipt_path(root, case)
            if source.exists() and target.exists():
                raise ValueError(f'Source/archive conflict: {case}')
            if not marker.exists():
                if target.exists() or receipt.exists():
                    raise ValueError(f'Missing final completion record for archived case: {case}')
                messages.append(f'SKIP {case}: no final completion JSON (incomplete/not started)')
                continue
            record = read_json(marker)
            if (record.get('status') != 'completed' or type(record.get('returncode')) is not int
                    or record.get('returncode') != 0):
                if target.exists() or receipt.exists():
                    raise ValueError(f'Archived case lacks successful final record: {case}')
                messages.append(f'SKIP {case}: final record is not completed/returncode 0')
                continue
            if (record.get('case') != case or str(record.get('size_seed')) != str(seed)
                    or str(record.get('position_seed')) != '1000'):
                raise ValueError(f'Completion record identity/seed mismatch: {case}')
            inp = safe_path(root / config['inputs'] / (case + '.xml'))
            if not inp.is_file() or record.get('input_sha256') != digest(inp):
                raise ValueError(f'Completion input SHA256 mismatch/missing input: {case}')
            validate_xml(inp, label, seed)
            folder = source if source.exists() else target
            if not folder.is_dir():
                raise ValueError(f'Missing original and archived result folder despite final record: {case}')
            files = inventory(folder)
            if any(Path(name).suffix.lower() == '.lck' for name in files):
                if not source.exists():
                    raise ValueError(f'Archived result contains solver lock: {case}')
                messages.append(f'SKIP {case}: live .lck file; left untouched')
                continue
            validate_artifacts(folder, case, label, seed)
            for path in (target, receipt):
                for parent in path.parents:
                    if parent.exists() and not parent.is_dir():
                        raise ValueError(f'Archive/receipt parent is not a directory: {parent}')
            expected = {'version': 1, 'case': case, 'source': source.relative_to(root).as_posix(),
                        'destination': target.relative_to(root).as_posix(), 'input_sha256': record['input_sha256'],
                        'completion_sha256': digest(marker), 'files': files}
            saved = read_json(receipt) if receipt.exists() else None
            if saved is not None:
                if saved.get('state') not in ('pending', 'complete') or any(saved.get(key) != value for key, value in expected.items()):
                    raise ValueError(f'Archival receipt/inventory mismatch: {case}')
            if target.exists():
                if saved is None:
                    raise ValueError(f'Existing target without archival receipt: {case}')
                action = 'verify' if saved['state'] == 'complete' else 'recover'
            else:
                if saved is not None and saved['state'] == 'complete':
                    raise ValueError(f'Complete receipt but missing archived destination: {case}')
                if source.stat().st_dev != nearest_existing(target.parent).stat().st_dev:
                    raise ValueError(f'Cross-filesystem move refused: {case}')
                action = 'move'
            plans.append((action, source, target, marker, receipt, expected))
    return plans, messages


def archive_results(root, *, study='all', normal_through=20, apply=False):
    """Preflight ALL selected cases before any write; return human-readable report."""
    root = Path(root).absolute()
    plans, messages = preflight(root, study, normal_through)
    for action, source, target, marker, receipt, expected in plans:
        case = expected['case']
        if action == 'verify':
            messages.append(f'VERIFIED {case}: already archived; all file hashes match')
            continue
        if not apply:
            messages.append(f'WOULD {"MOVE" if action == "move" else "RECOVER RECEIPT"} {case}: {source} -> {target}')
            continue
        folder = source if action == 'move' else target
        # Recheck immediately before changing state: a running unrelated case is
        # fine, but nothing may change this completed case since preflight.
        if inventory(folder) != expected['files'] or digest(marker) != expected['completion_sha256']:
            raise ValueError(f'Case changed since preflight: {case}')
        if action == 'move':
            safe_path(target)
            if target.exists():
                raise ValueError(f'Target appeared since preflight: {case}')
            write_receipt(receipt, dict(expected, state='pending'))
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.stat().st_dev != target.parent.stat().st_dev:
                raise ValueError(f'Cross-filesystem move refused: {case}')
            # rename only: no copy fallback, merging, deleting or solver filtering.
            source.rename(target)
            sync_directory(source.parent)
            sync_directory(target.parent)
        if inventory(target) != expected['files']:
            raise ValueError(f'Post-rename inventory mismatch; retain pending receipt and inspect: {case}')
        write_receipt(receipt, dict(expected, state='complete'))
        messages.append(f'{"MOVED" if action == "move" else "RECOVERED"} {case}: {target}')
    return messages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true', help='Actually rename eligible completed folders')
    mode.add_argument('--dry-run', action='store_true', help='Explicit default: verify only, write nothing')
    parser.add_argument('--study', choices=('all', 'uniform', 'normal-matched'), default='all')
    parser.add_argument('--normal-through', type=int, choices=range(1, 21), default=20, metavar='1..20')
    parser.add_argument('--root', type=Path, default=ROOT, help='Repository root (defaults to this script location)')
    args = parser.parse_args(argv)
    try:
        messages = archive_results(args.root, study=args.study, normal_through=args.normal_through, apply=args.apply)
    except (OSError, ValueError, RuntimeError, ET.ParseError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print('\n'.join(messages))
    print('Apply complete; no simulations launched.' if args.apply else 'Dry-run only; no files written or simulations launched.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
