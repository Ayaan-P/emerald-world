"""Native in-session XL event memory; no save file or sockets."""
import subprocess,tempfile,unittest
from pathlib import Path
from test_save_isolation import function
ROOT=Path(__file__).resolve().parents[2]
class XLSessionProgress(unittest.TestCase):
 def test_same_trainer_and_content_restore_without_cross_world_leaks(self):
  src=(ROOT/'src/platform/generated_map.c').read_text()
  code=r'''#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef uint8_t u8;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define XL_CELLS 16129
#define GENERATED_EVENT_BYTES 1466
#define GENERATED_CAST_BYTES 184
#define XL_PROGRESS_SLOTS 4
static bool8 sXLActive=1,sEventActive=1;static u8 sEventState,sEventData[1466],sCastMetadata[184],sXLTemplate[16129];
static struct {bool8 valid;u8 trainer[4],state,events[1466],cast[184],cells[16129];} sXLProgress[4];static u8 sXLProgressCurrent=0xFF,sXLProgressNext;
static struct {u8 playerTrainerId[4];} save,*gSaveBlock2Ptr=&save;
static int online;static int WorldBridge_Enabled(void){return online;}static void XLProgressPersist(void){}
'''+function(src,'XLRestoreEventProgress')+'\n'+function(src,'XLRememberEventProgress')+r'''
int main(void){save.playerTrainerId[0]=1;sEventState=0;XLRestoreEventProgress();sEventState=3;XLRememberEventProgress();
sEventState=0;XLRestoreEventProgress();assert(sEventState==3);
save.playerTrainerId[0]=2;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);sEventState=5;XLRememberEventProgress();
save.playerTrainerId[0]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==3);
sXLTemplate[100]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);sEventState=7;XLRememberEventProgress();
sXLTemplate[100]=0;sEventState=0;XLRestoreEventProgress();assert(sEventState==3);
sEventData[5]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);
online=1;sEventState=0;XLRestoreEventProgress();assert(sXLProgressCurrent==255&&sEventState==0);return 0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
