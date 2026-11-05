"""Exercise the normal save entry point with a generated instance active."""
from pathlib import Path
import subprocess,tempfile,unittest
from test_save_isolation import function
ROOT=Path(__file__).resolve().parents[2]
class GeneratedMapSaveGuard(unittest.TestCase):
 def test_native_file_publish_is_also_blocked(self):
  body=function((ROOT/'src/platform/sdl2.c').read_text(),'Platform_StoreSaveFile')
  code=r"""
#include <assert.h>
typedef unsigned char bool8;
#define FALSE 0
int inside=1,calls;
int GeneratedMap_IsInside(void){return inside;}
int StoreSaveFile(void){calls++;return 1;}
"""+body+r"""
int main(void){assert(!Platform_StoreSaveFile()&&!calls);inside=0;assert(Platform_StoreSaveFile()&&calls==1);return 0;}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
 def test_normal_save_never_calls_storage_while_inside(self):
  body=function((ROOT/'src/save.c').read_text(),'TrySavingData')
  code=r'''
#include <assert.h>
typedef unsigned char u8;
#define TRUE 1
#define SAVE_STATUS_ERROR 255
#define SAVE_STATUS_OK 1
int inside=1,gFlashMemoryPresent=1,gSaveAttemptStatus,gDamagedSaveSectors,calls,failed;
int GeneratedMap_IsInside(void){return inside;}
int HandleSavingData(u8 t){(void)t;calls++;return SAVE_STATUS_OK;}
void DoSaveFailedScreen(u8 t){(void)t;failed++;}
'''+body+r'''
int main(void){
 assert(TrySavingData(0)==SAVE_STATUS_ERROR && gSaveAttemptStatus==SAVE_STATUS_ERROR && calls==0 && failed==0);
 inside=0;assert(TrySavingData(0)==SAVE_STATUS_OK && calls==1);
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-DPORTABLE','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
