"""Agent world revisions preserve a stable identity and validated story."""
import unittest
from test_xl_wilds_cast import proposal
from test_xl_wilds_events import CAST,EVENTS
from world import xl_painted_events,xl_versioned_world
BLUEPRINT={'rooms':[[1,1,125,125]],'links':[],'entrance_room':0,'exit_room':0}
class XLVersionedWorld(unittest.TestCase):
 def test_revisions_keep_identity_and_story_but_change_palette(self):
  painted=xl_painted_events.encode(proposal(),[],CAST,EVENTS);original=xl_versioned_world.create(painted,b'1'*16)
  revised=xl_versioned_world.revise(original,BLUEPRINT,[{'x':30,'y':30,'width':5,'height':5,'terrain':'water'}])
  a=xl_versioned_world.decode(original);b=xl_versioned_world.decode(revised)
  self.assertEqual(a[0],b[0]);self.assertEqual(a[2:4],b[2:4]);self.assertNotEqual(a[4],b[4]);self.assertEqual(revised[:8],b'EWGMAP0F')
 def test_rejects_corrupt_or_inaccessible_revisions(self):
  original=xl_versioned_world.create(xl_painted_events.encode(proposal(),[],CAST,EVENTS),b'1'*16)
  for bad in (original[:-1],original[:8]+bytes(16)+original[24:],original[:50]+b'\xff'+original[51:]):
   with self.assertRaises(ValueError):xl_versioned_world.decode(bad)
  with self.assertRaises(ValueError):xl_versioned_world.revise(original,BLUEPRINT,[{'x':75,'y':20,'width':1,'height':1,'terrain':'water'}])
 def test_cli_revises_in_place_only_when_explicit(self):
  import json,tempfile
  from pathlib import Path
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);source=p/'painted';world=p/'world';changes=p/'changes.json';source.write_bytes(xl_painted_events.encode(proposal(),[],CAST,EVENTS))
   changes.write_text(json.dumps({'blueprint':BLUEPRINT,'paint':[{'x':30,'y':30,'width':4,'height':4,'terrain':'water'}]}))
   with patch('builtins.print'),patch('sys.stderr'):
    xl_versioned_world.main(['create',str(source),str(world)])
    before=world.read_bytes();self.assertNotEqual(before[8:24],bytes(16))
    with self.assertRaises(SystemExit):xl_versioned_world.main(['revise',str(world),str(changes),str(world)])
    self.assertEqual(world.read_bytes(),before)
    xl_versioned_world.main(['revise',str(world),str(changes),str(world),'--replace-output'])
   after=world.read_bytes();self.assertNotEqual(after,before);self.assertEqual(after[8:24],before[8:24])
 def test_production_c_stages_nonzero_world_id_only_after_valid_world(self):
  import subprocess,tempfile
  from pathlib import Path
  from test_save_isolation import function
  root=Path(__file__).resolve().parents[2];src=(root/'src/platform/generated_map.c').read_text()
  code=r'''#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef uint8_t u8;typedef uint32_t u32;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define GENERATED_WORLD_XL 1
#define GENERATED_WILDS_EVENTS 1
static bool8 sXLHasStableId;static u8 sXLStableId[16];static int calls,accept=1;
static int GeneratedMap_StageXLPaintedEvents(const u8 *e,u32 n,const u8 *c,u32 z,const u8 *p,u32 size){(void)e;(void)n;(void)c;(void)z;(void)p;(void)size;calls++;return accept;}
'''+function(src,'GeneratedMap_StageXLVersionedWorld')+r'''
int main(void){u8 id[16]={0},a[1]={0};assert(!GeneratedMap_StageXLVersionedWorld(id,16,a,1,a,1,a,1)&&calls==0);id[0]=1;accept=0;assert(!GeneratedMap_StageXLVersionedWorld(id,16,a,1,a,1,a,1)&&!sXLHasStableId);accept=1;assert(GeneratedMap_StageXLVersionedWorld(id,16,a,1,a,1,a,1)&&sXLHasStableId&&sXLStableId[0]==1);return 0;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
 def test_native_loader_exact_versioned_format(self):
  import subprocess,tempfile
  from pathlib import Path
  from test_save_isolation import function
  root=Path(__file__).resolve().parents[2];src=(root/'src/platform/sdl2.c').read_text()
  code=r'''#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef int bool8;
#define FALSE 0
#define GENERATED_MAP_LARGE 1
#define GENERATED_MAP_WILDS 1
#define GENERATED_WORLD_XL 1
#define GENERATED_WILDS_GUIDE 1
#define GENERATED_WILDS_CAST 1
#define GENERATED_WILDS_EVENTS 1
#define GENERATED_CAVE_PROFILES 0
#define GENERATED_CAVE_WILDLIFE 0
#define GENERATED_XL_MAP_BYTES 16129
#define GENERATED_EVENT_BYTES 1466
#define GENERATED_CAST_BYTES 184
#define GENERATED_GUIDE_BYTES 59
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_LARGE_MAP_TEMPLATE_BYTES 3969
static int calls;static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
static int GeneratedMap_StageTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageLargeTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageWildsTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageXLWilds(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageXLPalette(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageGuidedWilds(const u8 *p,unsigned n,const u8 *c,unsigned z){(void)p;(void)n;(void)c;(void)z;return 0;}
static int GeneratedMap_StageCastWilds(const u8 *p,unsigned n,const u8 *c,unsigned z){(void)p;(void)n;(void)c;(void)z;return 0;}
static int GeneratedMap_StageXLCast(const u8 *p,unsigned n,const u8 *c,unsigned z){(void)p;(void)n;(void)c;(void)z;return 0;}
static int GeneratedMap_StageEventWilds(const u8 *e,unsigned n,const u8 *c,unsigned z,const u8 *p,unsigned q){(void)e;(void)n;(void)c;(void)z;(void)p;(void)q;return 0;}
static int GeneratedMap_StageXLEvents(const u8 *e,unsigned n,const u8 *c,unsigned z,const u8 *p,unsigned q){(void)e;(void)n;(void)c;(void)z;(void)p;(void)q;return 0;}
static int GeneratedMap_StageXLPaintedEvents(const u8 *e,unsigned n,const u8 *c,unsigned z,const u8 *p,unsigned q){(void)e;(void)n;(void)c;(void)z;(void)p;(void)q;return 0;}
static int GeneratedMap_StageXLVersionedWorld(const u8 *id,unsigned d,const u8 *e,unsigned n,const u8 *c,unsigned z,const u8 *p,unsigned q){calls++;return d==16&&id[0]=='1'&&n==1466&&e[1]==2&&z==184&&c[0]==2&&q==16129&&p[0]=='#';}
'''+function(src,'LoadGeneratedMapTemplate')+r'''
int main(int argc,char **argv){if(argc!=4)return 1;if(!LoadGeneratedMapTemplate(argv[1])||calls!=1)return 2;if(LoadGeneratedMapTemplate(argv[2])||calls!=1)return 3;if(LoadGeneratedMapTemplate(argv[3])||calls!=1)return 4;return 0;}'''
  blob=xl_versioned_world.create(xl_painted_events.encode(proposal(),[],CAST,EVENTS),b'1'*16)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code)
   for n,b in [('good',blob),('short',blob[:-1]),('long',blob+b'x')]:(p/n).write_bytes(b)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test'),str(p/'good'),str(p/'short'),str(p/'long')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
