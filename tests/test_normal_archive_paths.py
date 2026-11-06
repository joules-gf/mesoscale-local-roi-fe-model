"""Solver-free archive regression tests using disposable synthetic artifacts."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '01_Secondary_Scripts'))
import plot_normal_mean_diameter_vs_stress_1pct as stress
import plot_normal_stress_and_mesh_quality as mesh

spec = importlib.util.spec_from_file_location('archive_runner', ROOT / '01_Secondary_Scripts/automated_run_helpers/run_normal_equal_mean.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
ARCHIVE = Path('reference_outputs/Normal Distribution/Sensitivity Study/Uniform Mean Diameter Change')


class ArchivePaths(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.batch = self.root / 'simulation_outputs/normal_equal_mean_batch'
        self.batch.mkdir(parents=True)
        for module in (runner, stress, mesh):
            self.enterContext(patch.object(module, 'ROOT', self.root))
        for module in (runner, stress):
            self.enterContext(patch.object(module, 'BATCH', self.batch))
        self.enterContext(patch.object(mesh, 'OUT', self.batch))

    def fixture(self, case='bp_same_size_case_01', archived=True):
        folder = self.root / (ARCHIVE if archived else Path('simulation_outputs')) / case
        (folder / 'abaqus_files').mkdir(parents=True)
        xml = '<root><domain><side_length>1</side_length></domain>' + '<material><size><dist_type>norm</dist_type><loc>0.05</loc></size></material>' * 4 + '</root>'
        source = self.root / (case + '.xml')
        source.write_text(xml)
        (folder / (case + '_resolved_input.xml')).write_text(xml)
        (folder / (case + '.csv')).write_text('0,0,0\n1,0.01,100\n')
        (folder / 'abaqus_files' / (case + '.sta')).write_text('THE ANALYSIS HAS COMPLETED SUCCESSFULLY')
        (folder / 'abaqus_files' / (case + '.inp')).write_text('*Node\n1,0,0\n2,1,0\n3,0,1\n*Element, type=CPS3\n1,1,2,3\n')
        row = dict(case=case, input=source.name, mean_mm=0.05, input_sha256=runner.digest(source))
        (self.batch / (case + '.completed.json')).write_text(json.dumps(dict(row, returncode=0)))
        (self.batch / 'manifest.json').write_text(json.dumps([row]))
        return folder, row

    def test_archived_artifacts_and_resume_never_spawn_solver(self):
        folder, row = self.fixture()
        self.assertTrue(runner.artifacts_ok(row['case']))
        with patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('solver forbidden')) as spawn:
            runner.run_batch([row])
        spawn.assert_not_called()
        self.assertTrue((self.batch / (row['case'] + '.completed.json')).is_file())
        self.assertFalse((self.root / 'simulation_outputs' / row['case']).exists())

    def test_archived_collect_and_mesh_audit(self):
        folder, row = self.fixture()
        rows = stress.collect_rows(expected_cases={row['case']})
        self.assertEqual(rows[0]['source_csv'], str((folder / (row['case'] + '.csv')).relative_to(self.root)))
        summary, _ = mesh.audit(rows[0])
        self.assertEqual(summary['triangle_count'], 1)
        self.assertEqual(summary['source_mesh'], str((folder / 'abaqus_files' / (row['case'] + '.inp')).relative_to(self.root)))

    def test_duplicate_locations_rejected_by_all_consumers(self):
        folder, row = self.fixture()
        (self.root / 'simulation_outputs' / row['case']).mkdir()
        for call in (lambda: runner.artifacts_ok(row['case']), lambda: runner.preflight([row]), lambda: stress.collect_rows(expected_cases={row['case']}), lambda: mesh.audit(row)):
            with self.subTest(call=call), self.assertRaisesRegex(RuntimeError, 'duplicate|Duplicate|Ambiguous'):
                call()

    def test_archived_unrecorded_output_is_not_resubmitted(self):
        _, row = self.fixture()
        (self.batch / (row['case'] + '.completed.json')).unlink()
        with self.assertRaisesRegex(RuntimeError, 'unrecorded'):
            runner.preflight([row])

    def test_original_and_round2_locations_still_work(self):
        for case in ('bp_same_size_baseline_0p050', 'normal_round2_mean_120um', 'uniform_midpoint_fixture'):
            with self.subTest(case=case):
                _, row = self.fixture(case, archived=False)
                self.assertTrue(runner.artifacts_ok(case))
                runner.preflight([row])
                self.assertEqual(len(stress.collect_rows(expected_cases={case})), 1)

    def test_incomplete_archived_result_blocks_resume(self):
        folder, row = self.fixture()
        (folder / (row['case'] + '.csv')).unlink()
        self.assertFalse(runner.artifacts_ok(row['case']))
        with self.assertRaisesRegex(RuntimeError, 'Invalid previous completion'):
            runner.preflight([row])


if __name__ == '__main__':
    unittest.main()
