"""Exercise the actual temporary private-six view without opening a game UI."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class PrivatePartyViewTests(unittest.TestCase):
 def test_view_is_private_and_restores_shared_party_for_both_owners(self):
  code=r'''
#define main CoreFixtureMain
#include "test/world/coop_engine_core.c"
#undef main
int main(void){
 for(u8 owner=0;owner<2;owner++){
  struct Pokemon shared[PARTY_SIZE],original[PARTY_SIZE];struct CoopRosterPlan p;
  Reset(owner,owner==0);Exchange();WorldCoop_InitControllers();
  assert(sCoop.state==COOP_BATTLE && sCoop.staged);
  assert(WorldCoop_HasHiddenUsable(owner*2));
  assert(!WorldCoop_HasHiddenUsable(1));
  struct CoopHeader old=sCoop.headers[owner];old.version=7;assert(!HeaderValid(&old,0));
  gPlayerParty[owner*3+1].hp=12;
  memcpy(shared,gPlayerParty,sizeof(shared));memcpy(original,sCoop.original,sizeof(original));
  assert(WorldCoop_BeginFullPartyMenu() && WorldCoop_FullPartyMenuActive());
  assert(gPlayerPartyCount==6 && gPlayerParty[3].hp==12);
  for(u8 i=0;i<PARTY_SIZE;i++){
   assert(gPlayerParty[i].box.personality==original[i].box.personality);
   assert(WorldCoop_GetOwnMon(i)==&gPlayerParty[i]);
  }
  assert(!WorldCoop_ChooseFullPartyMenu(1)); /* already active */
  assert(!WorldCoop_ChooseFullPartyMenu(0)); /* fainted */
  assert(!WorldCoop_ChooseFullPartyMenu(6));
  assert(WorldCoop_ChooseFullPartyMenu(4));
  assert(WorldCoop_FullPartyChoiceStage()==owner*3+2 && WorldCoop_FullPartyChoiceReply()==owner*3+2);
  assert(WorldCoop_ChooseFullPartyMenu(5));assert(WorldCoop_FullPartyChoice()==5);
  assert(WorldCoop_FullPartyChoiceStage()==owner*3+1);
  assert(WorldCoop_FullPartyChoiceReply()==(0x80 | ((owner*3+1)<<3) | 5));
  assert(!WorldCoop_PlanRosterRotation(5,&p)); /* never rotate while the view owns the array */
  WorldCoop_EndFullPartyMenu();assert(!WorldCoop_FullPartyMenuActive());
  assert(!memcmp(gPlayerParty,shared,sizeof(shared)) && WorldCoop_FullPartyChoice()==5);
  assert(WorldCoop_PlanRosterRotation(5,&p));
  WorldCoop_Abort();assert(!memcmp(gPlayerParty,original,sizeof(original)));
 }
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-DPORTABLE','-DCOOP_FULL_SIX_READY=1','-DUBFIX','-DVER_64BIT','-DNONMATCHING','-DMODERN=1','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
