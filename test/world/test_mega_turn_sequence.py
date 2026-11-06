"""Dot's asynchronous sequencing checks adapted to RC4's pre-order phase."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]

class MegaTurnSequence(unittest.TestCase):
 def test_form_ack_and_async_abilities_drain_once_before_next_battler(self):
  source=(ROOT/'src/battle_main.c').read_text()
  start=source.index('static bool8 TryMegaEvolutionBeforeTurn(void)\n{')
  end=source.index('\n}\n',start)+3
  program=r'''
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8;typedef uint8_t bool8;
#define TRUE 1
#define FALSE 0
#define MEGA_FEATURE_READY 1
#define MEGA_WIRE_ACTIVATE 1
#define MAX_BATTLERS_COUNT 4
#define B_ACTION_USE_MOVE 0
#define B_WIN_MSG 0
#define ABILITYEFFECT_ON_SWITCHIN 10
#define ABILITYEFFECT_INTIMIDATE1 11
#define ABILITYEFFECT_TRACE 12
#define STATUS3_INTIMIDATE_POKES 1
#define STATUS3_TRACE 2
#define _(s) s
u8 sMegaTurnBattler,sMegaTurnPhase,sMegaTurnDelay,gActiveBattler;
bool8 sMegaTurnAbilityChanged;
u8 gBattlersCount=3,gChosenActionByBattler[4]={0,0,1,0};
struct {u8 ability;} gBattleMons[4];
struct {bool8 noValidMoves;} gProtectStructs[4];
struct {bool8 intimidatedMon,traced;} gSpecialStatuses[4];
unsigned gStatuses3[4],gBattleControllerExecFlags,gBattleOutcome;
int applyCalls[4],cancelCalls[4],onCalls[4],intimidateCalls,traceCalls,publishCalls,drawn;
struct {u8 battler;} gBattleScripting;
const u8 BattleScript_MegaEvolved[1]={0};int messageCalls;
void BattleScriptPushCursorAndCallback(const u8 *p){assert(p==BattleScript_MegaEvolved);messageCalls++;}
bool8 MegaGame_Apply(u8 b){applyCalls[b]++;if(b==0)gBattleMons[b].ability=7;return TRUE;}
void MegaGame_CancelQueue(u8 b){cancelCalls[b]++;}
void MegaGame_RefreshSprite(u8 b){(void)b;drawn++;}
void BattlePutTextOnWindow(const u8 *s,int w){(void)s;(void)w;}
bool8 MegaGame_PublishForm(u8 b,u8 kind){(void)b;(void)kind;publishCalls++;gBattleControllerExecFlags=1;return TRUE;}
int AbilityBattleEffects(int type,u8 b,int a,int c,int d){
 (void)a;(void)c;(void)d;
 if(type==ABILITYEFFECT_ON_SWITCHIN){onCalls[b]++;return 1;}
 if(type==ABILITYEFFECT_INTIMIDATE1)return ++intimidateCalls==1;
 if(type==ABILITYEFFECT_TRACE)return ++traceCalls==1;
 assert(0);return 0;
}
''' + source[start:end] + r'''
void run(void){sMegaTurnDelay=0;TryMegaEvolutionBeforeTurn();}
int main(void){
 gBattleMons[0].ability=1;gBattleMons[1].ability=2;
 run();assert(applyCalls[0]==1 && publishCalls==1 && !onCalls[0]);
 run();assert(applyCalls[0]==1 && !onCalls[0]);
 gBattleControllerExecFlags=0;run();assert(messageCalls==1 && !onCalls[0]);
 run();assert(onCalls[0]==1);
 run();assert(onCalls[0]==1 && intimidateCalls==1);
 run();assert(traceCalls==1 && !applyCalls[1]);
 run();assert(applyCalls[1]==1 && publishCalls==2);
 gBattleControllerExecFlags=0;run();assert(messageCalls==2 && sMegaTurnBattler==1);
 run();
 assert(sMegaTurnBattler==3 && onCalls[1]==0 && cancelCalls[2]==1);
 assert(applyCalls[0]==1 && applyCalls[1]==1 && applyCalls[2]==0);
 assert(intimidateCalls==2 && traceCalls==2 && drawn==2);
 return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(program)
   result=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run([str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
