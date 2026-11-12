"""Analytic geometry, final-deck provenance and summary contract tests (no solver)."""
import csv
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "00_Main_Scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def square_deck():
    # Unequal triangle areas: 0.25 versus 0.75. Both touch the right-middle ROI.
    return """*Part, name=Domain
*Node
1,-.5,-.5,0
2,.5,-.5,0
3,.5,0,0
4,.5,.5,0
5,-.5,.5,0
*Element, type=CPS3
1,1,2,3
2,1,3,5
3,3,4,5
*Elset, elset=small, generate
1,1,1
*Elset, elset=large
2,3
*Solid Section, elset=small, material=Material-0
,
*Solid Section, elset=large, material=Material-1
,
*End Part
*Assembly, name=Assembly
*Instance, name=Domain-1, part=Domain
*End Instance
*End Assembly
*Material, name=Material-0
*Elastic
70000,.33
*Material, name=Material-1
*Elastic
70000,.33
"""


class AnalyticIntersectionTests(unittest.TestCase):
    def setUp(self):
        self.area = load("roi_area_fractions")
        self.export = load("abaqus_roi_report_export")

    def roi(self, center=(0., 0.), side="left", radius=1.):
        return self.export.ROIRegion("test", side, center, radius)

    def test_quarter_and_half_disk(self):
        quarter = [(0, 0), (3, 0), (0, 3)]
        half = [(0, -3), (3, 0), (0, 3)]
        self.assertAlmostEqual(self.area.triangle_semicircle_area(quarter, self.roi()), math.pi / 4, places=12)
        self.assertAlmostEqual(self.area.triangle_semicircle_area(half, self.roi()), math.pi / 2, places=12)

    def test_boundary_intersection_includes_centroid_outside(self):
        triangle = [(0, -3), (3, 0), (0, 3)]
        roi = self.roi(radius=.1)
        self.assertFalse(roi.contains_centroid((1, 0)))
        self.assertAlmostEqual(self.area.triangle_semicircle_area(triangle, roi), math.pi * .1**2 / 2, places=14)

    def test_reversed_vertices_and_translation(self):
        triangle = [(0, -3), (3, 0), (0, 3)]
        shifted = [(x + 8, y - 4) for x, y in reversed(triangle)]
        self.assertAlmostEqual(self.area.triangle_semicircle_area(shifted, self.roi((8, -4))), math.pi / 2, places=12)

    def test_tangent_and_outside_half_have_zero_area(self):
        for tri in ([(1, -2), (3, 0), (1, 2)], [(-3, 0), (0, -3), (0, 3)]):
            self.assertAlmostEqual(self.area.triangle_semicircle_area(tri, self.roi()), 0, places=12)

    def test_triangle_fully_inside_uses_unequal_actual_area(self):
        a = self.area.triangle_semicircle_area([(0, 0), (.2, 0), (0, .2)], self.roi())
        b = self.area.triangle_semicircle_area([(0, 0), (.4, 0), (0, .4)], self.roi())
        self.assertAlmostEqual(b / a, 4.)


