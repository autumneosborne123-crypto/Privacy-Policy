import unittest
from pathlib import Path


class TestLauncherConfiguration(unittest.TestCase):
    def test_restart_loop_has_a_real_start_label(self):
        lines = Path("run.bat").read_text(encoding="utf-8").splitlines()
        self.assertIn(":start", [line.strip().lower() for line in lines])


if __name__ == "__main__":
    unittest.main()