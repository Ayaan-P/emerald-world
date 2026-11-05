"""Exercise actual staged-party rotation and private rollback with fixtures."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class OwnedRotationTests(unittest.TestCase):
 def test_both_owners_preserve_evicted_mon_and_participation(self):
  code=r'''
#define main CoreFixtureMain
#include "test/world/coop_engine_core.c"
#undef main
int main(void){
 for(u8 owner=0;owner<2;owner++){
  struct Pokemon before[PARTY_SIZE],merged[PARTY_SIZE];
  struct CoopRosterPlan plan;u8 participation[6]={2,0,0,0,0,0};
  Reset(owner,owner==0);Exchange();WorldCoop_InitControllers();
  assert(sCoop.state==COOP_BATTLE && sCoop.staged && sCoop.count==3);
  memcpy(before,sCoop.original,sizeof(before));
  assert(sCoop.slots[0]==1 && sCoop.slots[1]==3 && sCoop.slots[2]==4);
  gPlayerParty[owner*3+1].hp=12;
  assert(WorldCoop_PlanRosterRotation(5,&plan));
  assert(plan.stage==1 && plan.outgoing==3 && plan.incoming==5);
  assert(WorldCoop_CommitRosterRotation(&plan,participation,2));
  assert(sCoop.working[3].hp==12 && sCoop.slots[1]==5);
  assert(gPlayerParty[owner*3+1].box.personality==before[5].box.personality);
  gPlayerParty[owner*3+1].hp=15;
  assert(BuildPrivateParty(merged));assert(merged[3].hp==12 && merged[5].hp==15);
  assert(CoopRoster_RewardMask(&sCoop.roster,0,2)==((1<<3)|(1<<5)));
  assert(!WorldCoop_CommitRosterRotation(&plan,participation,2));
  WorldCoop_Abort();assert(!memcmp(gPlayerParty,before,sizeof(before)));
 }
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-DPORTABLE','-DUBFIX','-DVER_64BIT','-DNONMATCHING','-DMODERN=1','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
