"""Solver-free contracts for explicit signed-mean PE22 log display."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('pe22_plotting_test_module', ROOT / '00_Main_Scripts/roi_plotting.py')
plotting = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = plotting
SPEC.loader.exec_module(plotting)


class Pe22LogPlottingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('PE22_TEST_SCRATCH'))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.summary = self.root / 'roi_summary.csv'
        self.cycle = self.root / 'cycle.csv'
        self.domain = self.root / 'domain.csv'
        self.area = self.root / 'area.csv'
        self.out = self.root / 'plots'
        names = ['roi_left_01', 'roi_left_02', 'roi_left_09', 'roi_right_01']
        rows = []
        for frame, time, sign in [(85, .85, 1), (95, .95, -1)]:
            for name, value in zip(names, [2e-8, 1e-20, 0., .003]):
                rows.append(dict(roi_name=name, frame_number=frame, step_time=time,
                                 average_stress_mpa=sign*123., average_plastic_strain=sign*value,
                                 stress_intensity_factor=sign*2.4, plastic_strain_source='PE22',
                                 **{'Phase 0': 10., 'Phase 1': 20., 'Phase 2': 30., 'Phase 3': 40.}))
        pd.DataFrame(rows).to_csv(self.summary, index=False)
        self.cycle.write_text('ODB file name: fixture\nStep Time,U_Y,Total RF Y\n0.85,0.01,500\n0.95,-0.01,-500\n')
        pd.DataFrame([dict(frame_number=85, step_time=.85000002, average_plastic_strain=.0007),
                      dict(frame_number=95, step_time=.94999999, average_plastic_strain=-.0008)]).to_csv(self.domain, index=False)
        pd.DataFrame([dict(roi_name=name, **{'Phase 0': 10., 'Phase 1': 20., 'Phase 2': 30., 'Phase 3': 40.},
                           represented_area=1., expected_area=1., coverage_error=0.) for name in names]).to_csv(self.area, index=False)
        self.addCleanup(plotting.plt.close, 'all')

    def run_plots(self, **kwargs):
        self.assertTrue(hasattr(plotting, 'make_pe22_log_plots'), 'explicit PE22 log entrypoint is missing')
        return plotting.make_pe22_log_plots(self.summary, self.cycle, self.domain, self.area, self.out, **kwargs)

    def test_log_axes_signed_means_tiny_values_and_off_axis_zeros(self):
        captured = []
        with patch.object(plotting, '_save_figure', side_effect=lambda fig, path: captured.append((fig, path))):
            paths = self.run_plots(material_label='AA7075-T651')
        self.assertEqual(len(paths), 4)
        for fig, path in captured:
            self.assertIn('AA7075-T651', fig._suptitle.get_text())
            if 'full_response' not in str(path):
                self.assertEqual(list(fig.axes[0].lines[0].get_ydata()), [2.4]*3 if '85' in path.name else [-2.4]*3)
                self.assertEqual(len(fig.axes[2].containers), 4)
                continue
            positive = '85' in path.name
            stress, plastic, phase = fig.axes[0], fig.axes[2], fig.axes[4]
            self.assertEqual(stress.get_ylabel(), 'Stress (S22), MPa')
            self.assertEqual(plastic.get_ylabel(), 'Plastic strain (PE22)\n(log scale)')
            self.assertEqual(plastic.get_yscale(), 'log')
            np.testing.assert_array_equal(stress.lines[0].get_ydata(), [123. if positive else -123.]*3)
            values = np.asarray(plastic.lines[0].get_ydata(), dtype=float)
            np.testing.assert_array_equal(values[:2], [2e-8, 1e-20])
            self.assertTrue(np.isnan(values[2]))
            self.assertEqual(list(plastic.lines[1].get_ydata()), [.0007 if positive else .0008]*2)
            zeros = [line for line in plastic.lines if line.get_gid() == 'pe22-zero-band']
            self.assertEqual(len(zeros), 1)
            self.assertEqual(list(zeros[0].get_xdata()), [2])
            self.assertTrue(all(y < 0 for y in zeros[0].get_ydata()))
            self.assertIsNot(zeros[0].get_transform(), plastic.transData)
            self.assertEqual(zeros[0].get_markerfacecolor(), 'none')
            self.assertIn('0', [text.get_text() for text in plastic.texts])
            self.assertEqual(len(phase.containers), 4)
            self.assertLess(plastic.get_ylim()[0], 1e-20)

    def test_real_fixture_exports_and_audit_preserve_inputs(self):
        before = {p: p.read_bytes() for p in [self.summary, self.cycle, self.domain, self.area]}
        paths = self.run_plots()
        self.assertEqual({p.relative_to(self.out).as_posix() for p in paths}, {
            'full_response/frame85_grouped_by_side.png', 'full_response/frame95_grouped_by_side.png',
            'sif_area_fractions/frame85_sif_grouped_by_side.png', 'sif_area_fractions/frame95_sif_grouped_by_side.png'})
        for path in paths:
            self.assertGreater(path.stat().st_size, 1000)
            self.assertGreater(path.with_suffix('.svg').stat().st_size, 1000)
        record = json.loads((self.out / 'plot_generation.json').read_text())
        self.assertIn('abs(mean', record['display_policy'])
        self.assertIn('not mean(abs', record['display_policy'])
        self.assertEqual(record['scale'], 'log')
        self.assertEqual(len(record['zero_locations']), 2)
        negative = next(row for row in record['roi_values'] if row['frame_number'] == 95 and row['roi_name'] == 'roi_left_01')
        self.assertEqual(negative['raw_signed_pe22'], -2e-8)
        self.assertEqual(negative['display_pe22'], 2e-8)
        self.assertEqual(record['domain_values'][1]['raw_signed_pe22'], -.0008)
        for key, path in [('roi_summary', self.summary), ('cycle', self.cycle), ('domain_pe22', self.domain), ('area_fractions', self.area)]:
            self.assertEqual(record['sources'][key]['sha256'], hashlib.sha256(before[path]).hexdigest())
            self.assertEqual(path.read_bytes(), before[path])

    def test_invalid_inputs_fail_before_rendering_or_output(self):
        mutations = [
            ('source', self.summary, lambda d: d.assign(plastic_strain_source='legacy')),
            ('missing_source', self.summary, lambda d: d.drop(columns='plastic_strain_source')),
            ('duplicate_roi', self.summary, lambda d: pd.concat([d, d.iloc[:1]])),
            ('nonfinite', self.summary, lambda d: d.assign(average_plastic_strain=np.inf)),
            ('unknown_source', self.summary, lambda d: d.assign(plastic_strain_source='PEEQ')),
            ('domain_nonfinite', self.domain, lambda d: d.assign(average_plastic_strain=np.nan)),
            ('area_no_coverage', self.area, lambda d: d.drop(columns=['represented_area', 'expected_area', 'coverage_error'])),
            ('fractional_frame', self.summary, lambda d: d.assign(frame_number=85.5)),
            ('wrong_frame', self.domain, lambda d: d.assign(frame_number=[84, 95])),
            ('domain_time', self.domain, lambda d: d.assign(step_time=[.84, .95])),
            ('duplicate_domain', self.domain, lambda d: pd.concat([d, d.iloc[:1]])),
            ('summary_time', self.summary, lambda d: d.assign(step_time=.85)),
            ('area_vector', self.area, lambda d: d.assign(**{'Phase 0': 20., 'Phase 1': 10.})),
            ('area_coverage', self.area, lambda d: d.assign(represented_area=.5)),
            ('area_missing_roi', self.area, lambda d: d.iloc[:-1]),
            ('area_duplicate', self.area, lambda d: pd.concat([d, d.iloc[:1]])),
        ]
        for name, path, mutate in mutations:
            with self.subTest(name=name):
                original = path.read_bytes()
                mutate(pd.read_csv(path)).to_csv(path, index=False)
                try:
                    with patch.object(plotting, '_save_figure') as save:
                        with self.assertRaises(ValueError):
                            self.run_plots()
                        save.assert_not_called()
                    self.assertFalse(self.out.exists())
                finally:
                    path.write_bytes(original)
        original = self.cycle.read_text()
        self.cycle.write_text(original.replace('0.95,-', '0.94,-'))
        with self.assertRaises(ValueError):
            self.run_plots()
        self.assertFalse(self.out.exists())

    def test_signed_mean_precision_is_not_changed_by_csv_parser(self):
        text = self.summary.read_text().replace('2e-08', '0.008782916834598241')
        self.summary.write_text(text)
        captured = []
        with patch.object(plotting, '_save_figure', side_effect=lambda fig, path: captured.append((fig, path))):
            self.run_plots()
        fig = next(fig for fig, path in captured if path.name == 'frame85_grouped_by_side.png')
        self.assertEqual(float(fig.axes[2].lines[0].get_ydata()[0]), float('0.008782916834598241'))

    def test_zero_domain_and_all_zero_rois_have_no_positive_data(self):
        summary = pd.read_csv(self.summary).assign(average_plastic_strain=0.)
        summary.to_csv(self.summary, index=False)
        pd.read_csv(self.domain).assign(average_plastic_strain=0.).to_csv(self.domain, index=False)
        captured = []
        with patch.object(plotting, '_save_figure', side_effect=lambda fig, path: captured.append((fig, path))):
            self.run_plots()
        for fig, path in captured:
            if 'full_response' in str(path):
                for ax in fig.axes[2:4]:
                    self.assertEqual(ax.get_yscale(), 'log')
                    self.assertTrue(np.isnan(ax.lines[0].get_ydata()).all())
                    self.assertEqual(len(ax.lines), 2)  # NaN data and off-axis zero markers only.
                    self.assertIn('Whole-model PE22 = 0 (off log axis)', [t.get_text() for t in ax.texts])

    def test_pairwise_time_agreement_is_required(self):
        data = pd.read_csv(self.summary)
        data.loc[data.frame_number == 85, 'step_time'] = .8499992
        data.to_csv(self.summary, index=False)
        self.cycle.write_text(self.cycle.read_text().replace('0.85,', '0.8500008,'))
        with patch.object(plotting, '_save_figure') as save:
            with self.assertRaises(ValueError):
                self.run_plots()
            save.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_legacy_orchestration_rejects_pe22_without_rendering(self):
        with patch.object(plotting, '_save_figure') as save:
            with self.assertRaisesRegex(ValueError, 'PE22|pe22'):
                plotting.make_all_roi_plots(self.summary, self.cycle, self.out)
            save.assert_not_called()
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
