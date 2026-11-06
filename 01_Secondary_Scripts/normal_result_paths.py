"""Locate normal equal-mean results without changing batch metadata locations."""
from pathlib import Path

EQUAL_MEAN_CASES = frozenset(f'bp_same_size_case_{i:02d}' for i in range(1, 21)) | {'bp_same_size_baseline_0p050'}
ARCHIVE = Path('reference_outputs/Normal Distribution/Sensitivity Study/Uniform Mean Diameter Change')


def resolve_case_folder(root, case):
    """Return existing original/archive folder, or original for an unrun case.

    Only the 21 original equal-mean cases have archive candidates. Refuse
    duplicate locations even if one is incomplete, rather than hiding stale data.
    """
    root = Path(root)
    original = root / 'simulation_outputs' / case
    candidates = [original]
    if case in EQUAL_MEAN_CASES:
        candidates.append(root / ARCHIVE / case)
    existing = [path for path in candidates if path.exists()]
    if len(existing) > 1:
        raise RuntimeError(f'Duplicate result locations for {case}: ' + ', '.join(map(str, existing)))
    return existing[0] if existing else original
