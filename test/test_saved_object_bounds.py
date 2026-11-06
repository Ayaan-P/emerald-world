"""Exercise the actual object save/load functions with 48 live, 16 saved slots."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'port/resolved/src/load_save.c'

def function(source,name):
 m=re.search(r'(?m)^void '+name+r'\([^;]*\)\n\{',source)
 if not m: raise AssertionError('missing '+name)
 depth=1;i=m.end()
 while depth:
  if source[i]=='{':depth+=1
  elif source[i]=='}':depth-=1
  i+=1
 return source[m.start():i]

class SavedObjectBounds(unittest.TestCase):
 def test_only_saved_slots_are_copied_and_transient_slots_are_cleared(self):
  source=SOURCE.read_text()
  code='''#include <stdint.h>\n#include <string.h>\n#include <assert.h>\n#define PORTABLE 1\n#define WORLD_EXTENDED_OBJECTS 1\n#define OBJECT_EVENTS_COUNT 48\n#define SAVED_OBJECT_EVENTS_COUNT 16\n#define OBJ_EVENT_ID_FOLLOWER 250\n#define OBJ_EVENT_MON 0x8000\n#define FALSE 0\n#define TRUE 1\ntypedef uint8_t u8;typedef uint16_t u16;\nstruct ObjectEvent {u16 graphicsId;u16 localId;u8 spriteId;u8 active;};\nstruct SaveBlock1 {struct ObjectEvent objectEvents[16];u8 sentinel[64];};\nstatic struct SaveBlock1 block,*gSaveBlock1Ptr=&block;\nstatic struct ObjectEvent gObjectEvents[48];static int cleaned,timer;\nstatic void WorldBridge_PrepareSave(void){cleaned++;}\nstatic void SetMinimumOWESpawnTimer(void){timer++;}\n'''+function(source,'SaveObjectEvents')+'\n'+function(source,'LoadObjectEvents')+'''\nint main(void){\n memset(&block,0xA5,sizeof(block));\n for (int i=0;i<48;i++){gObjectEvents[i].graphicsId=0x1200+i;gObjectEvents[i].localId=i;gObjectEvents[i].spriteId=i;gObjectEvents[i].active=1;}\n SaveObjectEvents();\n for(int i=0;i<64;i++)assert(block.sentinel[i]==0xA5);\n for(int i=0;i<16;i++)assert(block.objectEvents[i].spriteId==127);\n LoadObjectEvents();\n for(int i=0;i<16;i++){assert(gObjectEvents[i].graphicsId==0x1200+i);assert(gObjectEvents[i].localId==i);assert(gObjectEvents[i].active==1);}\n for(int i=16;i<48;i++){assert(!gObjectEvents[i].active);assert(!gObjectEvents[i].graphicsId);}\n assert(cleaned==2&&timer==1);return 0;}\n'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   result=subprocess.run(['cc','-std=c11','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run([str(p/'test')],capture_output=True,text=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'))
   self.assertEqual(result.returncode,0,result.stderr)
