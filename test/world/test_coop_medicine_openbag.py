"""Compile the actual bag-request emitter with isolated controller stubs."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CoopMedicineOpenBag(unittest.TestCase):
 def test_confusion_is_announced_only_for_coop(self):
  src=(ROOT/'src/battle_controllers.c').read_text();start=src.index('void BtlController_EmitChooseItem(')
  brace=src.index('{',start);depth=1;i=brace+1
  while depth:
   depth+=(src[i]=='{')-(src[i]=='}');i+=1
  code=r'''
#include <stdint.h>
#include <assert.h>
typedef uint8_t u8;typedef int32_t s32;
#define PARTY_SIZE 6
#define CONTROLLER_OPENBAG 12
#define STATUS2_CONFUSION 7
struct Mon {uint32_t status2;} gBattleMons[4];
u8 gActiveBattler,sBattleBuffersTransferData[16],captured[16];int coop,sizeSent;
int WorldCoop_IsBattle(void){return coop;}
void PrepareBufferDataTransfer(u8 id,u8 *p,int n){(void)id;sizeSent=n;for(int i=0;i<n;i++)captured[i]=p[i];}
''' + src[start:i] + r'''
int main(void){u8 order[3]={0x10,0x32,0x54};
 coop=1;gBattleMons[0].status2=STATUS2_CONFUSION;BtlController_EmitChooseItem(0,order);
 assert(sizeSent==5 && captured[0]==CONTROLLER_OPENBAG && captured[1]==0x10 && captured[4]==1);
 gBattleMons[0].status2=0;BtlController_EmitChooseItem(0,order);assert(sizeSent==5 && captured[4]==0);
 coop=0;BtlController_EmitChooseItem(0,order);assert(sizeSent==4);
 return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-DPORTABLE','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
