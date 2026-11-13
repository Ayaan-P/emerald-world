"""Shared painted XL map integrity and negotiated C wire; no rendered QA."""
from pathlib import Path
import hashlib, os, subprocess, tempfile, unittest
from world.shared_cave import SharedCave,CaveError
from world.shared_outdoor_palette import encode
ROOT=Path(__file__).resolve().parents[2]
NATIVE=Path(os.environ['EW_NATIVE_SOURCE']).resolve() if os.environ.get('EW_NATIVE_SOURCE') else ROOT/'__no_paired_native__'
def fixture():
 rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
 p={'rows':rows,'spawn':[1,1],'exit':[125,125]}
 return encode(p,[dict(x=3,y=3,width=2,height=2,terrain='sand'),dict(x=6,y=6,width=2,height=2,terrain='long_grass'),dict(x=9,y=9,width=2,height=2,terrain='rock'),dict(x=12,y=12,width=2,height=2,terrain='tall_grass')])
class PaintedOutdoorTests(unittest.TestCase):
 def test_palette_identity_geometry_and_frame_provenance(self):
  blob=fixture();c=SharedCave(blob);self.assertEqual(c.version,17);self.assertEqual(c.identity,hashlib.sha256(blob).hexdigest())
  self.assertTrue(c.walkable(3,3));self.assertTrue(c.walkable(6,6));self.assertFalse(c.walkable(9,9));self.assertTrue(c.walkable(12,12))
  frames=c.frames();self.assertIn(' XLPAINT\n',frames);self.assertIn('ss',frames);self.assertIn('rr',frames)
  bad=bytearray(blob);bad[8+3*127+3]=ord('x')
  with self.assertRaises(CaveError):SharedCave(bytes(bad))
 def test_new_format_is_distinct_and_invalid_changes_are_rejected(self):
  from world.xl_wilds_palette import encode as offline
  rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
  p={'rows':rows,'spawn':[1,1],'exit':[125,125]}
  self.assertEqual(offline(p,[])[:8],b'EWGMAP0D')
  with self.assertRaises(CaveError):SharedCave(offline(p,[]))
  with self.assertRaises(ValueError):encode(p,[dict(x=1,y=1,width=1,height=1,terrain='sand')])
  with self.assertRaises(ValueError):encode(p,[dict(x=3,y=3,width=1,height=1,terrain='unknown')])
  with self.assertRaises(ValueError):encode(p,[dict(x=2,y=1,width=124,height=125,terrain='rock')])
 @unittest.skipUnless((NATIVE/'src/world/world_cave_wire.c').is_file(), 'requires exact paired native candidate')
 def test_native_wire_checks_digest_and_format(self):
  code='''#include <stdio.h>\n#include <string.h>\n#include "global.h"\n#include "platform/world_cave_wire.h"\nint main(void){char line[256];struct WorldCaveWire w={0};int r=0;while(fgets(line,sizeof(line),stdin)){char *t[5],*save,*p;unsigned n=0;line[strcspn(line,"\\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))t[n++]=p;r=WorldCaveWire_Feed(&w,n,(const char *const*)t);if(r<0)return 2;}return r==1&&w.version==17&&w.nextRow==127?0:3;}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-DPORTABLE','-DGENERATED_WORLD_XL=1','-iquote',str(p),'-iquote',str(NATIVE/'include'),str(NATIVE/'src/world/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   f=SharedCave(fixture()).frames();run=lambda v:subprocess.run([str(p/'test')],input=v,text=True,capture_output=True).returncode
   self.assertEqual(run(f),0)
   self.assertNotEqual(run(f.replace('ss','ts',1)),0)
   self.assertNotEqual(run(f.replace('XLPAINT','XLWILDS')),0)

class SharedPaintedAuthority(unittest.TestCase):
 def setUp(self):
  import test_actor_runtime as fixture
  self.f=fixture.ActorRuntimeTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.s.archive_generated_areas=True;self.s.persist_generated_cave=True
 def test_actor_creates_and_two_trainers_get_identical_palette_legacy_denied(self):
  import json
  from world import actor_runtime as runtime
  from test_actor_habitats import HabitatTests
  blueprint=dict(rooms=[[3,3,20,18],[75,80,25,20]],links=[[0,1]],entrance_room=0,exit_room=1,style='rooms',seed=357,corridor_width=3)
  paint=[dict(x=4,y=4,width=3,height=3,terrain='sand'),dict(x=10,y=10,width=3,height=3,terrain='long_grass')]
  args=dict(label='Sandbank',layout='connected_shapes',blueprint=json.dumps(blueprint,separators=(',',':')),paint=json.dumps(paint,separators=(',',':')))
  self.f.apply(dict(id='painted',purpose='Make an outdoor landscape.',steps=[dict(id='create',tool='world.create_painted_landscape',args=args,after=[])]))
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  cave=self.s.shared_cave;self.assertEqual(cave.version,17)
  h=HabitatTests();h.s=self.s
  a=h.connect('PaintedA','SOCIALCAVE17');b=h.connect('PaintedB','SOCIALCAVE17');old=h.connect('OldPaint','SOCIALCAVE16')
  frames=h.send(a,'CAVE GET');self.assertEqual(frames,h.send(b,'CAVE GET'));self.assertIn('XLPAINT',frames);self.assertIn('sss',frames)
  self.assertIn('CAVE NONE',h.send(old,'CAVE GET'))
  for peer in (a,b):
   self.assertIn('CAVE OK',h.send(peer,'CAVE ACK '+cave.identity))
   g,n=self.s.wilds_map;h.send(peer,f'STATE 2 {g} {n} 3 3 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb')
   self.assertFalse(peer['closing']);self.assertEqual(peer['state'][2:4],[3,3])
  identity=cave.identity;self.s.close();case=self.f.f.f.f.case;case.server=case.open();self.s=case.server
  self.assertEqual(self.s.shared_cave.identity,identity);self.assertEqual(self.s.shared_cave.palette,cave.palette)

@unittest.skipUnless((NATIVE/'src/world/generated_map.c').is_file(), 'requires exact paired native candidate')
class NativePaintedStaging(unittest.TestCase):
 def test_real_native_staging_and_metatile_mapping(self):
  import re
  s=(NATIVE/'src/world/generated_map.c').read_text()
  def fn(signature):
   m=re.search(re.escape(signature)+r'[^;{}]*\)\s*\{',s);self.assertIsNotNone(m,signature)
   start=m.start();end=m.end();depth=1
   while depth:
    if s[end]=='{':depth+=1
    if s[end]=='}':depth-=1
    end+=1
   return s[start:end]
  pre='''#include <string.h>\n#include <stdint.h>\n#include <assert.h>\n#include "constants/metatile_labels.h"\ntypedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n#define GENERATED_MAP_READY 1\n#define GENERATED_WORLD_XL 1\n#define XL_SIDE 127\n#define XL_CELLS (127*127)\n#define WILDS_BLOCKED_WATER (0x400 | METATILE_General_CalmWater)\nstatic u8 sXLTemplate[XL_CELLS],sXLPalette[XL_CELLS];static bool8 sXLHasPalette,sXLStaged,sXLShared,sLargeStaged,sLargeShared,sHasTemplate,sLargeWilds;\nstatic int inside,entry,bridge=1;static int WorldBridge_Enabled(void){return bridge;}static int GeneratedMap_IsInside(void){return inside;}static int GeneratedMap_EntryPending(void){return entry;}\n'''
  code=pre+'\n'+fn('static u16 XLPaletteTile(')+'\n'+fn('static bool8 StageXLWilds(')+'\n'+fn('static bool8 StageXLPalette(')+'\n'+fn('bool8 GeneratedMap_StageSharedXLPalette(')+'\n'+fn('bool8 GeneratedMap_MatchesPreparedXLPalette(')+'\n'+fn('bool8 GeneratedMap_MatchesPreparedXLWilds(')+'''\nint main(void){static u8 c[XL_CELLS];int x,y;for(y=0;y<127;y++)for(x=0;x<127;x++)c[y*127+x]=(x==0||y==0||x==126||y==126)?'#':'.';c[3*127+3]='s';c[4*127+4]='g';c[5*127+5]='r';c[6*127+6]='t';assert(GeneratedMap_StageSharedXLPalette(c,XL_CELLS));assert(GeneratedMap_MatchesPreparedXLPalette(c,XL_CELLS));assert(!GeneratedMap_MatchesPreparedXLWilds(sXLTemplate,XL_CELLS));assert(sXLTemplate[5*127+5]=='#' && sXLTemplate[3*127+3]=='.');assert(XLPaletteTile('#')==(0x400|METATILE_General_CalmWater));assert(XLPaletteTile('r')==(0x400|METATILE_General_RockWall_GrassBase));assert(XLPaletteTile('s')==(0x3000|METATILE_General_SandPit_Center));assert(XLPaletteTile('g')==(0x3000|METATILE_General_LongGrass));c[3*127+3]='x';assert(!GeneratedMap_MatchesPreparedXLPalette(c,XL_CELLS));assert(!GeneratedMap_StageSharedXLPalette(c,XL_CELLS));c[3*127+3]='s';inside=1;assert(!GeneratedMap_StageSharedXLPalette(c,XL_CELLS));return 0;}\n'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=gnu99','-iquote',str(NATIVE/'include'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   subprocess.run([str(p/'test')],check=True)

@unittest.skipUnless((NATIVE/'src/world/world_bridge.c').is_file(), 'requires exact paired native candidate')
class NativePaintedBridge(unittest.TestCase):
 def test_actual_bridge_negotiation_and_safe_restage(self):
  import re
  source=(NATIVE/'src/world/world_bridge.c').read_text();m=re.search(r'static bool8 CaveLine\([^;{}]*\)\s*\{',source);self.assertIsNotNone(m)
  start=m.start();end=m.end();depth=1
  while depth:
   if source[end]=='{':depth+=1
   if source[end]=='}':depth-=1
   end+=1
  cave_line=source[start:end]
  code='''#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include "global.h"\n#include "platform/world_cave_wire.h"\nenum CaveState {CAVE_DISABLED,CAVE_IDLE,CAVE_WAIT,CAVE_WAIT_RESET,CAVE_ACK,CAVE_WAIT_OK,CAVE_READY,CAVE_MISMATCH,CAVE_RETURN_NONE};\nstatic struct {bool8 caveAvailable,staging,caveV16Probe,caveV17Probe;enum CaveState caveState;unsigned caveTimeout,caveRetry;char caveExpected[65];struct WorldCaveWire caveWire;} sWorld;\nstatic int inside,matched,stageCount;\nstatic int GeneratedMap_IsInside(void){return inside;}static int GeneratedMap_EntryPending(void){return 0;}\nstatic int GeneratedMap_MatchesPreparedXLPalette(const u8*p,unsigned n){return matched;}static int GeneratedMap_StageSharedXLPalette(const u8*p,unsigned n){stageCount++;return 1;}\nstatic int GeneratedMap_MatchesPreparedXLWilds(const u8*p,unsigned n){return 0;}static int GeneratedMap_StageSharedXLWilds(const u8*p,unsigned n){return 0;}\nstatic int GeneratedMap_MatchesPrepared(const u8*p,unsigned n){return 0;}static int GeneratedMap_StageTemplate(const u8*p,unsigned n){return 0;}\n'''+cave_line+'''\nint main(int argc,char **argv){char line[256];int r=0;sWorld.caveAvailable=1;sWorld.caveState=CAVE_WAIT;sWorld.caveV17Probe=atoi(argv[1]);inside=atoi(argv[2]);matched=atoi(argv[3]);while(fgets(line,sizeof(line),stdin)){char *t[5],*save,*p;unsigned n=0;line[strcspn(line,"\\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))t[n++]=p;r=CaveLine(n,t);if(!r)return 2;}return (int)sWorld.caveState==atoi(argv[4]) && stageCount==atoi(argv[5])?0:3;}\n'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-DPORTABLE','-DGENERATED_WORLD_XL=1','-iquote',str(p),'-iquote',str(NATIVE/'include'),str(NATIVE/'src/world/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   frames=SharedCave(fixture()).frames()
   def run(*a):return subprocess.run([str(p/'test'),*map(str,a)],input=frames,text=True,capture_output=True).returncode
   self.assertEqual(run(1,0,0,4,1),0);self.assertEqual(run(1,1,0,7,0),0);self.assertEqual(run(1,1,1,4,0),0);self.assertNotEqual(run(0,0,0,4,1),0)

if __name__=='__main__':unittest.main()
