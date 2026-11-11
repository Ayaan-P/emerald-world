import os,subprocess,tempfile
from pathlib import Path
import json
import unittest
from unittest.mock import patch
import test_actor_runtime as fixture
from world import actor_runtime as runtime

class LandscapeTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ActorRuntimeTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.s.archive_generated_areas=True;self.s.persist_generated_cave=True
 def plan(self,actor='canon_rydel',layout='connected_shapes',style='organic'):
  bp=dict(rooms=[[3,3,20,18],[75,80,25,20]],links=[[0,1]],entrance_room=0,exit_room=1,style=style,seed=357,corridor_width=3)
  if layout=='clearings':bp=dict(seed=52,loops=0,landmarks=[dict(id='west',x=20,y=25,radius=6),dict(id='east',x=90,y=70,radius=8)],reservations=[[45,45,15,15]])
  self.f.apply(dict(id='landscape',purpose='Create usable outdoor space.',steps=[dict(id='create',tool='world.create_landscape',args=dict(label='Open Country',layout=layout,blueprint=json.dumps(bp,separators=(',',':'))),after=[])]),version=1 if actor=='canon_wally' else 0,actor=actor)
 def test_two_layouts_real_archive_native_frames_and_restart(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  first=self.s.shared_cave;self.assertEqual(first.version,16);self.assertEqual(first.side,127)
  result=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE step='create'").fetchone()[0])
  self.assertEqual(result['place_id'],self.s.memory.place(first.identity))
  self.assertIn('XLWILDS',''.join(first.frames()))
  self.plan('canon_wally','clearings');self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  second=self.s.shared_cave;self.assertNotEqual(first.identity,second.identity)
  self.assertFalse(second.walkable(50,50));self.assertTrue(second.walkable(90,70))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive WHERE identity IN (?,?)',(first.identity,second.identity)).fetchone()[0],2)
  self.s.close();case=self.f.f.f.f.case;case.server=case.open();self.s=case.server
  self.assertEqual(self.s.shared_cave.identity,second.identity)
  self.assertIsNone(runtime.tick(self.s,now=30))
 def test_occupied_or_populated_active_world_not_displaced(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');old=self.s.shared_cave.identity
  self.plan('canon_wally','clearings');self.s.objects=[dict(id='resident',region_revision=old)]
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertEqual(self.s.shared_cave.identity,old)
 def test_atomic_receipt_failure(self):
  self.plan();old=self.s.shared_cave;original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if status=='succeeded':raise ValueError('injected storage failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertIs(self.s.shared_cave,old)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],0)

 def test_actual_authenticated_transfer_ack_entry_and_occupied_guard(self):
  from test_actor_habitats import HabitatTests
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  h=HabitatTests();h.s=self.s
  peer=h.connect('OutdoorVisitor','SOCIALCAVE16');frames=h.send(peer,'CAVE GET')
  self.assertIn('XLWILDS',frames);revision=self.s.shared_cave.identity
  self.assertIn('CAVE OK',h.send(peer,'CAVE ACK '+revision))
  h.send(peer,'STATE 2 %s %s 1 1 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb'%self.s.wilds_map)
  self.assertFalse(peer['closing']);self.assertEqual(self.s._region_scope(peer),revision)
  legacy=h.connect('OutdoorLegacy','SOCIALCAVE');self.assertIn('CAVE NONE',h.send(legacy,'CAVE GET'))
  self.plan('canon_wally','clearings');self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
  self.assertEqual(self.s.shared_cave.identity,revision)
 def test_exact_native_decoder_consumes_outdoor_layout(self):
  root=os.environ.get('EW_NATIVE_SOURCE')
  if not root:self.skipTest('requires exact paired native source')
  root=Path(root).resolve();self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');frames=''.join(self.s.shared_cave.frames())
  code='''#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[512];struct WorldCaveWire w={0};int r=0;
while(fgets(line,sizeof(line),stdin)){char *t[5],*save,*p;unsigned n=0;line[strcspn(line,"\\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))t[n++]=p;r=WorldCaveWire_Feed(&w,n,(const char *const*)t);if(r<0)return 2;}
return r==1 && w.version==16 ? 0:3;}'''
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);(d/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(d/'test.c').write_text(code)
   p=subprocess.run(['cc','-std=gnu99','-DPORTABLE','-DGENERATED_WORLD_XL=1','-DGENERATED_CAVE_PROFILES=1','-DGENERATED_CAVE_WILDLIFE=1','-iquote',str(d),'-iquote',str(root/'include'),str(root/'src/world/world_cave_wire.c'),str(d/'test.c'),'-o',str(d/'test')],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
   p=subprocess.run([str(d/'test')],input=frames,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)

 def test_invalid_disconnected_shape_never_changes_active_place(self):
  self.f.apply(dict(id='bad_layout',purpose='Invalid topology must not publish.',steps=[dict(id='create',tool='world.create_landscape',args=dict(label='Broken',layout='connected_shapes',blueprint=json.dumps(dict(rooms=[[3,3,6,6],[80,80,8,8]],links=[],entrance_room=0,exit_room=1))),after=[])]))
  old=self.s.shared_cave
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertIs(self.s.shared_cave,old)
