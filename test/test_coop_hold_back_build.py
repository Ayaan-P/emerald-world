import pathlib,subprocess,sys,unittest
R=pathlib.Path(__file__).resolve().parents[1]
class HoldBackBuild(unittest.TestCase):
 def test_explicit_development_gate(self):
  p=subprocess.run([sys.executable,str(R/'scripts/build_expansion.py'),'--experimental-coop-hold-back'],capture_output=True,text=True)
  self.assertEqual(p.returncode,2)
  self.assertIn('--experimental-coop-hold-back requires --development',p.stderr)
 def test_default_off_and_pin(self):
  s=(R/'engines/expansion.mk').read_text()
  self.assertIn('EW_COOP_HOLD_BACK ?= 0',s)
  self.assertIn('-DEW_COOP_HOLD_BACK=$(EW_COOP_HOLD_BACK)',s)
  s=(R/'scripts/build_expansion.py').read_text()
  gitlink=subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD:engines/expansion-native'],text=True).strip()
  self.assertIn("PIN = '"+gitlink+"'",s)
  self.assertIn("f'EW_COOP_HOLD_BACK={int(args.experimental_coop_hold_back)}'",s)
if __name__=='__main__':unittest.main()
