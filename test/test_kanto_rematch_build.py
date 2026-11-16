import subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
class KantoRematchBuildGate(unittest.TestCase):
 def test_prerequisites(self):
  for args in ([], ['--experimental-regional-badges'], ['--experimental-regional-badges','--kanto-content'], ['--experimental-regional-badges','--kanto-content','--regional-state']):
   result=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),'--experimental-kanto-rematches',*args],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0);self.assertIn('requires',result.stderr)
 def test_default_off_and_forwarded(self):
  self.assertIn('EW_KANTO_REMATCHES ?= 0',(ROOT/'engines/expansion.mk').read_text())
  self.assertIn('EW_KANTO_REMATCHES={int(args.experimental_kanto_rematches)}',(ROOT/'scripts/build_expansion.py').read_text())
