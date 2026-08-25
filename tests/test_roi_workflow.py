import csv
import importlib.util
import math
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "00_Main_Scripts"


def load_module(module_name):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PeakDetectionTests(unittest.TestCase):
    def test_last_stress_peak_times_returns_raw_times_and_scaled_frame_numbers(self):
        peak_detection = load_module("peak_detection")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "case_a"
            folder.mkdir()
            csv_path = folder / "case_a.csv"
            csv_path.write_text(
                "ODB file name: case_a\n"
                "Step Time,U_Y,Total RF Y\n"
                "0.00,0.0,0.0\n"
                "0.10,0.1,10.0\n"
                "0.20,0.0,0.0\n"
                "0.30,-0.1,-5.0\n"
                "0.40,0.0,0.0\n"
                "0.50,0.2,12.0\n"
                "0.60,0.0,0.0\n"
                "0.70,-0.2,-7.0\n"
                "0.80,0.0,0.0\n"
            )

            result = peak_detection.last_stress_peak_times(folder)

        self.assertEqual(result.raw_times, [0.5, 0.7])
        self.assertEqual(result.frame_numbers, [50, 70])


class RoiGeometryTests(unittest.TestCase):
    def test_default_edge_roi_specs_are_named_for_left_and_right_border_regions(self):
        roi_export = load_module("abaqus_roi_report_export")

        specs = roi_export.build_edge_roi_specs(width=1.0, height=1.0, radius=0.1, count_per_side=2)

        self.assertEqual([spec.name for spec in specs], ["roi_right_01", "roi_right_02", "roi_left_01", "roi_left_02"])
        self.assertEqual(specs[0].center, (1.0, 0.9))
        self.assertEqual(specs[0].side, "right")
        self.assertEqual(specs[2].center, (0.0, 0.9))
        self.assertEqual(specs[2].side, "left")
        self.assertTrue(specs[0].contains_centroid((0.95, 0.9)))
        self.assertFalse(specs[0].contains_centroid((0.85, 0.9)))
        self.assertTrue(specs[2].contains_centroid((0.05, 0.9)))
        self.assertFalse(specs[2].contains_centroid((0.15, 0.9)))


class RoiPostprocessingTests(unittest.TestCase):
    def test_roi_summary_computes_mechanics_and_phase_fractions_from_report_csv(self):
        roi_postprocessing = load_module("roi_postprocessing")
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "roi_right_01_frame50.csv"
            report.write_text(
                "Frame,Element Label,Material Name,         S-S22,         E-E22\n"
                "Step Time = 0.5,1,MATERIAL-0,100.0,0.0030\n"
                "Step Time = 0.5,2,MATERIAL-1,200.0,0.0040\n"
            )

            summary = roi_postprocessing.summarize_roi_report(report, youngs_modulus_mpa=100000.0, crack_length_m=0.0001)

        self.assertEqual(summary.roi_name, "roi_right_01")
        self.assertEqual(summary.frame_number, 50)
        self.assertAlmostEqual(summary.step_time, 0.5)
        self.assertAlmostEqual(summary.average_stress_mpa, 150.0)
        self.assertAlmostEqual(summary.average_plastic_strain, 0.0020)
        expected_ki = 1.12 * 150.0 * math.sqrt(math.pi * 0.0001)
        self.assertAlmostEqual(summary.stress_intensity_factor, expected_ki)
        self.assertEqual(summary.phase_fractions, {"Phase 0": 50.0, "Phase 1": 50.0, "Phase 2": 0.0, "Phase 3": 0.0})

    def test_compute_r_ratio_uses_min_over_max_for_each_roi_and_global_curve(self):
        roi_postprocessing = load_module("roi_postprocessing")
        high = {"roi_left_01": 100.0, "roi_right_01": 80.0}
        low = {"roi_left_01": -25.0, "roi_right_01": -40.0}

        result = roi_postprocessing.compute_r_ratios(high, low, global_high_stress=120.0, global_low_stress=-30.0)

        self.assertAlmostEqual(result.local_r_ratios["roi_left_01"], -0.25)
        self.assertAlmostEqual(result.local_r_ratios["roi_right_01"], -0.5)
        self.assertAlmostEqual(result.global_r_ratio, -0.25)


if __name__ == "__main__":
    unittest.main()
