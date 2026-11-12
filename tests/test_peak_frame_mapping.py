import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '00_Main_Scripts' / 'peak_detection.py'
spec = importlib.util.spec_from_file_location('peaks', SCRIPT)
assert spec is not None and spec.loader is not None
peaks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(peaks)


def inventory():
    return {'steps': [{'name': 'Load', 'frames': [
        {'index': 0, 'time': 0, 'increment': 0},
        {'index': 1, 'time': 0.13, 'increment': 10},
        {'index': 2, 'time': 0.85, 'increment': 159},
        {'index': 3, 'time': 0.93, 'increment': 180},
        {'index': 4, 'time': 1.0, 'increment': 200}]}]}


class FrameMappingTests(unittest.TestCase):
    def curve(self, root, stress='-2,-1,-3,-5,-2'):
        folder = root / 'case_a'
        folder.mkdir(exist_ok=True)
        path = folder / 'case_a.csv'
        path.write_text('ODB file name: case_a\nStep Time,Total RF Y\n' + ''.join(
            f'{t},{s}\n' for t, s in zip([0, .13, .85, .93, 1], stress.split(','))))
        return folder, path

    def test_irregular_times_match_index_not_increment_or_scaled_time(self):
        self.assertEqual(peaks.match_frame_times([.85, .93, None], inventory()), [2, 3, None])
        inv = {'steps': [{'name': 'Load', 'frames': [
            {'index': i, 'time': i / 100, 'increment': i + 74} for i in range(101)]}]}
        self.assertEqual(peaks.match_frame_times([.85], inv), [85])

    def test_default_returns_actual_times_without_invented_indices(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, _ = self.curve(Path(tmp))
            result = peaks.last_stress_peak_times(folder)
            self.assertEqual(result.raw_times, [.13, .93])
            self.assertEqual(result.frame_numbers, [None, None])
            matched = peaks.last_stress_peak_times(folder, frame_inventory=inventory())
            self.assertEqual(matched.frame_numbers, [1, 3])
            legacy = peaks.last_stress_peak_times(folder, time_to_frame_scale=100)
            self.assertEqual(legacy.frame_numbers, [13, 93])
            with self.assertRaises(ValueError):
                peaks.last_stress_peak_times(folder, frame_inventory=inventory(), time_to_frame_scale=100)

    def test_close_unselected_frames_do_not_invalidate_unique_target_match(self):
        inv = inventory()
        inv['steps'][0]['frames'][1]['time'] = 0.0000001
        self.assertEqual(peaks.match_frame_times([.85], inv), [2])

    def test_tolerance_missing_ambiguous_bounds_and_nonfinite(self):
        self.assertEqual(peaks.match_frame_times([.8500005], inventory()), [2])
        for times in ([.850002], [-.01], [1.01], [float('nan')], [float('inf')]):
            with self.subTest(times=times), self.assertRaises(ValueError):
                peaks.match_frame_times(times, inventory())
        for field, value in [('index', 99), ('index', 1), ('index', True), ('time', float('nan')), ('time', .13), ('time', .1300005)]:
            inv = inventory()
            inv['steps'][0]['frames'][2][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                peaks.match_frame_times([.13], inv)
        inv = inventory()
        del inv['steps'][0]['frames'][2]['time']
        with self.assertRaises(ValueError):
            peaks.match_frame_times([.85], inv)

    def test_multiple_steps_require_explicit_same_step(self):
        inv = inventory()
        other = copy.deepcopy(inv['steps'][0])
        other['name'] = 'Unload'
        inv['steps'].append(other)
        with self.assertRaises(ValueError):
            peaks.match_frame_times([.85], inv)
        self.assertEqual(peaks.match_frame_times([.85], inv, step_name='Load'), [2])
        with self.assertRaises(ValueError):
            peaks.match_frame_times([.85], inv, step_name='Missing')
        inv['steps'][1]['name'] = 'Load'
        with self.assertRaises(ValueError):
            peaks.match_frame_times([.85], inv, step_name='Load')

    def test_signed_plateau_extrema_use_middle_sample_without_absolute_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'case_plateau'
            folder.mkdir()
            path = folder / 'case_plateau.csv'
            path.write_text('ODB file name: case_plateau\nStep Time,Total RF Y\n' + ''.join(
                f'{i / 10},{value}\n' for i, value in enumerate([-3, -1, -1, -1, -3, -5, -5, -3])))
            result = peaks.last_stress_peak_times(folder)
            self.assertEqual(result.raw_times, [.2, .5])
            self.assertEqual(result.frame_numbers, [None, None])

    def test_nonfinite_curve_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for stress in ('0,nan,0,-1,0', '0,inf,0,-1,0'):
                folder, _ = self.curve(Path(tmp), stress)
                with self.assertRaises(ValueError):
                    peaks.last_stress_peak_times(folder)
            _, path = self.curve(Path(tmp))
            path.write_text(path.read_text().replace('0.13,', 'nan,'))
            with self.assertRaises(ValueError):
                peaks.last_stress_peak_times(path.parent)

    def test_cli_inventory_file_csv_and_case_write_readable_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder, path = self.curve(root)
            inv = root / 'inventory.json'
            inv.write_text(json.dumps(inventory()))
            output = root / 'selection.json'
            for option, value in [('--csv', path), ('--case-folder', folder)]:
                result = subprocess.run([sys.executable, str(SCRIPT), option, str(value), '--frame-inventory', str(inv), '--output-json', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data, json.loads(output.read_text()))
                self.assertEqual(data['frame_numbers'], [1, 3])
                self.assertEqual(data['raw_times'], [.13, .93])
                self.assertEqual(data['step_name'], 'Load')


if __name__ == '__main__':
    unittest.main()
