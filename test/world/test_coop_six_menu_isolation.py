"""Compile the battle callback and verify private-view controller isolation."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class SixMenuIsolation(unittest.TestCase):
 def test_other_controllers_pause_during_and_immediately_after_menu_open(self):
  src=(ROOT/'src/battle_main.c').read_text();start=src.index('static void BattleMainCB1(void)\n{');brace=src.index('{',start);depth=1;i=brace+1
  while depth:
   depth+=(src[i]=='{')-(src[i]=='}');i+=1
  code=r'''
#include <assert.h>
typedef unsigned char u8;
u8 gActiveBattler,gBattlersCount=4;int view,engineCalls,controllerCalls[4];
int WorldCoop_FullPartyMenuActive(void){return view;}
void engine(void){engineCalls++;}void (*gBattleMainFunc)(void)=engine;
void first(void){controllerCalls[0]++;view=1;}void second(void){controllerCalls[1]++;}
void third(void){controllerCalls[2]++;}void fourth(void){controllerCalls[3]++;}
void (*gBattlerControllerFuncs[4])(void)={first,second,third,fourth};
''' + src[start:i] + r'''
int main(void){
 view=1;BattleMainCB1();assert(!engineCalls && !controllerCalls[0]);
 view=0;BattleMainCB1();assert(engineCalls==1 && controllerCalls[0]==1);
 assert(!controllerCalls[1] && !controllerCalls[2] && !controllerCalls[3]);
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-DPORTABLE','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
