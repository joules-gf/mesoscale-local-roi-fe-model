"""Temporary-fixture tests only: no solver imports or real result moves."""
import hashlib
import subprocess
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / '01_Secondary_Scripts/automated_run_helpers'
sys.path.insert(0, str(HELPERS))
sys.path.insert(0, str(REPO))


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = __import__('archive_completed_rng_results')
        self.locations = __import__('rng_result_locations')

    def fixture(self, study='uniform', seed=1, marker=True):
        config = self.locations.STUDIES[study]
        case = f'{config["prefix"]}_{seed:04d}_pos1000'
        source = self.root / 'simulation_outputs' / case
        source.mkdir(parents=True)
        (source / 'abaqus_files').mkdir()
        (source / 'abaqus_files' / (case + '.sta')).write_text('THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n')
        (source / (case + '.csv')).write_text('time,strain,stress\n0,0,0\n1,.01,450\n')
        (source / 'abaqus_files' / (case + '.odb')).write_bytes(bytes(range(256)) * 6000)
        size = '<dist_type>uniform</dist_type><loc>.05</loc>' if study == 'uniform' else f'<dist_type>norm</dist_type><loc>.055</loc><scale>{.01 / math.sqrt(12)}</scale>'
        xml = f'<input><settings><rng_seeds><position>1000</position><size>{seed}</size></rng_seeds></settings>' + ('<material><size>' + size + '</size></material>') * 4 + '</input>'
        (source / (case + '_resolved_input.xml')).write_text(xml)
        inp = self.root / config['inputs'] / (case + '.xml')
        inp.parent.mkdir(parents=True, exist_ok=True)
        inp.write_text(xml)
        record = self.root / config['batch'] / (case + '.completed.json')
        record.parent.mkdir(parents=True, exist_ok=True)
        if marker:
            record.write_text(json.dumps(dict(case=case, size_seed=str(seed), position_seed='1000', status='completed', returncode=0, input_sha256=hashlib.sha256(inp.read_bytes()).hexdigest())))
        return case, source, record

    def run_archive(self, apply=False, study='all', normal_through=20):
        return self.archive.archive_results(self.root, study=study, normal_through=normal_through, apply=apply)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_dry_run_no_writes(self):
        self.fixture()
        before = self.snapshot()
        self.assertIn('WOULD MOVE', '\n'.join(self.run_archive()))
        self.assertEqual(before, self.snapshot())

    def test_completed_move_and_hash_preservation(self):
        case, source, marker = self.fixture()
        before = self.archive.inventory(source)
        saved = marker.read_bytes()
        self.run_archive(apply=True)
        dest = self.locations.archived_directory(self.root, case)
        self.assertFalse(source.exists())
        self.assertEqual(before, self.archive.inventory(dest))
        self.assertEqual(saved, marker.read_bytes())
        self.assertEqual('complete', json.loads(self.archive.receipt_path(self.root, case).read_text())['state'])

    def test_missing_marker_including_live_case_is_untouched(self):
        _, source, _ = self.fixture(marker=False)
        (source / 'abaqus_files/job.lck').write_text('busy')
        before = self.snapshot()
        self.run_archive(apply=True)
        self.assertEqual(before, self.snapshot())

    def test_live_lock_even_with_marker_skipped(self):
        _, source, _ = self.fixture()
        (source / 'abaqus_files/job.lck').write_text('busy')
        before = self.snapshot()
        self.assertIn('SKIP', '\n'.join(self.run_archive(apply=True)))
        self.assertEqual(before, self.snapshot())

    def test_bad_hash_seed_family_and_moments_rejected(self):
        for corruption in ('hash', 'seed', 'family', 'moments'):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                case, source, marker = self.fixture()
                if corruption == 'hash':
                    data = json.loads(marker.read_text()); data['input_sha256'] = '0' * 64
                    marker.write_text(json.dumps(data))
                else:
                    xml = source / (case + '_resolved_input.xml')
                    text = xml.read_text()
                    text = text.replace('<size>1</size>', '<size>2</size>') if corruption == 'seed' else text.replace('uniform', 'norm') if corruption == 'family' else text.replace('.05', '.06')
                    xml.write_text(text)
                before = self.snapshot()
                with self.assertRaises((ValueError, RuntimeError)):
                    self.run_archive(apply=True)
                self.assertEqual(before, self.snapshot())

    def test_preflight_collision_prevents_all_moves(self):
        _, first, _ = self.fixture()
        case, _, _ = self.fixture(seed=2)
        self.locations.archived_directory(self.root, case).mkdir(parents=True)
        before = self.snapshot()
        with self.assertRaises((ValueError, RuntimeError)):
            self.run_archive(apply=True)
        self.assertTrue(first.exists())
        self.assertEqual(before, self.snapshot())

    def test_later_study_receipt_parent_file_prevents_all_writes(self):
        first_case, first, _ = self.fixture()
        case, source, _ = self.fixture('normal-matched')
        blocker = self.archive.receipt_path(self.root, case).parent
        blocker.parent.mkdir(parents=True)
        blocker.write_text('not a directory')
        before = self.snapshot()
        directories = {p.relative_to(self.root) for p in self.root.rglob('*') if p.is_dir()}
        with mock.patch.object(self.archive, 'write_receipt', wraps=self.archive.write_receipt) as write:
            with self.assertRaises((OSError, ValueError)):
                self.run_archive(apply=True)
            write.assert_not_called()
        self.assertTrue(first.is_dir())
        self.assertTrue(source.is_dir())
        self.assertFalse(self.archive.receipt_path(self.root, first_case).exists())
        self.assertEqual(before, self.snapshot())
        self.assertEqual(directories, {p.relative_to(self.root) for p in self.root.rglob('*') if p.is_dir()})

    def test_later_study_destination_ancestor_file_prevents_all_writes(self):
        for depth in (0, 1, 2):
            with self.subTest(depth=depth), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                first_case, first, _ = self.fixture()
                case, source, _ = self.fixture('normal-matched')
                blocker = self.locations.archived_directory(self.root, case).parents[depth]
                blocker.parent.mkdir(parents=True)
                blocker.write_text('not a directory')
                before = self.snapshot()
                directories = {p.relative_to(self.root) for p in self.root.rglob('*') if p.is_dir()}
                with mock.patch.object(self.archive, 'write_receipt', wraps=self.archive.write_receipt) as write:
                    with self.assertRaises((OSError, ValueError)):
                        self.run_archive(apply=True)
                    write.assert_not_called()
                self.assertTrue(first.is_dir())
                self.assertTrue(source.is_dir())
                self.assertFalse(self.archive.receipt_path(self.root, first_case).exists())
                self.assertEqual(before, self.snapshot())
                self.assertEqual(directories, {p.relative_to(self.root) for p in self.root.rglob('*') if p.is_dir()})

    def test_noninteger_returncodes_skipped_without_moves(self):
        for returncode in (0.0, False, True):
            with self.subTest(returncode=returncode), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                case, source, marker = self.fixture()
                record = json.loads(marker.read_text())
                record['returncode'] = returncode
                marker.write_text(json.dumps(record))
                before = self.snapshot()
                messages = self.run_archive(apply=True)
                self.assertIn(f'SKIP {case}: final record is not completed/returncode 0', messages)
                self.assertTrue(source.is_dir())
                self.assertFalse(self.locations.archived_directory(self.root, case).exists())
                self.assertFalse(self.archive.receipt_path(self.root, case).exists())
                self.assertEqual(before, self.snapshot())

    def test_idempotent_and_later_normal_case(self):
        self.fixture('normal-matched')
        self.run_archive(apply=True, normal_through=13)
        before = self.snapshot()
        self.assertIn('VERIFIED', '\n'.join(self.run_archive(apply=True)))
        self.assertEqual(before, self.snapshot())
        case, source, _ = self.fixture('normal-matched', seed=14)
        self.run_archive(apply=True, normal_through=13)
        self.assertTrue(source.exists())
        self.run_archive(apply=True)
        self.assertTrue(self.locations.archived_directory(self.root, case).exists())

    def test_interrupted_after_rename_recovers_from_pending_receipt(self):
        case, source, _ = self.fixture()
        original = self.archive.write_receipt
        def interrupt(path, data):
            if data['state'] == 'complete':
                raise OSError('simulated interruption after rename')
            original(path, data)
        with mock.patch.object(self.archive, 'write_receipt', side_effect=interrupt):
            with self.assertRaises(OSError):
                self.run_archive(apply=True)
        self.assertFalse(source.exists())
        self.assertEqual('pending', json.loads(self.archive.receipt_path(self.root, case).read_text())['state'])
        self.assertIn('RECOVERED', '\n'.join(self.run_archive(apply=True)))
        self.assertEqual('complete', json.loads(self.archive.receipt_path(self.root, case).read_text())['state'])

    def test_interrupted_before_rename_can_retry(self):
        case, source, _ = self.fixture()
        with mock.patch.object(Path, 'rename', side_effect=OSError('interrupted before rename')):
            with self.assertRaises(OSError):
                self.run_archive(apply=True)
        self.assertTrue(source.exists())
        self.run_archive(apply=True)
        self.assertTrue(self.locations.archived_directory(self.root, case).exists())

    def test_cli_dryrun_and_apply_only_on_fixture(self):
        case, source, _ = self.fixture('normal-matched')
        before = self.snapshot()
        command = [sys.executable, str(REPO / 'archive_completed_rng_results.py'), '--root', str(self.root), '--study', 'normal-matched', '--normal-through', '13']
        preview = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, preview.returncode, preview.stderr)
        self.assertIn('WOULD MOVE', preview.stdout)
        self.assertEqual(before, self.snapshot())
        applied = subprocess.run(command + ['--apply'], capture_output=True, text=True)
        self.assertEqual(0, applied.returncode, applied.stderr)
        self.assertFalse(source.exists())
        self.assertTrue(self.locations.archived_directory(self.root, case).exists())

    def test_running_batch_and_active_next_case_unchanged(self):
        _, _, marker = self.fixture('normal-matched')
        lock = marker.parent / 'RUNNING.lock'
        lock.write_text('12345')
        _, active, _ = self.fixture('normal-matched', seed=14, marker=False)
        (active / 'abaqus_files/job.lck').write_text('busy')
        active_before = self.archive.inventory(active)
        self.run_archive(apply=True)
        self.assertEqual('12345', lock.read_text())
        self.assertEqual(active_before, self.archive.inventory(active))

    def test_noncompleted_marker_skipped(self):
        _, _, marker = self.fixture()
        record = json.loads(marker.read_text())
        record.update(status='failed', returncode=1)
        marker.write_text(json.dumps(record))
        before = self.snapshot()
        self.assertIn('SKIP', '\n'.join(self.run_archive(apply=True)))
        self.assertEqual(before, self.snapshot())

    def test_location_helper_missing_and_unrecognized_paths(self):
        for case in ('uniform_size_rng_0020_pos1000', 'normal_matched_size_rng_0020_pos1000', 'unrelated_case'):
            self.assertEqual(self.root / 'simulation_outputs' / case, self.locations.case_directory(self.root, case))

    def test_missing_both_with_final_record_is_error(self):
        case, source, _ = self.fixture()
        source.rename(self.root / 'not-a-result')
        with self.assertRaisesRegex((ValueError, RuntimeError), 'missing|Missing'):
            self.run_archive()

    def test_receipt_detects_modified_archived_bytes(self):
        case, _, _ = self.fixture()
        self.run_archive(apply=True)
        (self.locations.archived_directory(self.root, case) / 'extra').write_text('unexpected')
        with self.assertRaises((ValueError, RuntimeError)):
            self.run_archive(apply=True)

    def test_artifact_validation(self):
        for name, text in (('csv', 'time,strain,stress\n0,nan,1\n1,0,inf\n'), ('sta', 'analysis failed')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                case, source, _ = self.fixture()
                path = source / (case + '.csv') if name == 'csv' else source / 'abaqus_files' / (case + '.sta')
                path.write_text(text)
                with self.assertRaises((ValueError, RuntimeError)):
                    self.run_archive(apply=True)

    def test_symlink_rejection(self):
        _, source, _ = self.fixture()
        try:
            (source / 'linked').symlink_to(source / 'abaqus_files', target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises((ValueError, RuntimeError)):
            self.run_archive(apply=True)

    def test_location_helper_both_studies_and_conflicts(self):
        for study in ('uniform', 'normal-matched'):
            case, source, _ = self.fixture(study)
            dest = self.locations.archived_directory(self.root, case)
            self.assertEqual(source, self.locations.case_directory(self.root, case))
            dest.parent.mkdir(parents=True, exist_ok=True)
            source.rename(dest)
            self.assertEqual(dest, self.locations.case_directory(self.root, case))
            source.mkdir()
            with self.assertRaises((ValueError, RuntimeError)):
                self.locations.case_directory(self.root, case)
        for bad in ('../escape', '/absolute', 'uniform_size_rng_0000_pos1000', 'uniform_size_rng_0021_pos1000', 'normal_matched_size_rng_1_pos1000'):
            if '/' in bad:
                with self.assertRaises(ValueError):
                    self.locations.case_directory(self.root, bad)
            else:
                self.assertIsNone(self.locations.archived_directory(self.root, bad))


if __name__ == '__main__':
    unittest.main()
