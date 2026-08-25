import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "00_Main_Scripts" / "abaqus_input_generation_v02.py"


def load_module():
    sys.path.insert(0, str(PROJECT_ROOT / "00_Main_Scripts"))
    spec = importlib.util.spec_from_file_location("abaqus_input_generation_v02", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AbaqusElsetWrappingTests(unittest.TestCase):
    def test_wraps_long_seed_elset_lines_without_losing_set_names(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / "case.inp"
            seed_names = [f"Set-E-Seed-{i}" for i in range(9993, 10024)]
            long_line = ",".join(seed_names)
            inp.write_text(
                "*Heading\n"
                "*Elset, elset=Set-E-Material-3\n"
                f"{long_line}\n"
                "*Surface, name=Surface-0, type=element\n"
                "1, S1\n"
            )

            module.wrap_abaqus_elset_include_lines(str(inp), max_line_length=120)

            lines = inp.read_text().splitlines()
            elset_data = []
            in_target_elset = False
            for line in lines:
                if line.startswith("*Elset, elset=Set-E-Material-3"):
                    in_target_elset = True
                    continue
                if in_target_elset and line.startswith("*"):
                    break
                if in_target_elset:
                    elset_data.extend([part.strip() for part in line.split(",") if part.strip()])
                    self.assertLessEqual(len(line), 120)

            self.assertEqual(elset_data, seed_names)

    def test_does_not_wrap_surface_element_facet_lines(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / "case.inp"
            inp.write_text(
                "*Surface, name=Surface-0, type=element\n"
                "1601, S2\n"
                "5473, S1\n"
            )

            module.wrap_abaqus_elset_include_lines(str(inp), max_line_length=20)

            self.assertEqual(inp.read_text().splitlines(), [
                "*Surface, name=Surface-0, type=element",
                "1601, S2",
                "5473, S1",
            ])


if __name__ == "__main__":
    unittest.main()
