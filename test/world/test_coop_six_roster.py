"""Compile the real battle-local mapping and participation tracker."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class SixRosterTests(unittest.TestCase):
 def test_rotation_preserves_private_identity_and_exp_participation(self):
  code=r'''
#include "global.h"
#include "platform/world_coop_roster.h"
#include <assert.h>
#include <string.h>
int main(void){
 struct CoopRoster a,b,before;struct CoopRosterPlan p,stale;
 u8 slots[3]={0,2,4},other[3]={1,3,5},participation[6]={3,0,0,0,0,0};
 assert(CoopRoster_Init(&a,0x3f,slots));assert(CoopRoster_Init(&b,0x3f,other));
 /* Pending participation is captured atomically with the rotation. */
 assert(CoopRoster_Plan(&a,5,0,&p));assert(p.stage==1 && p.outgoing==2 && p.incoming==5);
 stale=p;before=a;assert(!memcmp(&a,&before,sizeof(a)));assert(!CoopRoster_Commit(&a,&p,1,participation,2));assert(CoopRoster_Commit(&a,&p,0,participation,2));
 assert(a.staged[0]==0 && a.staged[1]==5 && a.staged[2]==4);
 assert(a.knockedOff & (1<<2));assert(!(a.knockedOff & (1<<5)));
 assert(!CoopRoster_Commit(&a,&stale,0,participation,2)); /* a stale plan cannot evict a new mon */
 assert(CoopRoster_Record(&a,0,2));assert(CoopRoster_RewardMask(&a,0,4)==((1<<0)|(1<<2)|(1<<5)|(1<<4)));
 assert(CoopRoster_RewardMask(&b,0,2)==(1<<3)); /* trainers do not share ledgers */
 assert(CoopRoster_Plan(&a,2,0,&p));assert(CoopRoster_Commit(&a,&p,0,participation,0));
 assert(a.knockedOff & (1<<2)); /* a previously knocked-off held item stays knocked off */
 assert(!CoopRoster_Plan(&a,0,0,&p)); /* never evict/switch into the active mon */
 assert(CoopRoster_Plan(&a,4,0,&p) && p.stage==2 && p.incoming==p.outgoing);
 assert(CoopRoster_Commit(&a,&p,0,participation,2));
 u8 bad[3]={0,0,4};before=a;assert(!CoopRoster_Init(&a,0x3f,bad));assert(!memcmp(&a,&before,sizeof(a)));
 u8 sparse[3]={0,COOP_ROSTER_EMPTY,4};assert(CoopRoster_Init(&a,0x3f,sparse));
 assert(CoopRoster_Plan(&a,5,0,&p) && p.stage==1 && p.outgoing==COOP_ROSTER_EMPTY);
 before=a;participation[3]=8;assert(!CoopRoster_Commit(&a,&p,0,participation,2));
 assert(!memcmp(&a,&before,sizeof(a)));participation[3]=0;
 assert(CoopRoster_Commit(&a,&p,0,participation,2));
 assert(!CoopRoster_Record(&a,6,1));assert(!CoopRoster_Record(&a,0,8));
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint8_t bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   cmd=['cc','-std=c99','-DPORTABLE','-Wall','-Wextra','-Werror','-I',str(p),'-I',str(ROOT/'include'),str(ROOT/'src/platform/world_coop_roster.c'),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
