"""Use the real native dependency scanner to catch missing new-species art."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]

class ExpandedArtDependencies(unittest.TestCase):
    def test_native_scanner_schedules_expanded_front_art(self):
        with tempfile.TemporaryDirectory(prefix='rc4-art-deps-') as directory:
            dep = Path(directory)/'graphics.d'
            result = subprocess.run(['tools/scaninc/scaninc', '-M', str(dep), '-g', 'build/assets', '-I', 'include', '-I', 'gflib', '-I', 'tools/agbcc/include', 'src/graphics.c'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            dependencies = set(dep.read_text().split())
            for species in ('gimmighoul_roaming', 'meltan', 'cosmoem'):
                self.assertIn(f'build/assets/graphics/expanded/{species}/front.png.4bpp.lz', dependencies)
