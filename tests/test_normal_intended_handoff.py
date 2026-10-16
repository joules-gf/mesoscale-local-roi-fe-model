"""Solver-free tests of the intended batch's predecessor success gate."""
import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HELPERS = Path(__file__).resolve().parents[1] / '01_Secondary_Scripts/automated_run_helpers'
sys.path.insert(0, str(HELPERS))
import run_normal_intended as runner


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.previous = self.root / 'simulation_outputs/previous'
        self.inputs = self.root / 'inputs'
        self.previous.mkdir(parents=True)
        self.inputs.mkdir()
        self.patches = [patch.object(runner, 'ROOT', self.root), patch.object(runner, 'PREVIOUS', self.previous), patch.object(runner, 'MATCHED_INPUTS', self.inputs)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def successful_fixture(self):
        rows = []
        summary = []
        for index in range(21):
            case = f'test_case_{index:02d}'
            path = self.inputs / (case + '.xml')
            path.write_text('<input/>')
            rows.append({'case': case, 'input_file': path.name})
            summary.append({'case': case, 'status': 'completed', 'returncode': '0'})
            (self.previous / (case + '.completed.json')).write_text(json.dumps({'input_sha256': runner.engine.digest(path), 'status': 'completed', 'returncode': 0}))
            dest = self.root / 'simulation_outputs' / case
            (dest / 'abaqus_files').mkdir(parents=True)
            (dest / 'abaqus_files' / (case + '.sta')).write_text('THE ANALYSIS HAS COMPLETED SUCCESSFULLY')
            (dest / (case + '.csv')).write_text('strain,stress\n0,0\n0.01,1\n')
        for path, data in [(self.inputs / 'manifest.csv', rows), (self.previous / 'runtime_summary.csv', summary)]:
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(data[0]))
                writer.writeheader()
                writer.writerows(data)
        (self.previous / 'COMPLETED.txt').write_text('unit-test fixture')
        return rows

    def test_active_predecessor_waits_even_with_completion_file(self):
        self.successful_fixture()
        (self.previous / 'RUNNING.lock').write_text('fixture')
        self.assertFalse(runner.predecessor_ready())

    def test_stopped_without_completion_blocks(self):
        with self.assertRaisesRegex(RuntimeError, 'stopped'):
            runner.predecessor_ready()

    def test_all_verified_allows_handoff(self):
        self.successful_fixture()
        self.assertTrue(runner.predecessor_ready())

    def test_changed_input_blocks(self):
        rows = self.successful_fixture()
        (self.inputs / rows[0]['input_file']).write_text('<changed/>')
        with self.assertRaisesRegex(RuntimeError, 'verification failed'):
            runner.predecessor_ready()

    def test_missing_result_blocks(self):
        rows = self.successful_fixture()
        case = rows[0]['case']
        (self.root / 'simulation_outputs' / case / (case + '.csv')).unlink()
        with self.assertRaisesRegex(RuntimeError, 'verification failed'):
            runner.predecessor_ready()

    def test_missing_completion_record_blocks(self):
        rows = self.successful_fixture()
        (self.previous / (rows[0]['case'] + '.completed.json')).unlink()
        with self.assertRaisesRegex(RuntimeError, 'record set mismatch'):
            runner.predecessor_ready()

    def test_failed_summary_blocks(self):
        self.successful_fixture()
        path = self.previous / 'runtime_summary.csv'
        path.write_text(path.read_text().replace('completed,0', 'failed,1', 1))
        with self.assertRaisesRegex(RuntimeError, '21 successful'):
            runner.predecessor_ready()


if __name__ == '__main__':
    unittest.main()
