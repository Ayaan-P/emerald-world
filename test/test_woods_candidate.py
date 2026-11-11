import ast,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Candidate(unittest.TestCase):
 def test_requires_existing_save_reader_cohort(self):
  r=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),'--experimental-woods-continuation'],capture_output=True,text=True)
  self.assertNotEqual(r.returncode,0);self.assertIn('requires --experimental-roxanne-continuation',r.stderr)
 def test_default_off_and_native_reference_match(self):
  s=(ROOT/'scripts/build_expansion.py').read_text();m=(ROOT/'engines/expansion.mk').read_text()
  self.assertIn('EW_WOODS_CONTINUATION ?= 0',m)
  self.assertIn('-DEW_WOODS_CONTINUATION=$(EW_WOODS_CONTINUATION)',m[:m.index('include Makefile.native')])
  option=next(n for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Call) and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='--experimental-woods-continuation')
  self.assertFalse(any(k.arg=='default' and getattr(k.value,'value',False) for k in option.keywords))
  self.assertIn("f'EW_WOODS_CONTINUATION={int(args.experimental_woods_continuation)}'",s)
if __name__=='__main__':unittest.main()
