"""Transaction fixture only. Native UI/stock effect acceptance belongs to integrated RC."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class OwnedAutoHealTests(unittest.TestCase):
    def test_transaction_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = str(Path(tmp) / "owned-autoheal")
            subprocess.run([os.environ.get("CC", "cc"), "-std=gnu99", "-DPORTABLE",
                            "-DUBFIX", "-DMODERN=1", "-DNONMATCHING",
                            "-iquote", str(ROOT / "include"),
                            str(ROOT / "test/world/owned_autoheal_core.c"),
                            "-o", exe], check=True, cwd=ROOT)
            subprocess.run([exe], check=True)


if __name__ == "__main__":
    unittest.main()
