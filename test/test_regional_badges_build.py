import subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
class BadgeBuildGate(unittest.TestCase):
 def test_prerequisites(self):
  for args in (['--experimental-regional-badges'], ['--experimental-regional-badges','--kanto-content'], ['--experimental-regional-badges','--kanto-content','--regional-state']):
   r=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),*args],capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0);self.assertIn('requires',r.stderr)
 def test_default_off_and_forwarded(self):
  self.assertIn('EW_REGIONAL_BADGES ?= 0',(ROOT/'engines/expansion.mk').read_text())
  self.assertIn('EW_REGIONAL_BADGES={int(args.experimental_regional_badges)}',(ROOT/'scripts/build_expansion.py').read_text())
