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
#define XL_PROGRESS_SLOTS 64
static bool8 sXLActive=1,sEventActive=1,sXLHasPalette,sXLHasStableId;static u8 sXLPalette[16129],sXLStableId[16];static u8 sEventState,sEventData[1466],sCastMetadata[184],sXLTemplate[16129];
static struct {bool8 valid;u8 trainer[4],state,identity[64];} sXLProgress[64];static u8 sXLProgressCurrent=0xFF,sXLProgressNext;
static struct {u8 playerTrainerId[4];} save,*gSaveBlock2Ptr=&save;
static int online;static int WorldBridge_Enabled(void){return online;}static void XLProgressPersist(void){}
void WorldCaveWire_XLEventDigest(const u8 *,const u8 *,const u8 *,char *);
void WorldCaveWire_XLPaintedEventDigest(const u8 *,const u8 *,const u8 *,char *);
void WorldCaveWire_XLStableStoryDigest(const u8 *,const u8 *,const u8 *,char *);
'''+function(src,'XLRestoreEventProgress')+'\n'+function(src,'XLRememberEventProgress')+r'''
int main(void){save.playerTrainerId[0]=1;sEventState=0;XLRestoreEventProgress();sEventState=3;XLRememberEventProgress();
sEventState=0;XLRestoreEventProgress();assert(sEventState==3);
save.playerTrainerId[0]=2;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);sEventState=5;XLRememberEventProgress();
save.playerTrainerId[0]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==3);
sXLTemplate[100]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);sEventState=7;XLRememberEventProgress();
sXLTemplate[100]=0;sEventState=0;XLRestoreEventProgress();assert(sEventState==3);
sEventData[5]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);
sEventData[5]=0;sXLHasPalette=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);sEventState=7;XLRememberEventProgress();
sXLPalette[100]='t';sEventState=0;XLRestoreEventProgress();assert(sEventState==0);sXLPalette[100]=0;sEventState=0;XLRestoreEventProgress();assert(sEventState==7);
sXLHasPalette=0;sEventState=0;XLRestoreEventProgress();assert(sEventState==3);
sXLHasStableId=1;sXLStableId[0]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);sEventState=9;XLRememberEventProgress();
sXLPalette[200]='t';sXLTemplate[200]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==9);
sEventData[5]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);sEventData[5]=0;
sXLStableId[0]=2;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);sXLStableId[0]=1;sEventState=0;XLRestoreEventProgress();assert(sEventState==9);
sXLHasStableId=0;sXLTemplate[200]=0;
online=1;sEventState=0;XLRestoreEventProgress();assert(sXLProgressCurrent==255&&sEventState==0);
online=0;memset(sXLProgress,0,sizeof(sXLProgress));sXLProgressNext=0;sEventData[5]=0;
for(int i=0;i<64;i++){sXLTemplate[100]=i;sEventState=0;XLRestoreEventProgress();sEventState=(i%15)+1;XLRememberEventProgress();}
sXLTemplate[100]=0;sEventState=0;XLRestoreEventProgress();assert(sEventState==1);
sXLTemplate[100]=64;sEventState=0;XLRestoreEventProgress();sEventState=7;XLRememberEventProgress();
sXLTemplate[100]=0;sEventState=0;XLRestoreEventProgress();assert(sEventState==0);return 0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DPORTABLE','-iquote',str(p),'-iquote',str(ROOT/'include'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
