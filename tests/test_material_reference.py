import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "00_Main_Scripts"
MODULE_PATH = SCRIPT_DIR / "material_reference.py"


def load_material_reference_module():
    spec = importlib.util.spec_from_file_location("material_reference", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MaterialReferenceTests(unittest.TestCase):
    def test_reference_material_lookup_returns_constants_and_csv_path(self):
        material_reference = load_material_reference_module()

        ref = material_reference.get_reference_material(" AA2024-T351 ")

        self.assertEqual(ref["name"], "AA2024-T351")
        self.assertEqual(ref["E_MPa"], 73100)
        self.assertEqual(ref["H_prime_MPa"], 662)
        self.assertEqual(ref["n_prime"], 0.070)
        self.assertEqual(ref["stress_max_MPa"], 449)
        self.assertTrue(ref["reference_csv"].endswith(
            "00_Main_Scripts/material_reference_curves/aa2024-T351_monotonic_ROM_1pct_strain.csv"
        ))

    def test_resolve_abaqus_reference_material_sets_auto_e_and_metadata(self):
        material_reference = load_material_reference_module()
        abaqus = {
            "reference_material": "AA7075-T651",
            "E": "auto",
            "nu": 0.33,
            "plastic_stresses": [350, 470, 710, 710],
        }

        resolved = material_reference.resolve_abaqus_reference_material(abaqus)

        self.assertEqual(resolved["E"], 70000)
        self.assertEqual(resolved["reference_material"], "AA7075-T651")
        self.assertEqual(
            resolved["reference_material_properties"]["plot_label"],
            "AA7075-T651 cyclic ROM",
        )

    def test_resolve_abaqus_reference_material_rejects_conflicting_explicit_e(self):
        material_reference = load_material_reference_module()
        abaqus = {
            "reference_material": "AA2024-T351",
            "E": 71000,
            "nu": 0.33,
            "plastic_stresses": [350, 407, 449, 506],
        }

        with self.assertRaises(ValueError) as cm:
            material_reference.resolve_abaqus_reference_material(abaqus)

        message = str(cm.exception)
        self.assertIn("AA2024-T351 expects E = 73100 MPa", message)
        self.assertIn("input file gives E = 71000 MPa", message)

    def test_expand_all_includes_resolves_reference_material_and_auto_e_in_output_xml(self):
        # Load after injecting SCRIPT_DIR so abaqus_input_generation_v02 can import sibling modules.
        import sys
        sys.path.insert(0, str(SCRIPT_DIR))
        try:
            spec = importlib.util.spec_from_file_location(
                "abaqus_input_generation_v02", SCRIPT_DIR / "abaqus_input_generation_v02.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(SCRIPT_DIR))

        with tempfile.TemporaryDirectory() as tmpdir:
            xml_path = Path(tmpdir) / "case.xml"
            xml_path.write_text(
                """<input>
    <abaqus>
        <reference_material> AA2024-T351 </reference_material>
        <E> auto </E>
        <nu> 0.33 </nu>
        <displacement_yy> 0.01 </displacement_yy>
        <plastic_stresses> 350, 407, 449, 506 </plastic_stresses>
    </abaqus>
</input>
"""
            )

            resolved_path = module.expand_all_includes(xml_path)
            root = ET.parse(resolved_path).getroot()
            abaqus = root.find("abaqus")

            self.assertEqual(abaqus.findtext("reference_material").strip(), "AA2024-T351")
            self.assertEqual(abaqus.findtext("E").strip(), "73100")
            self.assertTrue(abaqus.findtext("reference_curve_csv").strip().endswith(
                "00_Main_Scripts/material_reference_curves/aa2024-T351_monotonic_ROM_1pct_strain.csv"
            ))
            self.assertEqual(
                abaqus.findtext("reference_plot_label").strip(),
                "AA2024-T351 cyclic ROM",
            )


if __name__ == "__main__":
    unittest.main()
