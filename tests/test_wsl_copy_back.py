import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "00_Main_Scripts"


def load_wsl_windows_compat():
    spec = importlib.util.spec_from_file_location("wsl_windows_compat", SCRIPTS_DIR / "wsl_windows_compat.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WslCopyBackTests(unittest.TestCase):
    def test_copy_tree_contents_recursively_overwrites_existing_large_result_file(self):
        compat = load_wsl_windows_compat()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "stage_case"
            dst = root / "source_case"
            (src / "abaqus_files").mkdir(parents=True)
            (dst / "abaqus_files").mkdir(parents=True)

            old_file = dst / "abaqus_files" / "case.odb"
            new_file = src / "abaqus_files" / "case.odb"
            old_file.write_bytes(b"old")
            new_file.write_bytes((b"new-result" * 1024) + b"done")
            (src / "abaqus_files" / "case.sta").write_text("completed")

            compat._copy_tree_contents(src, dst)

            self.assertEqual(old_file.read_bytes(), new_file.read_bytes())
            self.assertEqual((dst / "abaqus_files" / "case.sta").read_text(), "completed")

    def test_windows_batch_abaqus_launcher_runs_through_cmd(self):
        compat = load_wsl_windows_compat()

        def fake_which(name):
            if name == "abaqus":
                return r"C:\SIMULIA\Commands\abaqus.bat"
            if name == "cmd.exe":
                return r"C:\Windows\System32\cmd.exe"
            return None

        with mock.patch.object(compat.platform, "system", return_value="Windows"), \
             mock.patch.object(compat.shutil, "which", side_effect=fake_which):
            command = compat.find_abaqus_command()

        self.assertEqual(
            command,
            [r"C:\Windows\System32\cmd.exe", "/C", r"C:\SIMULIA\Commands\abaqus.bat"],
        )


if __name__ == "__main__":
    unittest.main()
