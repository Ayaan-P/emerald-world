import pathlib,subprocess,sys,unittest
R=pathlib.Path(__file__).resolve().parents[1]
class TurnPlanBuild(unittest.TestCase):
 def test_requires_development(self):
  p=subprocess.run([sys.executable,str(R/'scripts/build_expansion.py'),'--experimental-coop-turn-plan'],capture_output=True,text=True)
  self.assertEqual(p.returncode,2)
  self.assertIn('--experimental-coop-turn-plan requires --development',p.stderr)
 def test_flag(self):
  s=(R/'engines/expansion.mk').read_text()
  self.assertIn('EW_COOP_TURN_PLAN ?= 0',s)
  self.assertIn('-DEW_COOP_TURN_PLAN=$(EW_COOP_TURN_PLAN)',s)
  self.assertIn("f'EW_COOP_TURN_PLAN={int(args.experimental_coop_turn_plan)}'",(R/'scripts/build_expansion.py').read_text())
if __name__=='__main__':unittest.main()
