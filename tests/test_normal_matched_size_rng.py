"""Solver-free tests; subprocess and FE result artifacts are explicit test fixtures."""
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('normal_rng', REPO / '01_Secondary_Scripts/automated_run_helpers/run_normal_matched_size_rng.py')
assert SPEC is not None and SPEC.loader is not None
batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch)


class NormalRNGTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs, self.uniform = self.root / 'inputs', self.root / 'uniform'
        shutil.copytree(batch.INPUTS, self.inputs)
        shutil.copytree(batch.UNIFORM, self.uniform)
        self.patches = [patch.object(batch, 'ROOT', self.root), patch.object(batch, 'INPUTS', self.inputs), patch.object(batch, 'UNIFORM', self.uniform), patch.object(batch, 'BATCH', self.root / 'simulation_outputs/batch')]
        for item in self.patches:
            item.start()
        self.calls = []
        self.console = contextlib.redirect_stdout(io.StringIO())
        self.console.__enter__()
        # Copy the runner so its self-referencing child command stays portable.
        destination = self.root / Path(batch.__file__).relative_to(REPO)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(batch.__file__, destination)
        self.file_patch = patch.object(batch, '__file__', str(destination))
        self.file_patch.start()

    def tearDown(self):
        self.file_patch.stop()
        self.console.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def fake_process(self, command, **kwargs):
        self.calls.append(command)
        case = Path(command[-1]).stem
        dest = self.root / 'simulation_outputs' / case
        (dest / 'abaqus_files').mkdir(parents=True)
        (dest / 'abaqus_files' / (case + '.sta')).write_text('THE ANALYSIS HAS COMPLETED SUCCESSFULLY')
        (dest / (case + '.csv')).write_text('time,strain,stress\n0,0,0\n1,0.01,1\n')
        process = MagicMock()
        process.__enter__.return_value = process
        process.stdout = iter(['unit-test progress\n'])
        process.wait.return_value = 0
        self.assertEqual(kwargs['env']['MPLBACKEND'], 'Agg')
        self.assertEqual(kwargs['env']['MICROSTRUCTURE_NONINTERACTIVE'], '1')
        self.assertEqual(kwargs['cwd'], self.root)
        return process

    def test_plan_twenty_only_size_seed_varies(self):
        rows = batch.load_cases()
        self.assertEqual(len(rows), 20)
        patterns = []
        for row in rows:
            root = batch.ET.parse(self.inputs / row['input_file']).getroot()
            root.find('settings/rng_seeds/size').text = 'VARIED'
            patterns.append([(e.tag, (e.text or '').strip()) for e in root.iter()])
        self.assertTrue(all(p == patterns[0] for p in patterns))

    def test_run_order_live_log_and_resume(self):
        rows = batch.load_cases()
        with patch.object(batch.subprocess, 'Popen', side_effect=self.fake_process):
            batch.run_batch(rows)
            batch.run_batch(rows)
        self.assertEqual(len(self.calls), 20)
        self.assertEqual([Path(c[-1]).stem for c in self.calls], [r['case'] for r in rows])
        self.assertTrue(all(c[0] == batch.sys.executable for c in self.calls))
        self.assertIn('unit-test progress', next(batch.BATCH.glob('*.log')).read_text())
        with (batch.BATCH / 'runtime_summary.csv').open() as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 20)

    def test_missing_artifacts_stops_even_zero_exit(self):
        process = MagicMock()
        process.__enter__.return_value = process
        process.stdout = iter([])
        process.wait.return_value = 0
        with patch.object(batch.subprocess, 'Popen', return_value=process) as launch:
            with self.assertRaisesRegex(RuntimeError, 'Batch stopped'):
                batch.run_batch(batch.load_cases())
            self.assertEqual(launch.call_count, 1)

    def test_nonzero_exit_stops(self):
        process = MagicMock()
        process.__enter__.return_value = process
        process.stdout = iter(['unit-test failure'])
        process.wait.return_value = 1
        with patch.object(batch.subprocess, 'Popen', return_value=process) as launch:
            with self.assertRaisesRegex(RuntimeError, 'Batch stopped'):
                batch.run_batch(batch.load_cases())
            self.assertEqual(launch.call_count, 1)

    def test_existing_partial_output_refused(self):
        rows = batch.load_cases()
        (self.root / 'simulation_outputs' / rows[0]['case']).mkdir(parents=True)
        with patch.object(batch.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(RuntimeError, 'Unrecorded output'):
                batch.run_batch(rows)
            launch.assert_not_called()

    def test_changed_completed_input_refused(self):
        rows = batch.load_cases()[:1]
        with patch.object(batch.subprocess, 'Popen', side_effect=self.fake_process):
            batch.run_batch(rows)
        path = self.inputs / rows[0]['input_file']
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(RuntimeError, 'mismatch'):
            batch.run_batch(rows)

    def test_wrong_position_seed_rejected(self):
        path = next(self.inputs.glob('*.xml'))
        path.write_text(path.read_text().replace('<position> 1000 </position>', '<position> 999 </position>'))
        with self.assertRaises(ValueError):
            batch.load_cases()

    def test_missing_matched_scale_rejected(self):
        path = next(self.inputs.glob('*.xml'))
        root = batch.ET.parse(path).getroot()
        size = root.find('material/size')
        size.remove(size.find('scale'))
        path.write_text(batch.ET.tostring(root, encoding='unicode'))
        with self.assertRaises(ValueError):
            batch.load_cases()

    def test_curve_requires_numeric_rows(self):
        rows = batch.load_cases()[:1]
        with patch.object(batch.subprocess, 'Popen', side_effect=self.fake_process):
            batch.run_batch(rows)
        case = rows[0]['case']
        curve = self.root / 'simulation_outputs' / case / (case + '.csv')
        curve.write_text('header\nnot,numeric,data\nnot,numeric,data\n')
        self.assertFalse(batch.artifacts_ok(case))


if __name__ == '__main__':
    unittest.main()
