"""Solver-free tests for round-2 plot composition and mean markers."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'01_Secondary_Scripts'))
import plot_normal_stress_and_mesh_quality as plot
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba


class Round2FigureTests(unittest.TestCase):
    def test_mean_not_median_and_round2_color(self):
        fig, ax = plt.subplots()
        try:
            data = [np.array([0.1,0.11,0.12,0.49])]
            count = plot.draw_violins(ax, data, [130.0], 'tab:orange')
            self.assertEqual(count, 1)
            self.assertNotAlmostEqual(float(data[0].mean()), float(np.median(data[0])))
            np.testing.assert_allclose(ax.collections[0].get_facecolor()[0,:3], to_rgba('tab:orange')[:3])
            # Mean collection follows the violin body; this is not its median.
            np.testing.assert_allclose(ax.collections[1].get_segments()[0][:,1], data[0].mean())
        finally:
            plt.close(fig)

    def test_combined_24_case_round_membership_and_numeric_order(self):
        # Explicit fixtures, never used as scientific results or figure data.
        original_diameters = [10,15,25,35,45,50,55,65,75,85,95,105,115,125,135,145,155,165,175,185,200]
        first = [{'case':f'fixture_round1_{d}', 'mean_diameter_microns':float(d)} for d in original_diameters]
        second = [{'case':f'normal_round2_mean_{d:03d}um','mean_diameter_microns':float(d)} for d in (120,130,140)]
        with patch.object(plot,'collect_rows',side_effect=[first,second]) as collect:
            rows=plot.study_rows(True)
        self.assertEqual(len(rows),24)
        self.assertEqual(sum(r['round']==1 for r in rows),21)
        self.assertEqual([r['mean_diameter_microns'] for r in rows if r['round']==2],[120,130,140])
        self.assertEqual([r['mean_diameter_microns'] for r in rows],sorted(r['mean_diameter_microns'] for r in rows))
        self.assertEqual(collect.call_args.args[1],{f'normal_round2_mean_{d:03d}um' for d in (120,130,140)})

    def test_missing_round2_results_are_not_silently_omitted(self):
        with patch.object(plot,'collect_rows',side_effect=[[{'case':str(i),'mean_diameter_microns':i} for i in range(21)],FileNotFoundError('missing actual round2 result')]):
            with self.assertRaises(FileNotFoundError):
                plot.study_rows(True)


if __name__=='__main__':
    unittest.main()
