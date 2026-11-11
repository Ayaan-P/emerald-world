"""Build option contract only; no native binary or actual save is used."""
import ast,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Candidate(unittest.TestCase):
 def test_recovery_requires_explicit_complete_development_cohort(self):
  for flags in ([],['--development'],['--development','--regional-state']):
   r=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),'--experimental-rusturf-recovery',*flags],capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0)
   self.assertIn('requires --development --regional-state --kanto-content',r.stderr)
 def test_default_off_and_same_abi_reference_flags(self):
  make=(ROOT/'engines/expansion.mk').read_text();source=(ROOT/'scripts/build_expansion.py').read_text()
  for flag in ('EW_RUSTURF_RECOVERY','EW_REGIONAL_BADGES','EW_REGIONAL_COMPLETION','EW_ROUTE5_CUSTODY','EW_KANTO_REMATCHES','EW_REGIONAL_STARTERS'):
   self.assertIn(flag+' ?= 0',make)
   self.assertIn('-D'+flag+'=$('+flag+')',make[:make.index('include Makefile.native')])
   self.assertIn(flag,source)
  tree=ast.parse(source)
  self.assertIn("PIN = '0aacf14f9dae6cb7d572b5a90d85cc780b80ddd8'",source)
  option=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='--experimental-rusturf-recovery')
  self.assertFalse(any(k.arg=='default' and isinstance(k.value,ast.Constant) and k.value.value for k in option.keywords))
  self.assertIn("'rusturf-draft'",source)
if __name__=='__main__':unittest.main()
