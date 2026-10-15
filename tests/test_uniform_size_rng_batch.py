"""Unit tests only: solver subprocess is mocked; no physical simulation runs."""
import csv
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('uniform_batch', REPO / '01_Secondary_Scripts/automated_run_helpers/run_uniform_size_rng.py')
assert SPEC is not None and SPEC.loader is not None
batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs = self.root / 'inputs'
        shutil.copytree(batch.INPUTS, self.inputs)
        self.patches = [patch.object(batch, 'ROOT', self.root), patch.object(batch, 'INPUTS', self.inputs), patch.object(batch, 'BATCH', self.root / 'simulation_outputs/batch')]
        for item in self.patches:
            item.start()
        self.calls = []

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def fake_solver(self, command, **kwargs):
        self.calls.append(command)
        case = Path(command[-1]).stem
        dest = self.root / 'simulation_outputs' / case
        (dest / 'abaqus_files').mkdir(parents=True)
        (dest / 'abaqus_files' / (case + '.sta')).write_text('THE ANALYSIS HAS COMPLETED SUCCESSFULLY')
        (dest / (case + '.csv')).write_text('strain,stress\n0,0\n0.01,1\n')
        return subprocess.CompletedProcess(command, 0)

    def test_twenty_ordered_and_resume(self):
        rows = batch.load_cases()
        with patch.object(batch.subprocess, 'run', side_effect=self.fake_solver):
            batch.run_batch(rows)
            batch.run_batch(rows)
        self.assertEqual(len(self.calls), 20)
        self.assertEqual([Path(c[-1]).stem for c in self.calls], [r['case'] for r in rows])
        self.assertTrue(all(c[0] == batch.sys.executable for c in self.calls))
        with (batch.BATCH / 'runtime_summary.csv').open() as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 20)

    def test_zero_exit_without_artifacts_is_failure(self):
        with patch.object(batch.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as call:
            with self.assertRaisesRegex(RuntimeError, 'Batch stopped'):
                batch.run_batch(batch.load_cases())
            self.assertEqual(call.call_count, 1)
        self.assertFalse(list(batch.BATCH.glob('*.completed.json')))

    def test_nonzero_exit_stops_batch(self):
        with patch.object(batch.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as call:
            with self.assertRaisesRegex(RuntimeError, 'Batch stopped'):
                batch.run_batch(batch.load_cases())
            self.assertEqual(call.call_count, 1)

    def test_partial_output_refused(self):
        rows = batch.load_cases()
        (self.root / 'simulation_outputs' / rows[0]['case']).mkdir(parents=True)
        with patch.object(batch.subprocess, 'run') as call:
            with self.assertRaisesRegex(RuntimeError, 'Output already exists'):
                batch.run_batch(rows)
            call.assert_not_called()

    def test_changed_control_rejected(self):
        path = next(self.inputs.glob('*.xml'))
        path.write_text(path.read_text().replace('<position> 1000 </position>', '<position> 999 </position>'))
        with self.assertRaises(ValueError):
            batch.load_cases()

    def test_explicit_scale_rejected(self):
        path = next(self.inputs.glob('*.xml'))
        path.write_text(path.read_text().replace('</loc>', '</loc><scale>0.01</scale>', 1))
        with self.assertRaises(ValueError):
            batch.load_cases()

    def test_changed_completed_input_refused(self):
        rows = batch.load_cases()[:1]
        with patch.object(batch.subprocess, 'run', side_effect=self.fake_solver):
            batch.run_batch(rows)
        path = self.inputs / rows[0]['input_file']
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(RuntimeError, 'mismatch'):
            batch.run_batch(rows)


if __name__ == '__main__':
    unittest.main()
