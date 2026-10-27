"""Regression: Windows cp1252 stdout must safely tee Unicode child output."""
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / '01_Secondary_Scripts/automated_run_helpers/run_normal_equal_mean.py'
spec = importlib.util.spec_from_file_location('normal_equal_mean', PATH)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ConsoleRegression(unittest.TestCase):
    def test_cp1252_tee_reconfigured_before_unicode_output(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding='cp1252', errors='strict')
        with patch.object(runner.sys, 'stdout', stream), patch.object(runner.sys, 'stderr', stream):
            runner.configure_console()
            print('\u2705 Post-processing completed.', flush=True)
        self.assertEqual(buffer.getvalue().decode('utf-8').splitlines(), ['\u2705 Post-processing completed.'])


if __name__ == '__main__':
    unittest.main()
