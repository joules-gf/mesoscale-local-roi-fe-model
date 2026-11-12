"""Solver-free checks of the two material baselines using real input completion.

Run with the project's Windows interpreter. BASELINE_TEST_SCRATCH may select an
isolated temporary parent; no mesh generation or solver entry point is invoked.
"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "00_Main_Scripts"))
import abaqus_input_generation_v02 as generation

MATERIALS = (
    ("AA2024-T351", "aa2024_t351", [0.13, 0.10, 0.30, 0.47], [325, 400, 525, 650], 73100),
    ("AA7075-T651", "aa7075_t651", [0.10, 0.10, 0.40, 0.40], [410, 470, 680, 710], 70000),
)


class MaterialBaselineTests(unittest.TestCase):
    def test_xml_structure_and_local_includes(self):
        stems = set()
        for material, stem, fractions, yields, modulus in MATERIALS:
            folder = REPO / "simulation_inputs" / material
            xmls = sorted(folder.glob("*.xml"))
            self.assertEqual(len(xmls), 4)
            for path in xmls:
                self.assertNotIn(path.stem, stems)
                stems.add(path.stem)
                root = ET.parse(path).getroot()
                self.assertEqual(root.tag, "input")
                self.assertEqual(root.findall(".//scale"), [])
                for include in root.findall("include"):
                    target = (folder / include.text.strip()).resolve()
                    self.assertEqual(target.parent, folder.resolve())
                    self.assertTrue(target.is_file())
            mesh = ET.parse(folder / f"{stem}_baseline_mesh.xml").getroot()
            self.assertEqual([float(p.findtext("fraction")) for p in mesh.findall("material")], fractions)
            self.assertAlmostEqual(sum(fractions), 1.0)

    def test_real_complete_input_data_without_mesh_or_solver(self):
        os.environ["MICROSTRUCTURE_NONINTERACTIVE"] = "1"
        os.environ["MPLBACKEND"] = "Agg"
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        msp = generation.get_microstructpy()
        records = []
        with tempfile.TemporaryDirectory(prefix="material-baseline-check-", dir=os.environ.get("BASELINE_TEST_SCRATCH")) as temporary:
            sandbox = Path(temporary)
            (sandbox / "00_Main_Scripts").mkdir()
            original_cwd = Path.cwd()
            try:
                os.chdir(sandbox)
                with mock.patch.object(generation, "__file__", str(sandbox / "00_Main_Scripts" / "abaqus_input_generation_v02.py")), mock.patch.object(tempfile, "tempdir", str(sandbox)), mock.patch.object(msp.cli, "run", side_effect=AssertionError("Mesh generation forbidden")), mock.patch.object(plt, "show", side_effect=AssertionError("GUI forbidden")), mock.patch.object(generation, "ask_continue_or_quit", side_effect=AssertionError("GUI confirmation forbidden")):
                    for material, stem, fractions, yields, modulus in MATERIALS:
                        for loading in ("monotonic", "cyclic_Rminus1"):
                            with self.subTest(material=material, loading=loading):
                                path = REPO / "simulation_inputs" / material / f"{stem}_normal_{loading}.xml"
                                repo_output = REPO / "simulation_outputs" / path.stem
                                existed_before = repo_output.exists()
                                with contextlib.redirect_stdout(io.StringIO()):
                                    complete, name, output, mesh_dir, expected_plot, expanded = generation.complete_input_data(str(path))
                                domain, phases, settings, abaqus = complete
                                self.assertEqual(name, path.stem)
                                self.assertEqual(Path(output), sandbox / "simulation_outputs")
                                self.assertEqual(Path(mesh_dir), sandbox / "simulation_outputs" / name / "msp_mesh_files")
                                self.assertFalse(Path(mesh_dir).exists())
                                self.assertEqual(repo_output.exists(), existed_before)
                                self.assertAlmostEqual(float(domain.area), 1.0)
                                self.assertEqual([p["fraction"] for p in phases], fractions)
                                for phase in phases:
                                    dist = phase["size"]
                                    self.assertEqual(dist.dist.name, "norm")
                                    self.assertAlmostEqual(float(dist.mean()), 0.050)
                                    self.assertAlmostEqual(float(dist.std()), 0.010)
                                self.assertEqual(abaqus["E"], modulus)
                                self.assertEqual(abaqus["reference_material"], material)
                                self.assertEqual(list(abaqus["plastic_stresses"]), yields)
                                self.assertEqual(abaqus["nu"], 0.33)
                                self.assertEqual(abaqus["displacement_yy"], 0.01)
                                self.assertTrue(Path(abaqus["reference_curve_csv"]).is_file())
                                self.assertIs(settings["restart"], False)
                                self.assertIs(settings["verbose"], True)
                                self.assertEqual(settings["mesh_min_angle"], 25)
                                self.assertEqual(settings["mesh_max_edge_length"], 0.00328)
                                self.assertEqual(settings["rng_seeds"], {"size": 1000})
                                self.assertEqual(settings["filetypes"]["tri"], "abaqus")
                                if loading == "monotonic":
                                    self.assertNotIn("cyclic_parameters", abaqus)
                                    self.assertNotIn("num_increments_step", abaqus)
                                    self.assertIsNone(expected_plot)
                                else:
                                    self.assertEqual(abaqus["cyclic_parameters"], {"rRatio_strain": -1, "frequency_hz": 5, "start_min": False, "time_increment_s": 0.01, "plot_before": False})
                                    self.assertEqual(abaqus["num_increments_step"], 250)
                                    # Current implementation tests presence, not truth, of plot_before.
                                    self.assertTrue((sandbox / f"expected_cycles_{name}.png").is_file())
                                records.append({"case": name, "E_MPa": abaqus["E"], "nu": abaqus["nu"], "plastic_stresses_MPa": list(abaqus["plastic_stresses"]), "fractions": [p["fraction"] for p in phases], "normal_mean": [float(p["size"].mean()) for p in phases], "normal_std": [float(p["size"].std()) for p in phases], "restart": settings["restart"], "verbose": settings["verbose"], "mesh_min_angle": settings["mesh_min_angle"], "mesh_max_edge_length": settings["mesh_max_edge_length"], "rng_seeds": settings["rng_seeds"], "displacement_yy": abaqus["displacement_yy"], "cyclic_parameters": abaqus.get("cyclic_parameters"), "num_increments_step": abaqus.get("num_increments_step"), "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
                                Path(expanded).unlink()
            finally:
                os.chdir(original_cwd)
                plt.close("all")
        self.assertEqual(len(records), 4)
        print("VERIFIED_REAL_COMPLETION " + json.dumps(records, sort_keys=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
