"""Canonical locations for the two exact 20-case size-RNG studies (stdlib only)."""
from pathlib import Path
import re

STUDIES = {
    'uniform': {
        'prefix': 'uniform_size_rng',
        'inputs': 'simulation_inputs/Uniform Distribution/size-rng-position1000',
        'batch': 'simulation_outputs/uniform_size_rng_position1000_batch',
        'reference': 'reference_outputs/Uniform Distribution/Sensitivity Study/Size RNG/Position RNG 1000',
    },
    'normal-matched': {
        'prefix': 'normal_matched_size_rng',
        'inputs': 'simulation_inputs/Normal Distribution/size-rng-position1000-matched-uniform',
        'batch': 'simulation_outputs/normal_matched_size_rng_position1000_batch',
        'reference': 'reference_outputs/Normal Distribution/Sensitivity Study/Size RNG matched-uniform/Position RNG 1000',
    },
}


def safe_path(path: Path) -> Path:
    """Reject traversal and any existing symlink, including parent components."""
    path = Path(path)
    if '..' in path.parts:
        raise ValueError(f'Path traversal rejected: {path}')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f'Symlink rejected: {part}')
    return path


def case_identity(case: str):
    if not case or '/' in case or '\\' in case or case in ('.', '..') or ':' in case:
        raise ValueError(f'Invalid case name: {case!r}')
    match = re.fullmatch(r'(uniform_size_rng|normal_matched_size_rng)_(000[1-9]|001[0-9]|0020)_pos1000', case)
    if match is None:
        return None
    study = 'uniform' if match[1] == 'uniform_size_rng' else 'normal-matched'
    return study, int(match[2])


def archived_directory(root: Path, case: str):
    identity = case_identity(case)
    if identity is None:
        return None
    return safe_path(Path(root) / STUDIES[identity[0]]['reference'] / case)


def case_directory(root: Path, case: str) -> Path:
    """Prefer live output, otherwise its recognized archive; never hide a conflict."""
    case_identity(case)
    source = safe_path(Path(root) / 'simulation_outputs' / case)
    archived = archived_directory(root, case)
    if archived is not None and archived.exists():
        if source.exists():
            raise RuntimeError(f'Source/archive conflict for {case}: {source} and {archived}')
        return archived
    return source
