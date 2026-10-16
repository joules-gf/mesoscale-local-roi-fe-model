# Archive completed size-RNG results

`archive_completed_rng_results.py` moves **whole completed case folders**, not
selected files, from `simulation_outputs` to their canonical reference locations.
It uses Python's standard library only. It never launches simulations and never
edits scientific XML, curves, meshes, solver files, batch completion markers,
runtime summaries, logs, or batch locks.

## Commands (run at repository root)

First pull the code update on the computer holding the completed results. Preview
(the default is dry-run; no directories, receipts, or files are written):

```console
python archive_completed_rng_results.py --normal-through 13
```

For the reported snapshot of **20 uniform cases and normal cases 1–13**:

```console
python archive_completed_rng_results.py --study all --normal-through 13 --apply
```

The upper bound selects candidates, not a claimed completion count. Incomplete
cases are skipped. Without `--normal-through`, normal seeds 1–20 are considered:

```console
python archive_completed_rng_results.py
python archive_completed_rng_results.py --apply
```

Study-specific previews/applications:

```console
python archive_completed_rng_results.py --study uniform
python archive_completed_rng_results.py --study uniform --apply
python archive_completed_rng_results.py --study normal-matched --normal-through 13
python archive_completed_rng_results.py --study normal-matched --normal-through 13 --apply
```

`--dry-run` explicitly requests the default preview. `--root PATH` supports another
repository root; normally omit it. Use `python3` instead of `python` where needed.
The script exits nonzero on validation, conflict, filesystem, or hash failures.
No real result moves were used to test this tool; tests use temporary fixtures.

## Exact scope and destinations

Only exact four-digit seed names 0001–0020 ending in `_pos1000` are recognized:

| Study | Case prefix | Canonical parent under repository root |
| --- | --- | --- |
| Uniform | `uniform_size_rng_` | `reference_outputs/Uniform Distribution/Sensitivity Study/Size RNG/Position RNG 1000` |
| Matched normal | `normal_matched_size_rng_` | `reference_outputs/Normal Distribution/Sensitivity Study/Size RNG matched-uniform/Position RNG 1000` |

Each destination retains the full original case directory name.

Uniform inputs are read from
`simulation_inputs/Uniform Distribution/size-rng-position1000`; their final
records remain in `simulation_outputs/uniform_size_rng_position1000_batch`.
Matched-normal inputs are read from
`simulation_inputs/Normal Distribution/size-rng-position1000-matched-uniform`;
their final records remain in
`simulation_outputs/normal_matched_size_rng_position1000_batch`.

## Eligibility and safety

The entire selected set is preflighted **before any move or receipt write**.
A case must have its matching `<case>.completed.json` with `status=completed`,
integer `returncode=0`, matching case/size/position identity, and an
`input_sha256` matching the actual input XML. Both input and resolved-output XML
must contain four material phases, position seed 1000, the case's size seed, and
the expected distribution:

- Uniform: `dist_type=uniform`, lower bound .05, width .01. An omitted width uses
  `.2 * loc`, matching the study's original input convention.
- Matched normal: `dist_type=norm`, mean .055, standard deviation `.01/sqrt(12)`.

Also required: the matching `abaqus_files/<case>.sta` contains
`THE ANALYSIS HAS COMPLETED SUCCESSFULLY`, and `<case>.csv` contains at least two
rows with finite numeric strain/stress in zero-based columns 1 and 2. The
matching `<case>_resolved_input.xml` is checked rather than trusting filenames.

No final JSON means skip, even if plausible result files exist. A noncompleted
record is skipped. A case containing any `.lck` file is left untouched. Final
successful records with missing results, mismatched provenance, invalid artifacts,
symlinks, special files, or an existing unrelated target cause an error rather
than invented success. Source/archive duplicates are conflicts, never merged.
Path traversal is rejected. Batch `RUNNING.lock` does **not** prevent archiving
previously completed cases while a later case runs; it is not modified.

Run **one archiver at a time**, and do not edit or reopen completed case folders
while archiving. A later active case may keep running. Inventory rechecks narrow
but cannot eliminate races with unrelated programs changing the same folders.
Cross-filesystem moves are refused; there is no copy/delete fallback. Each folder
uses a same-filesystem rename. There is no blanket deletion or filtering.

Preflight prevents known invalid cases causing partial moves. Hardware/process
failure during application can still leave a prefix of selected cases archived;
per-case receipts make a repeat safe.

## Hashes, receipts, interruption recovery

Every source file (including ignored databases and hidden files) is inventoried
with its relative name, byte size and streamed SHA256. After rename, every file
is hashed again and the complete inventory must match. Empty directories move
with the folder too. All bytes stay unchanged.

Receipts live **outside** case folders, in a `.archival_receipts` directory under
each canonical reference parent, named `<case>.json`. Keep these receipts with
the results. A receipt records exact source/destination, input/completion-record
hashes, and the complete file inventory. An atomic, flushed `pending` receipt is
written **before** rename, then atomically replaced with a `complete` receipt
only after destination hashes match. Directory entries are fsynced where the
platform supports POSIX directory fsync; Windows uses flushed atomic JSON
replacement, with power-loss durability subject to filesystem guarantees.

Re-running:

- Verifies and skips completed archives without rewriting their receipt.
- Retries a `pending` receipt if rename had not happened yet.
- Verifies destination hashes and finishes a `pending` receipt if rename happened
  but the final receipt write was interrupted.
- Refuses to adopt an existing destination without a matching receipt.
- Reports missing originals **and** destinations despite a successful final
  record, or a complete receipt whose destination disappeared.
- Can archive later completed normal cases 14–20 with the default upper bound.

Do not delete receipts to silence an error. Inspect the named case and preserve
both result bytes and records. A post-rename failure intentionally leaves the
pending receipt for investigation/recovery; no rollback or deletion is attempted.

## Resume and sharing

The batch runners' archive-aware `case_directory(root, case)` integration looks
for current output first, then the recognized canonical archive. If both exist,
it raises a conflict. This lets subsequent batch runs verify archived completed
cases rather than rerunning or treating them as missing; incomplete/live folders
remain where the runner expects them. Keep the original batch completion JSONs
and matching inputs in place. Use the code version containing that runner
integration before resuming a batch after archiving.

**Running this script does not upload results.** The results remain on the
friend's computer until the friend reviews them and performs their own later
Git add/commit/push. The code commit/push alone does not include results that
exist only on their machine. Ignored solver databases (for example `.odb`) are
preserved locally by the move, but Git ignore rules still apply: they are not
automatically included in a later normal commit. Do not force-add large databases
without separately agreeing on repository/storage policy.

## Tests (no FE solves)

```console
python -m unittest discover -s tests -p test_archive_completed_rng_results.py -v
```

Tests actually rename temporary fixture folders and check byte/hash preservation,
no-write dry-run, incomplete/live-case skips, provenance and artifact rejection,
preflight conflicts, idempotency, receipt tampering, both interruption windows,
missing-result errors, both study locations, and symlink/traversal rejection.
