import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GET_FORCE_DISP = PROJECT_ROOT / "00_Main_Scripts" / "getForceDisp.py"


class GetForceDispNoZipTests(unittest.TestCase):
    def test_get_force_disp_does_not_zip_reaction_force_and_displacement_values(self):
        source = GET_FORCE_DISP.read_text()

        self.assertNotIn("zip(rf.values, u.values)", source)
        self.assertNotIn("for rf_val, u_val in zip", source)

    def test_get_force_disp_reports_boundary_node_counts_for_auditability(self):
        source = GET_FORCE_DISP.read_text()

        self.assertIn("Bottom RF Node Count", source)
        self.assertIn("Upper U Node Count", source)


if __name__ == "__main__":
    unittest.main()
