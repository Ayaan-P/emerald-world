import subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
class BuildGate(unittest.TestCase):
 def test_explicit_prerequisites(self):
  for args in (['--experimental-combined-presence'],['--experimental-combined-presence','--kanto-content'],['--experimental-combined-presence','--kanto-content','--regional-state']):
   r=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),*args],capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0);self.assertIn('requires',r.stderr)
 def test_default_off_and_forwarded(self):
  mk=(ROOT/'engines/expansion.mk').read_text();builder=(ROOT/'scripts/build_expansion.py').read_text()
  self.assertIn('WORLD_COMBINED_PRESENCE ?= 0',mk);self.assertIn('WORLD_COMBINED_PRESENCE={int(args.experimental_combined_presence)}',builder)
