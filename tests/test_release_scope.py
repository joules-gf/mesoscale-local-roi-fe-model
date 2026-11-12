"""Verify the candidate's declared files and example include closure."""
import ast
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class ReleaseScopeTests(unittest.TestCase):
    def test_manifest_paths_exist_and_stay_in_repository(self):
        data = json.loads((ROOT / 'docs/RELEASE_SCOPE.json').read_text())
        paths = data['included_files']
        self.assertEqual(len(paths), len(set(paths)))
        for name in paths:
            with self.subTest(path=name):
                path = ROOT / name
                self.assertTrue(path.is_file())
                self.assertTrue(path.resolve().is_relative_to(ROOT.resolve()))
        self.assertFalse(any(name.startswith(('01_Secondary_Scripts/', 'archive/')) for name in paths))
        self.assertFalse(any('matched-uniform' in name for name in paths))

    def test_example_includes_are_all_supplied(self):
        data = json.loads((ROOT / 'docs/RELEASE_SCOPE.json').read_text())
        supplied = set(data['included_files'])
        for name in supplied:
            if not name.startswith('simulation_inputs/') or not name.endswith('.xml'):
                continue
            tree = ET.parse(ROOT / name)
            for element in tree.iter('include'):
                self.assertIsNotNone(element.text)
                child = (ROOT / name).parent / (element.text or '').strip()
                self.assertIn(child.relative_to(ROOT).as_posix(), supplied)
                self.assertTrue(child.is_file())

    def test_private_attribution_metadata_is_not_in_release(self):
        data = json.loads((ROOT / 'docs/RELEASE_SCOPE.json').read_text())
        self.assertNotIn('docs/CONTRIBUTIONS.json', data['included_files'])
        # The release must work without the separately retained private ledger.
        self.assertNotIn('!/docs/CONTRIBUTIONS.json', (ROOT / '.gitignore').read_text())

    def test_required_runtime_additions_are_declared(self):
        data = json.loads((ROOT / 'docs/RELEASE_SCOPE.json').read_text())
        declared = set(data['included_files'])
        # Only inspect the declared release roots: a normal working checkout may
        # also retain ignored historical research files. Exact-tree verification
        # for publication compares the complete Git index externally.
        self.assertIn('tests/test_release_scope.py', declared)
        self.assertIn('00_Main_Scripts/abaqus_odb_frame_inventory.py', declared)
        self.assertIn('00_Main_Scripts/roi_area_fractions.py', declared)

    def test_core_syntax_compiles_without_importing_abaqus(self):
        data = json.loads((ROOT / 'docs/RELEASE_SCOPE.json').read_text())
        for name in data['included_files']:
            if name.endswith('.py'):
                with self.subTest(file=name):
                    ast.parse((ROOT / name).read_text(encoding='utf-8-sig'), filename=name)

    def test_roi_template_requires_explicit_frame_selection(self):
        data = json.loads((ROOT / 'docs/roi_report_config.example.json').read_text())
        self.assertEqual(data['frames'], [])
        self.assertTrue(data['save_clean_backup'])
        self.assertTrue(data['reset_from_clean_backup'])


if __name__ == '__main__':
    unittest.main()
