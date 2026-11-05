"""Run the actual guarded turn-loop body with asynchronous ability stubs."""
from pathlib import Path
import subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[2]

class MegaTurnSequence(unittest.TestCase):
 def test_ability_scripts_pause_and_resume_without_repeating_transform(self):
  source = (ROOT / 'src/battle_main.c').read_text()
  start = source.index('        /* Ability scripts run asynchronously')
  end = source.index('        sMegaTurnHandled = TRUE;', start) + len('        sMegaTurnHandled = TRUE;')
  body = source[start:end]
  program = r'''
#include <assert.h>
#include <stdbool.h>
typedef unsigned char u8; typedef bool bool8;
#define FALSE false
#define TRUE true
#define B_ACTION_USE_MOVE 1
#define ABILITYEFFECT_ON_SWITCHIN 10
#define ABILITYEFFECT_INTIMIDATE1 11
#define ABILITYEFFECT_TRACE 12
struct Mon {u8 ability;} gBattleMons[4];
struct Protect {int noValidMoves;} protect[4], *gProtectStructs=protect;
u8 gBattlersCount=3, gBattlerByTurnOrder[4]={0,1,2},gChosenActionByBattler[4]={1,1,0};
u8 sMegaTurnIndex=0,sMegaAbilityPhase=0;bool8 sMegaTurnHandled=false;
int applyCalls[4],cancelCalls[4],onCalls[4],intimidateCalls,traceCalls;
int MegaGame_Apply(u8 b) { applyCalls[b]++; if (b==0) {gBattleMons[b].ability=7;return 1;} return 1; }
void MegaGame_CancelQueue(u8 b) { cancelCalls[b]++; }
int AbilityBattleEffects(int type,u8 b,int a,int c,int d) {
 (void)a;(void)c;(void)d;
 if(type==ABILITYEFFECT_ON_SWITCHIN) {onCalls[b]++;return onCalls[b]==1;}
 if(type==ABILITYEFFECT_INTIMIDATE1) return ++intimidateCalls==1;
 if(type==ABILITYEFFECT_TRACE) return ++traceCalls==1;
 assert(0);return 0;
}
void run(void) {
''' + body + r'''
}
int main(void) {
 gBattleMons[0].ability=1; gBattleMons[1].ability=2;
 run(); assert(!sMegaTurnHandled && applyCalls[0]==1 && onCalls[0]==1);
 run(); assert(!sMegaTurnHandled && applyCalls[0]==1 && intimidateCalls==1);
 run(); assert(!sMegaTurnHandled && traceCalls==1 && applyCalls[1]==0);
 run(); assert(sMegaTurnHandled && applyCalls[0]==1 && applyCalls[1]==1 && cancelCalls[2]==1);
 assert(onCalls[0]==1 && onCalls[1]==0 && intimidateCalls==2 && traceCalls==2);
 return 0;
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'test.c').write_text(program)
   c=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(c.returncode,0,c.stderr)
   c=subprocess.run([str(p/'test')],capture_output=True,text=True)
   self.assertEqual(c.returncode,0,c.stderr)
if __name__=='__main__':unittest.main()
