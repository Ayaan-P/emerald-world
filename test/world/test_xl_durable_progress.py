"""Private bounded journal stores XL story progress; no sockets or game save edits."""
import os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PAYLOAD=1+4*(6+1466+184+16129)
class XLDurableProgress(unittest.TestCase):
 def test_journal_restarts_corruption_and_unsafe_paths(self):
  code=r'''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "platform/xl_progress_store.h"
#define N (1+4*(6+1466+184+16129))
static unsigned char data[N];
int main(int argc,char **argv){int mode=atoi(argv[2]);(void)argc;if(mode==0){if(XLProgressStore_Init(argv[1],0,data,N))return 1;return 0;}
 if(!XLProgressStore_Init(argv[1],1,data,N))return 2;
 if(mode==1){data[0]=1;if(!XLProgressStore_Save(data,N))return 3;data[0]=2;if(!XLProgressStore_Save(data,N))return 4;}
 if(mode==2&&data[0]!=2)return 5;if(mode==3&&data[0]!=1)return 6;XLProgressStore_Close();return 0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DPORTABLE','-iquote',str(ROOT/'include'),str(ROOT/'src/platform/xl_progress_store.c'),str(ROOT/'src/platform/native_save.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   run=lambda path,mode:subprocess.run([str(p/'test'),str(path),str(mode)],capture_output=True,text=True).returncode
   save=p/'trainer.sav';self.assertEqual(run(save,0),0);side=p/'trainer.sav.generated-story';self.assertFalse(side.exists())
   self.assertEqual(run(save,1),0);self.assertEqual(side.stat().st_mode&0o777,0o600);self.assertEqual(run(save,2),0)
   raw=bytearray(side.read_bytes());raw[20]^=1;side.write_bytes(raw);self.assertEqual(run(save,3),0)
   damaged=bytearray(side.read_bytes());damaged[12+PAYLOAD+20]^=1;side.write_bytes(damaged);before=side.read_bytes();self.assertEqual(run(save,2),2);self.assertEqual(side.read_bytes(),before)
   unsafe=p/'unsafe.sav.generated-story';target=p/'target';target.write_bytes(b'keep');unsafe.symlink_to(target);self.assertEqual(run(p/'unsafe.sav',1),2);self.assertEqual(target.read_bytes(),b'keep')
   loose=p/'loose.sav.generated-story';loose.write_bytes(b'foreign');os.chmod(loose,0o644);self.assertEqual(run(p/'loose.sav',1),2);self.assertEqual(loose.read_bytes(),b'foreign')
   os.chmod(loose,0o600);self.assertEqual(run(p/'loose.sav',1),2);self.assertEqual(loose.read_bytes(),b'foreign')
 def test_real_cache_and_journal_survive_process_restart(self):
  from test_save_isolation import function
  src=(ROOT/'src/platform/generated_map.c').read_text()
  code=r'''#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include "platform/xl_progress_store.h"
typedef uint8_t u8;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define XL_CELLS 16129
#define GENERATED_EVENT_BYTES 1466
#define GENERATED_CAST_BYTES 184
#define XL_PROGRESS_SLOTS 4
#define XL_PROGRESS_SLOT_BYTES (6 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES + XL_CELLS)
#define XL_PROGRESS_PAYLOAD_BYTES (1 + XL_PROGRESS_SLOTS * XL_PROGRESS_SLOT_BYTES)
static bool8 sXLActive=1,sEventActive=1;static u8 sEventState,sEventData[1466],sCastMetadata[184],sXLTemplate[16129];
static struct {bool8 valid;u8 trainer[4],state,events[1466],cast[184],cells[16129];} sXLProgress[4];static u8 sXLProgressCurrent=255,sXLProgressNext,sXLProgressPayload[XL_PROGRESS_PAYLOAD_BYTES];static bool8 sXLProgressDurable;
static struct {u8 playerTrainerId[4];} save,*gSaveBlock2Ptr=&save;static int WorldBridge_Enabled(void){return 0;}
'''+ '\n'.join(function(src,n) for n in ('XLProgressPack','XLProgressUnpack','GeneratedMap_InitXLProgress','XLProgressPersist','XLRestoreEventProgress','XLRememberEventProgress'))+r'''
int main(int argc,char **argv){int mode=atoi(argv[2]);(void)argc;save.playerTrainerId[0]=1;if(!GeneratedMap_InitXLProgress(argv[1],1))return 2;
XLRestoreEventProgress();if(mode==1){sEventState=3;XLRememberEventProgress();}else {if(sEventState!=3)return 3;save.playerTrainerId[0]=2;sEventState=0;XLRestoreEventProgress();if(sEventState!=0)return 4;}
XLProgressStore_Close();return 0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-iquote',str(ROOT/'include'),str(ROOT/'src/platform/xl_progress_store.c'),str(ROOT/'src/platform/native_save.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   save=p/'trainer.sav';save.write_bytes(b'unchanged')
   for mode in (1,2):
    q=subprocess.run([str(p/'test'),str(save),str(mode)],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   self.assertEqual(save.read_bytes(),b'unchanged')
 def test_windows_falls_back_without_creating_file(self):
  code=r'''#include "platform/xl_progress_store.h"
int main(void){char data[8]={0};return XLProgressStore_Init("unused",1,data,sizeof(data))?1:0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DPORTABLE','-D_WIN32','-iquote',str(ROOT/'include'),str(ROOT/'src/platform/xl_progress_store.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],cwd=p,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr);self.assertEqual({x.name for x in p.iterdir()},{'test','test.c'})
