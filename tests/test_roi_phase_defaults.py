"""Release defaults: phase merging is explicit, never inferred from labels."""
import importlib.util
import inspect
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / '00_Main_Scripts' / 'roi_plotting.py'


class PhaseGroupingDefaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('release_roi_plotting', SCRIPT)
        assert spec is not None and spec.loader is not None
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def test_default_groups_preserve_each_phase(self):
        groups = self.module.phase_plot_groups()
        self.assertEqual([columns for _, columns, _ in groups],
                         [['Phase 0'], ['Phase 1'], ['Phase 2'], ['Phase 3']])

    def test_all_public_plot_entry_points_default_to_separate(self):
        for name in ('phase_plot_groups', 'plot_full_response',
                     'plot_sif_volume_fraction_comparison',
                     'plot_representative_comparison', 'make_all_roi_plots'):
            with self.subTest(function=name):
                parameter = inspect.signature(getattr(self.module, name)).parameters['combine_equal_yield_phases']
                self.assertIs(parameter.default, False)

    def test_explicit_combination_is_still_available(self):
        groups = self.module.phase_plot_groups(combine_equal_yield_phases=True)
        self.assertIn(['Phase 2', 'Phase 3'], [columns for _, columns, _ in groups])

    def cli(self, *options):
        argv = ['roi_plotting.py', '--roi-summary', 'summary.csv',
                '--cycle-csv', 'curve.csv', '--output-root', 'plots', *options]
        with patch.object(sys, 'argv', argv), patch.object(self.module, 'make_all_roi_plots', return_value=[]) as make:
            self.module.main()
            return make.call_args.kwargs['combine_equal_yield_phases']

    def test_cli_defaults_to_separate(self):
        self.assertIs(self.cli(), False)

    def test_cli_combination_requires_explicit_option(self):
        self.assertIs(self.cli('--combine-equal-yield-phases'), True)

    def test_legacy_separate_option_remains_accepted(self):
        self.assertIs(self.cli('--separate-phases'), False)

    def test_conflicting_cli_grouping_options_are_rejected(self):
        with self.assertRaises(SystemExit) as caught:
            self.cli('--combine-equal-yield-phases', '--separate-phases')
        self.assertEqual(caught.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
