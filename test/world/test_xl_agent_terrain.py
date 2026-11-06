"""Offline checks for owner-authored shared XL geometry (no sockets)."""
import json,tempfile,unittest
from pathlib import Path
from test_shared_generated_cave import MemoryAuthority
from test_shared_xl_wilds import blob
from world.shared_cave import SharedCave
from world import shared_terrain

class XLAgentTerrain(unittest.TestCase):
 def test_empty_gate_capability_restart_and_connected_geometry(self):
  area=SharedCave(blob()); identity=area.identity
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob())
   try:
    server._replace_cave(blob())
    def connect(name,cap):
     ident=server.create_identity(name);c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
     server._line(c,f"HELLO 1 {name} {ident['token']} SOCIALTRAVELCHATRALLY{cap}".encode());self.assertIn(b'WELCOME',c['out']);c['out'].clear();return c
    a=connect('Alice','CAVE10T');old=connect('Old','CAVE10')
    server._line(a,b'CAVE GET');self.assertIn(b'CAVE TERRAINH',a['out']);a['out'].clear()
    server._line(a,('CAVE ACK '+identity).encode());a['out'].clear();g,n=server.wilds_map
    server._line(a,(f'STATE 1 {g} {n} 1 1 1 7 1 '+('a'*16)+' '+('b'*16)).encode());a['out'].clear()
    edit=[{'x':100,'y':100,'terrain':'water'}]
    with self.assertRaises(ValueError):server.set_shared_geometry(identity,edit)
    a['in_generated_cave']=False;a['state']=[0,0,0,0,1,7,0]
    self.assertEqual(server.set_shared_geometry(identity,edit)['revision'],1)
    self.assertFalse(server._active_walkable(100,100));self.assertIn(b'CAVE RESET',a['out']);a['out'].clear()
    server._line(old,b'CAVE GET');self.assertEqual(old['out'],b'CAVE NONE\n')
    a['cave_next']=0;server._line(a,b'CAVE GET');self.assertIn(b'CAVE TERRAINH',a['out']);self.assertIn(b' 01646402',a['out'])
    view=server.inspect_shared_terrain(identity);self.assertEqual(view['effective_rows'][100][100],'#')
    with self.assertRaises(ValueError):server.set_shared_geometry(identity,[{'x':125,'y':125,'terrain':'water'}])
   finally:server.close()
   resumed=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True)
   try:self.assertFalse(resumed._active_walkable(100,100))
   finally:resumed.close()
 def test_xl_overlay_validator_rejects_disconnected_and_bad_order(self):
  cave=SharedCave(blob())
  with self.assertRaises(ValueError):shared_terrain.encode(cave,{(1,2):2,(2,1):2})
  with self.assertRaises(ValueError):shared_terrain.validate(cave,bytes([2,100,100,0,1,1,0]))
 def test_native_staging_validates_connected_xl_overlay(self):
  import subprocess
  from test_save_isolation import function
  source=(Path(__file__).resolve().parents[2]/'src/platform/generated_map.c').read_text()
  code=r'''#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int16_t s16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_WILDS_LARGE_TERRAIN 1
#define XL_SIDE 127
#define XL_CELLS (127*127)
static u8 sXLTemplate[XL_CELLS],sXLWalk[XL_CELLS],sXLTerrain[1539];static u16 sXLTerrainSize;static bool8 sXLStaged=1,sXLShared=1;
static int GeneratedMap_IsInside(void){return 0;}static int GeneratedMap_EntryPending(void){return 0;}
''' + function(source,'TerrainHeader') + '\n' + function(source,'GeneratedMap_StageSharedXLTerrain') + r'''
int main(void){u8 patch[]={1,100,100,2};for(int i=0;i<XL_CELLS;i++)sXLTemplate[i]=(i/127==0||i/127==126||i%127==0||i%127==126)?'#':'.';
assert(GeneratedMap_StageSharedXLTerrain(patch,sizeof(patch)));assert(!sXLWalk[100*127+100] && sXLWalk[100*127+101]);
u8 protected[]={1,125,125,2};assert(!GeneratedMap_StageSharedXLTerrain(protected,sizeof(protected)));
u8 disconnected[]={2,1,2,2,2,1,2};assert(!GeneratedMap_StageSharedXLTerrain(disconnected,sizeof(disconnected)));return 0;}
'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.c').write_text(code);q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
 def test_native_wire_accepts_bounded_xl_terrain_snapshot(self):
  import subprocess
  root=Path(__file__).resolve().parents[2]
  code=r'''#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[600];struct WorldCaveWire w={0};int r=0;while(fgets(line,sizeof(line),stdin)){char *t[7],*save,*p;unsigned n=0;line[strcspn(line,"\n")]=0;for(p=strtok_r(line," ",&save);p&&n<7;p=strtok_r(NULL," ",&save))t[n++]=p;r=WorldCaveWire_Feed(&w,n,(const char *const*)t);if(r<0)return 2;}return r==1&&w.terrainSeen&&w.terrainRevision==1&&w.terrainSize==4?0:3;}'''
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   flags=['-DPORTABLE','-DGENERATED_WORLD_XL=1','-DGENERATED_WILDS_CAST=1','-DGENERATED_WILDS_EVENTS=1','-DGENERATED_WILDS_SHARED_TERRAIN=1','-DGENERATED_WILDS_SHARED_GEOMETRY=1','-DGENERATED_WILDS_LARGE_TERRAIN=1']
   q=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',*flags,'-iquote',str(p),'-iquote',str(root/'include'),str(root/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   cave=SharedCave(blob());frames=cave.frames((1,bytes([1,100,100,2])),True)
   q=subprocess.run([str(p/'test')],input=frames,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
 def test_512_cell_compact_owner_edits_beyond_old_boundary(self):
  from unittest.mock import patch
  from world.shared_terrain_control import publish_geometry
  cave=SharedCave(blob());tiles=[{'x':x,'y':y,'terrain':'grass'} for x in range(80,96) for y in range(80,112)]
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);server=MemoryAuthority(p/'socket',p/'world',persist_generated_cave=True,archive_generated_areas=True,cave_template=blob())
   try:
    server._replace_cave(blob())
    def owner(_socket,request,**kwargs):
     c={'out':bytearray(),'closing':False};server._admin_line(c,json.dumps(request).encode());return json.loads(c['out'])
    with patch('world.shared_terrain_control.admin_request',side_effect=owner):result=publish_geometry(p/'admin',cave.identity,tiles)
    self.assertTrue(result['ok']);self.assertEqual(result['tiles'],512)
    self.assertEqual(len(shared_terrain.validate(cave,server._active_terrain()[1])),512)
   finally:server.close()
