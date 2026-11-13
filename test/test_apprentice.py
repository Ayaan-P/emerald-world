import pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/battle_setup.c').exists() else ROOT/'engines/expansion-native'
def function(s,sig):
 p=s.index(sig+'\n{');start=s.index('{',p);depth=0
 for i in range(start,len(s)):
  depth+=(s[i]=='{')-(s[i]=='}')
  if not depth:return s[p:i+1]
class Outings(unittest.TestCase):
 def test_actual_native_session_and_entry_exit_enabled_disabled(self):
  source=(NATIVE/'src/world/world_apprentice.c').read_text();setup=(NATIVE/'src/battle_setup.c').read_text()
  funcs='\n'.join(function(setup,x) for x in ['static void DoStandardWildBattle(bool32 isDouble)','static void CB2_EndWildBattle(void)'])
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp)
   import re
   for header in re.findall(r'#include "([^"]+)"',source):
    p=d/header;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
   text=(ROOT/'test/native_apprentice.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_apprentice.c')).replace('ACTUAL_ENTRY_EXIT',funcs).replace('ACTUAL_IDENTITY', function((NATIVE/'src/difficulty.c').read_text(),'enum DifficultyLevel GetBattlePartnerDifficultyLevel(u16 partnerId)')+'\n'+function((NATIVE/'src/battle_ai_main.c').read_text(),'static u64 GetAiFlags(u16 trainerId, enum BattlerId battler)'))
   (d/'test.c').write_text(text)
   for enabled in (0,1):
    subprocess.run(['cc','-std=c99','-DPORTABLE',f'-DEW_APPRENTICE_OUTINGS={enabled}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True)
    subprocess.run([str(d/'test')],check=True)
 def test_native_routing_and_lifecycle_hooks(self):
  root=NATIVE/'src';s=(root/'battle_ai_main.c').read_text();self.assertIn('WorldApprentice_Active() && battler == B_BATTLER_2',s)
  self.assertIn('if (WorldApprentice_Active()) return DIFFICULTY_NORMAL;', (root/'difficulty.c').read_text())
  self.assertIn('WorldApprentice_BlockItemTransfer(fromBattler, battler)',function((root/'battle_util.c').read_text(),'bool32 CanBattlerGetOrLoseItem(enum BattlerId fromBattler, enum BattlerId battler, enum Item itemId)'))
  core=(root/'world/world_core_story.c').read_text();self.assertIn('WorldApprentice_Reset(FALSE)',function(core,'void WorldCoreStory_Disconnected(void)'));self.assertIn('WorldApprentice_Reset(TRUE)',function(core,'void WorldCoreStory_NewGame(void)'))
  chat=(root/'world/world_chat.c').read_text();self.assertIn('WorldApprentice_Command(text, sChat.hint',chat)
 def test_no_player_party_rollback_or_saved_template_mutation(self):
  s=(NATIVE/'src/world/world_apprentice.c').read_text();self.assertNotIn('gParties[B_TRAINER_PLAYER]',s);self.assertNotIn('FlagSet(',s);self.assertNotIn('TrySavingData(',s);self.assertNotIn('SetFollowerNPCData(',s);self.assertIn('CreateApprenticeMon(&sOuting.party[i]',s)
if __name__=='__main__':unittest.main()
