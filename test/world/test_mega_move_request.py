"""Compile the actual move-request emitter with a minimal controller stub."""
from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
class MoveRequestTest(unittest.TestCase):
 def test_master_announces_eligibility_without_changing_existing_fields(self):
  src=(ROOT/'src/battle_controllers.c').read_text()
  start=src.index('void BtlController_EmitChooseMove(')
  brace=src.index('{',start);depth=1;i=brace+1
  while depth:
   depth += (src[i]=='{')-(src[i]=='}');i+=1
  body=src[start:i]
  c=r'''
#include <stdint.h>
#include <assert.h>
typedef uint8_t u8;typedef int32_t s32;typedef uint8_t bool8;
#define CONTROLLER_CHOOSEMOVE 10
#define MEGA_MOVE_CAN_SELECT_BIT 1
struct ChooseMoveStruct {u8 bytes[20];};
u8 gActiveBattler, sBattleBuffersTransferData[64], captured[64];
int eligible,capturedSize;
int MegaGame_CanQueue(u8 b){(void)b;return eligible;}
void PrepareBufferDataTransfer(u8 id,u8 *p,int n){(void)id;capturedSize=n;for(int i=0;i<n;i++)captured[i]=p[i];}
''' + body + r'''
int main(void){struct ChooseMoveStruct m={{0}};m.bytes[3]=42;
 eligible=1;BtlController_EmitChooseMove(0,1,0,&m);
 assert(capturedSize==24 && captured[0]==10 && captured[1]==1 && captured[2]==0 && captured[3]==1 && captured[7]==42);
 eligible=0;BtlController_EmitChooseMove(0,0,1,&m);
 assert(captured[1]==0 && captured[2]==1 && captured[3]==0 && captured[7]==42);
 return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(c)
   result=subprocess.run(['cc','-std=c99','-DPORTABLE','-Wall','-Wextra','-Werror','-Wno-sign-compare',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
if __name__=='__main__':unittest.main()
