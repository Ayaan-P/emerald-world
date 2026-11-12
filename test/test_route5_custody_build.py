import subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
class CustodyBuildGate(unittest.TestCase):
 def test_prerequisites(self):
  for args in ([], ['--experimental-regional-badges'], ['--experimental-regional-badges','--kanto-content'], ['--experimental-regional-badges','--kanto-content','--regional-state']):
   result=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),'--experimental-route5-custody',*args],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0);self.assertIn('requires',result.stderr)
 def test_default_off_and_forwarded(self):
  self.assertIn('EW_ROUTE5_CUSTODY ?= 0',(ROOT/'engines/expansion.mk').read_text())
  self.assertIn('EW_ROUTE5_CUSTODY={int(args.experimental_route5_custody)}',(ROOT/'scripts/build_expansion.py').read_text())
