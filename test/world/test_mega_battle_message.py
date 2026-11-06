"""Check the native-only battle announcement is registered without moving old IDs."""
from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[2]
class MegaMessageTest(unittest.TestCase):
 def test_script_and_string_registration(self):
  ids=(ROOT/'include/constants/battle_string_ids.h').read_text()
  msg=(ROOT/'src/battle_message.c').read_text()
  script=(ROOT/'data/battle_scripts_1.s').read_text()
  self.assertIn('#define STRINGID_TRAINER2WINTEXT            380',ids)
  self.assertIn('#define STRINGID_MEGA_EVOLVED               381',ids)
  self.assertIn('[STRINGID_MEGA_EVOLVED - BATTLESTRINGS_TABLE_START] = sText_MegaEvolved',msg)
  self.assertIn('{B_SCR_ACTIVE_NAME_WITH_PREFIX}\\nMega Evolved!',msg)
  self.assertIn('.ifdef PORTABLE\nBattleScript_MegaEvolved::\n\tprintstring STRINGID_MEGA_EVOLVED\n\twaitmessage B_WAIT_TIME_LONG\n\tend3\n.endif',script)
  # C-preprocessing should resolve the new ID before the assembler runs.
  p=subprocess.run(['cpp','-I',str(ROOT/'include'),'-I',str(ROOT),str(ROOT/'data/battle_scripts_1.s')],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr)
  self.assertIn('BattleScript_MegaEvolved::\n printstring 381',p.stdout)
if __name__=='__main__':unittest.main()
