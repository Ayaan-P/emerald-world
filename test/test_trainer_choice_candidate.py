import ast,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Candidate(unittest.TestCase):
 def test_explicit_development_only(self):
  r=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),'--experimental-trainer-choice'],capture_output=True,text=True)
  self.assertNotEqual(r.returncode,0);self.assertIn('requires --development and matching authority',r.stderr)
 def test_same_default_off_pointer_cohort(self):
  s=(ROOT/'scripts/build_expansion.py').read_text();m=(ROOT/'engines/expansion.mk').read_text()
  self.assertIn('EW_TRAINER_CHOICE ?= 0',m)
  self.assertIn('-DEW_TRAINER_CHOICE=$(EW_TRAINER_CHOICE)',m[:m.index('include Makefile.native')])
  option=next(n for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Call) and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='--experimental-trainer-choice')
  self.assertFalse(any(k.arg=='default' and getattr(k.value,'value',False) for k in option.keywords))
  self.assertIn("f'EW_TRAINER_CHOICE={int(args.experimental_trainer_choice)}'",s)
if __name__=='__main__':unittest.main()
