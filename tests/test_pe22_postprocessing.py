import csv
import importlib.util
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '00_Main_Scripts' / 'roi_postprocessing.py'
spec = importlib.util.spec_from_file_location('roi_pe22', SCRIPT)
assert spec is not None and spec.loader is not None
roi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roi)


class DirectPe22Tests(unittest.TestCase):
    def report(self, folder, *, pe=True, elastic=False, values=(-0.006, 0, 0.0001), pe_header='         PE-PE22'):
        path = folder / 'roi_right_01_frame2.csv'
        headers = ['Frame', 'Material Name', '         S-S22']
        if pe:
            headers.append(pe_header)
        if elastic:
            headers.append('         E-E22')
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            for value in values:
                row = ['Step Time = 0.85', 'MATERIAL-0', -120]
                if pe:
                    row.append(value)
                if elastic:
                    row.append(0.02)
                writer.writerow(row)
        return path

    def test_direct_mean_signed_zero_small_values_and_no_modulus_dependence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.report(Path(tmp))
            for modulus in (0, -1, float('nan'), 70000):
                with self.subTest(modulus=modulus):
                    summary = roi.summarize_roi_report(path, plastic_strain_source='pe22', youngs_modulus_mpa=modulus)
                    self.assertAlmostEqual(summary.average_plastic_strain, -0.0059 / 3)
                    self.assertEqual(summary.average_stress_mpa, -120)
                    self.assertAlmostEqual(summary.stress_intensity_factor, 1.12 * -120 * math.sqrt(math.pi * 0.0001))

    def test_missing_pe22_never_falls_back_to_elastic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.report(Path(tmp), pe=False, elastic=True)
            with self.assertRaisesRegex(ValueError, 'PE-PE22'):
                roi.summarize_roi_report(path, plastic_strain_source='pe22')
            self.assertGreater(roi.summarize_roi_report(path, plastic_strain_source='legacy').average_plastic_strain, 0)

    def test_direct_rejects_missing_and_nonfinite_rows_instead_of_skipping(self):
        with tempfile.TemporaryDirectory() as tmp:
            for values in ((float('nan'), 0, 1), (float('inf'), 0, 1), ('', 0, 1), ()):
                path = self.report(Path(tmp), values=values)
                with self.subTest(values=values), self.assertRaises(ValueError):
                    roi.summarize_roi_report(path, plastic_strain_source='pe22')

    def test_folder_metadata_area_override_and_legacy_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'roi_reports_pe22'
            folder.mkdir()
            self.report(folder, elastic=True)
            area = Path(tmp) / 'roi_area_fractions.csv'
            area.write_text('roi_name,Phase 0,Phase 1,Phase 2,Phase 3\nroi_right_01,10,20,30,40\n')
            path = roi.write_roi_summary_csv(folder, plastic_strain_source='pe22', area_fractions_csv=area)
            direct = list(csv.DictReader(path.read_text().splitlines()))[0]
            self.assertEqual(direct['plastic_strain_source'], 'PE22')
            self.assertEqual(float(direct['Phase 3']), 40)
            self.assertAlmostEqual(float(direct['average_plastic_strain']), -0.0059 / 3)
            legacy = roi.summarize_roi_folder(folder)
            self.assertNotIn('plastic_strain_source', legacy.columns)

    def test_cli_defaults_to_direct_and_does_not_write_old_report_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'roi_reports_pe22'
            folder.mkdir()
            self.report(folder)
            result = subprocess.run([sys.executable, str(SCRIPT), '--roi-reports', str(folder)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            row = list(csv.DictReader((folder / 'roi_summary.csv').read_text().splitlines()))[0]
            self.assertEqual(row['plastic_strain_source'], 'PE22')
            self.assertFalse((root / 'roi_reports').exists())

    def test_pe22_header_padding_is_not_assumed_and_raw_file_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            for padding in ('', ' ' * 7, ' ' * 9):
                path = self.report(Path(tmp), pe_header=padding + 'PE-PE22')
                before = path.read_bytes()
                with self.subTest(padding=padding):
                    result = roi.summarize_roi_report(path, plastic_strain_source='pe22')
                    self.assertAlmostEqual(result.average_plastic_strain, -0.0059 / 3)
                    self.assertEqual(path.read_bytes(), before)

    def test_duplicate_normalized_headers_are_rejected_before_pandas_mangles_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'roi_right_01_frame2.csv'
            for second in ('PE-PE22', '       PE-PE22'):
                path.write_text(f'Frame,         S-S22,PE-PE22,{second}\nStep Time = 0.85,100,-.001,.9\n')
                with self.subTest(second=second), self.assertRaisesRegex(ValueError, 'duplicate|Duplicate'):
                    roi.summarize_roi_report(path, plastic_strain_source='pe22')

    def test_unknown_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'plastic_strain_source'):
                roi.summarize_roi_report(self.report(Path(tmp)), plastic_strain_source='typo')


if __name__ == '__main__':
    unittest.main()