class DeckAndCoverageTests(unittest.TestCase):
    def setUp(self):
        self.area = load("roi_area_fractions")

    def parse(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "final.inp"
            path.write_text(text)
            return self.area.read_input_deck(path)

    def test_generated_sets_and_all_elements_have_unique_phase(self):
        mesh = self.parse(square_deck())
        self.assertEqual(len(mesh.triangles), 3)
        self.assertEqual(mesh.phases, {1: "Phase 0", 2: "Phase 1", 3: "Phase 1"})
        rows = self.area.compute_area_fractions(mesh)
        self.assertEqual(len(rows), 18)
        for row in rows:
            self.assertAlmostEqual(sum(row[f"Phase {i}"] for i in range(4)), 100, places=9)
            self.assertAlmostEqual(row["represented_area"], math.pi * .1**2 / 2, places=12)
            self.assertAlmostEqual(row["coverage_error"], 0., places=12)
        right_middle = next(row for row in rows if row["roi_name"] == "roi_right_05")
        self.assertGreater(right_middle["Phase 0"], 0.)
        self.assertLess(right_middle["Phase 0"], 50.)
        expected_percent = 100 * (math.pi / 2 - math.atan(.5)) / math.pi
        self.assertAlmostEqual(right_middle["Phase 0"], expected_percent, places=10)

    def test_all_four_phases_nested_sets_and_reversed_winding(self):
        text = """*Node
1,-.5,-.5
2,.5,-.5
3,.5,.5
4,-.5,.5
5,0,0
"""
        for i, conn in enumerate(("5,2,1", "5,3,2", "5,4,3", "5,1,4")):
            text += f"*Element, type=CPS3, elset=base{i}\n{i+1},{conn}\n"
            text += f"*Elset, elset=phase{i}\nbase{i}\n*Solid Section, elset=phase{i}, material=Material-{i}\n,\n"
            text += f"*Material, name=Material-{i}\n*Elastic\n70000,.33\n"
        rows = self.area.compute_area_fractions(self.parse(text))
        for i in range(4):
            self.assertGreater(sum(row[f"Phase {i}"] for row in rows), 0.)
        self.assertAlmostEqual(next(row for row in rows if row["roi_name"] == "roi_right_05")["Phase 1"], 100., places=10)
        self.assertAlmostEqual(next(row for row in rows if row["roi_name"] == "roi_left_05")["Phase 3"], 100., places=10)

    def test_missing_unknown_and_overlapping_material_mappings_fail(self):
        cases = [
            square_deck().replace("*Solid Section, elset=small, material=Material-0\n,\n", ""),
            square_deck().replace("material=Material-0", "material=Unknown"),
            square_deck() + "*Solid Section, elset=large, material=Material-0\n,\n",
            square_deck().replace("2,3\n*Solid", "2,3,999\n*Solid"),
        ]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)

    def test_invalid_type_missing_node_degenerate_nonplanar_fail(self):
        for text in [square_deck().replace("CPS3", "CPE3"),
                     square_deck().replace("1,1,2,3", "1,1,2,99"),
                     square_deck().replace("1,1,2,3", "1,1,1,3"),
                     square_deck().replace("1,-.5,-.5,0", "1,-.5,-.5,.2")]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)

    def test_overlapping_geometry_fails_even_if_total_area_balances_hole(self):
        # Duplicate the lower triangle and remove upper triangle: area alone is insufficient.
        text = square_deck().replace("3,3,4,5", "3,1,2,3")
        with self.assertRaisesRegex(ValueError, "[Oo]verlap"):
            self.parse(text)

    def test_missing_mesh_coverage_is_not_normalized(self):
        text = square_deck().replace("3,3,4,5\n", "").replace("2,3\n*Solid", "2\n*Solid")
        with self.assertRaisesRegex(ValueError, "[Cc]overage"):
            self.area.compute_area_fractions(self.parse(text))

    def test_unsupported_include_multiple_instances_transform_fail(self):
        for text in [square_deck() + "*Include, input=other.inp\n",
                     square_deck().replace("*End Instance", "0,0,0\n*End Instance"),
                     square_deck().replace("*End Assembly", "*Instance, name=Other, part=Domain\n*End Instance\n*End Assembly")]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)

    def test_cli_csv_and_metadata_are_final_deck_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = Path(tmp) / "final.inp"
            output = Path(tmp) / "roi_area_fractions.csv"
            deck.write_text(square_deck())
            proc = subprocess.run([sys.executable, str(SCRIPTS / "roi_area_fractions.py"), "--input-deck", str(deck), "--output-csv", str(output)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with output.open() as stream:
                rows = list(csv.DictReader(stream))
            metadata = json.loads(output.with_suffix(".json").read_text())
            self.assertEqual(len(rows), 18)
            self.assertEqual(metadata["reference_configuration"], "undeformed")
            self.assertEqual(len(metadata["source_sha256"]), 64)
            self.assertEqual(metadata["element_count"], 3)
            self.assertIn("analytic", metadata["method"])
            # Exercise the actual area-producer -> summary-consumer contract.
            fractions = load("roi_postprocessing").load_area_fractions(output, required_roi_names=[row["roi_name"] for row in rows])
            self.assertEqual(len(fractions), 18)


class SummaryIntegrationTests(unittest.TestCase):
    def test_invalid_modulus_fails_in_report_folder_and_writer(self):
        post = load("roi_postprocessing")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            report = folder / "roi_right_01_frame50.csv"
            report.write_text("Frame,         S-S22,         E-E22\nStep Time = 0.5,100,.004\n")
            for modulus in (0., -70000., float("nan"), float("inf")):
                for action in (lambda: post.summarize_roi_report(report, youngs_modulus_mpa=modulus),
                               lambda: post.summarize_roi_folder(folder, youngs_modulus_mpa=modulus),
                               lambda: post.write_roi_summary_csv(folder, youngs_modulus_mpa=modulus)):
                    with self.subTest(modulus=modulus), self.assertRaises(ValueError):
                        action()

    def test_area_override_leaves_report_averaging_and_repeated_rows_unchanged(self):
        post = load("roi_postprocessing")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            report = folder / "roi_right_01_frame50.csv"
            report.write_text("Frame,Material Name,         S-S22,         E-E22\n" +
                              "Step Time = 0.5,MATERIAL-0,100,.004\n" * 2 +
                              "Step Time = 0.5,MATERIAL-1,300,.006\n")
            area_csv = folder / "areas.csv"
            area_csv.write_text("roi_name,Phase 0,Phase 1,Phase 2,Phase 3,represented_area,expected_area,coverage_error\nroi_right_01,20,80,0,0,.01,.01,0\n")
            old = post.summarize_roi_report(report, youngs_modulus_mpa=70000)
            new = post.summarize_roi_report(report, youngs_modulus_mpa=70000, area_fractions_csv=area_csv)
            self.assertEqual(new[:-1], old[:-1])
            self.assertEqual(new.phase_fractions, {"Phase 0": 20., "Phase 1": 80., "Phase 2": 0., "Phase 3": 0.})
            summary = post.summarize_roi_folder(folder, youngs_modulus_mpa=70000, area_fractions_csv=area_csv)
            self.assertAlmostEqual(summary.iloc[0]["average_plastic_strain"], new.average_plastic_strain)
            out = post.write_roi_summary_csv(folder, folder / "summary.csv", youngs_modulus_mpa=70000, area_fractions_csv=area_csv)
            self.assertTrue(out.is_file())
            proc = subprocess.run([sys.executable, str(SCRIPTS / "roi_postprocessing.py"), "--roi-reports", str(folder), "--area-fractions-csv", str(area_csv), "--youngs-modulus-mpa", "70000", "--plastic-strain-source", "legacy"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_invalid_or_missing_override_roi_fails_loudly(self):
        post = load("roi_postprocessing")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "areas.csv"
            for data in ["roi_name,Phase 0,Phase 1,Phase 2,Phase 3\nother,100,0,0,0\n",
                         "roi_name,Phase 0,Phase 1,Phase 2,Phase 3\na,100,0,0,0\na,100,0,0,0\n",
                         "roi_name,Phase 0,Phase 1,Phase 2,Phase 3\na,99,0,0,0\n",
                         "roi_name,Phase 0,Phase 1,Phase 2,Phase 3\na,nan,0,0,0\n"]:
                path.write_text(data)
                with self.subTest(data=data), self.assertRaises(ValueError):
                    post.load_area_fractions(path, required_roi_names=["a"])


if __name__ == "__main__":
    unittest.main()
