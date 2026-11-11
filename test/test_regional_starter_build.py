import subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
class RegionalStarterBuildGate(unittest.TestCase):
 def test_prerequisites(self):
  for args in ([], ['--experimental-regional-badges'], ['--experimental-regional-badges','--kanto-content'], ['--experimental-regional-badges','--kanto-content','--regional-state']):
   result=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),'--experimental-regional-starters',*args],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0);self.assertIn('requires',result.stderr)
 def test_default_off_and_forwarded(self):
  self.assertIn('EW_REGIONAL_STARTERS ?= 0',(ROOT/'engines/expansion.mk').read_text())
  self.assertIn('EW_REGIONAL_STARTERS={int(args.experimental_regional_starters)}',(ROOT/'scripts/build_expansion.py').read_text())
