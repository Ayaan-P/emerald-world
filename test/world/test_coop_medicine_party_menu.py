"""Compile the actual target-selection callback with disposable UI stubs."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CoopMedicinePartyMenu(unittest.TestCase):
 def test_owner_target_is_staged_without_consuming_item(self):
  src=(ROOT/'src/party_menu.c').read_text();start=src.index('void ItemUseCB_WorldCoopMedicine(')
  brace=src.index('{',start);depth=1;i=brace+1
  while depth:
   depth+=(src[i]=='{')-(src[i]=='}');i+=1
  code=r'''
#include <stdint.h>
#include <assert.h>
typedef uint8_t u8;typedef uint16_t u16;typedef void (*TaskFunc)(u8);
#define TRUE 1
#define FALSE 0
#define SE_SELECT 1
struct Pokemon {int id;} gPlayerParty[6];
struct {int slotId;} gPartyMenu;
struct Task {TaskFunc func;} gTasks[2];
int gPartyMenuUseExitCallback,gSpecialVar_ItemId,chosenSlot,closed,errors;
const u8 gText_WontHaveEffect[]={0};
u8 GetPartyIdFromBattleSlot(u8 slot){return slot==2?4:1;}
int WorldCoop_SelectMedicineTarget(u16 item,u8 slot,struct Pokemon *mon){
 assert(item==13);assert(mon==&gPlayerParty[gPartyMenu.slotId]);chosenSlot=slot;return slot==1;
}
void PlaySE(int x){(void)x;}
void DisplayPartyMenuMessage(const u8 *x,int y){(void)x;(void)y;errors++;}
void ScheduleBgCopyTilemapToVram(int x){(void)x;}
void Task_ClosePartyMenu(u8 task){(void)task;closed++;}
void done(u8 task){(void)task;}
''' + src[start:i] + r'''
int main(void){gSpecialVar_ItemId=13;gPartyMenu.slotId=0;
 ItemUseCB_WorldCoopMedicine(0,done);assert(chosenSlot==1 && closed==1 && gPartyMenuUseExitCallback);
 gPartyMenu.slotId=2;ItemUseCB_WorldCoopMedicine(0,done);
 assert(chosenSlot==4 && errors==1 && closed==1 && !gPartyMenuUseExitCallback && gTasks[0].func==done);
 return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
