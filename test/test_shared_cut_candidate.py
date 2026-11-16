import ast,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Candidate(unittest.TestCase):
 def test_explicit_development_only(self):
  r=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),'--experimental-shared-cut'],capture_output=True,text=True)
  self.assertNotEqual(r.returncode,0);self.assertIn('requires --development and matching native peers',r.stderr)
 def test_same_default_off_pointer_cohort(self):
  s=(ROOT/'scripts/build_expansion.py').read_text();m=(ROOT/'engines/expansion.mk').read_text()
  self.assertIn('EW_SHARED_CUT ?= 0',m)
  self.assertIn('-DEW_SHARED_CUT=$(EW_SHARED_CUT)',m[:m.index('include Makefile.native')])
  option=next(n for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Call) and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='--experimental-shared-cut')
  self.assertFalse(any(k.arg=='default' and getattr(k.value,'value',False) for k in option.keywords))
  self.assertIn("f'EW_SHARED_CUT={int(args.experimental_shared_cut)}'",s)
if __name__=='__main__':unittest.main()
