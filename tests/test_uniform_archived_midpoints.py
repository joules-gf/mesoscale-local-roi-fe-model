"""Solver-free regression checks for archived uniform midpoint locations."""
import importlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '01_Secondary_Scripts'))
plotter = importlib.import_module('plot_phase_lower_bound_vs_stress_1pct_all_cases')
spec = importlib.util.spec_from_file_location('uniform_mesh_quality_paths', ROOT / '01_Secondary_Scripts/automated_run_helpers/mesh_angle30_quality.py')
assert spec is not None and spec.loader is not None
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


class ArchivedUniformMidpoints(unittest.TestCase):
    def test_plotter_reads_all_24_cases_from_reference_simulations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            study = root / 'reference_outputs/Uniform Distribution/Sensitivity Study/lower-bound-diameter-equal-4all-phases'
            cases = [(f'bp_same_size_case_{i:02d}', value) for i, value in enumerate([10, 15, *range(25, 186, 10), 200], 1)]
            cases.extend(zip(plotter.MIDPOINTS, (70, 80, 150, 160)))
            self.assertEqual(len(cases), 24)
            for name, value in cases:
                folder = study / 'Simulations' / name
                folder.mkdir(parents=True)
                xml = '<input>' + f'<material><size><dist_type>uniform</dist_type><loc>{value / 1000}</loc></size></material>' * 4 + '</input>'
                (folder / (name + '_resolved_input.xml')).write_text(xml)
                (folder / (name + '.csv')).write_text('0,0,0\n1,0.01,100\n')
            with patch.object(plotter, 'ROOT', root), patch.object(plotter, 'STUDY', study):
                rows = plotter.collect_rows()
            self.assertEqual(len(rows), 24)
            self.assertEqual(sum(row['group'] == 'midpoint' for row in rows), 4)
            self.assertTrue(all('/Simulations/' in row['source_csv'].replace('\\', '/') for row in rows))

    def test_mesh_audit_midpoints_use_reference_simulations(self):
        destination = ROOT / 'reference_outputs/Uniform Distribution/Sensitivity Study/lower-bound-diameter-equal-4all-phases/Simulations'
        midpoints = [folder for folder, group in quality.all_cases() if group == 'midpoint']
        self.assertEqual(len(midpoints), 4)
        self.assertEqual({folder.parent for folder in midpoints}, {destination})
        self.assertEqual(quality.NEW_SOURCES[150].parent, destination)
        self.assertEqual(quality.NEW_SOURCES[160].parent, destination)


if __name__ == '__main__':
    unittest.main()
