import json,unittest,tempfile,os,subprocess
from pathlib import Path
from unittest.mock import patch
import test_actor_runtime as fixture
from world import actor_runtime as runtime
from world.actor_habitat_revision import inspect
from world.species_cohort import species_id

class HabitatRevisionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ActorRuntimeTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.s.persist_generated_cave=True;self.s.archive_generated_areas=True
  self.activate(31)
 def activate(self,side):
  rows=['#'*side]+['#'+'.'*(side-2)+'#']*(side-2)+['#'*side]
  self.s._replace_cave((b'EWGMAP01' if side==31 else b'EWGMAP04')+''.join(rows).encode(),label='Existing habitat')
 def plan(self,actor='canon_rydel',species='RALTS',rate=25,version=0,now=None):
  self.f.apply(dict(id='habitat'+str(version),purpose='Revise real encounters using committed history.',steps=[
   dict(id='inspect',tool='world.inspect_habitat',args={},after=[]),
   dict(id='revise',tool='world.revise_habitat',args=dict(observation=dict(result='inspect',key='tool_receipt'),profile='granite',rate=rate,slots=json.dumps([[species,8]]*12,separators=(',',':'))),after=['inspect'])]),actor=actor,version=version)
  self.assertEqual(runtime.tick(self.s,now=10+version*20 if now is None else now)['status'],'succeeded')
 def result(self):return next(e for e in reversed(self.s.memory.history()['events']) if e.get('tool')=='world.revise_habitat')['result']
 def connect(self,name,role):
  token=self.s.create_identity(name)['token'];p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.s._line(p,('HELLO 1 '+name+' '+token+' '+role).encode());self.assertIn(b'WELCOME',p['out']);p['out'].clear();return p
 def send(self,p,line):p['out'].clear();self.s._line(p,line.encode());return p['out'].decode()
 def test_real_encounter_table_place_continuity_transfer_and_restart(self):
  old=self.s.shared_cave;place=self.s.memory.place(old.identity);self.plan()
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded');new=self.s.shared_cave
  self.assertEqual(new._rows,old._rows);self.assertEqual(new.version,10);self.assertEqual(new.wildlife[0],25)
  self.assertEqual(int.from_bytes(new.wildlife[1:3],'little'),species_id('RALTS','expansion-native'))
  self.assertEqual(self.s.memory.place(new.identity),place);self.assertEqual(self.result()['place_id'],place)
  p=self.connect('New','SOCIALCAVE10');oldpeer=self.connect('Old','SOCIALCAVE3')
  self.assertIn('CAVE WILD '+new.identity,self.send(p,'CAVE GET'));self.assertIn('CAVE NONE',self.send(oldpeer,'CAVE GET'))
  self.assertIn('CAVE OK',self.send(p,'CAVE ACK '+new.identity))
  self.assertEqual(self.s.objects,[])
  db=self.s.db.execute('PRAGMA database_list').fetchone()[2]
  from test_shared_generated_cave import MemoryAuthority
  self.s.close();restored=MemoryAuthority('/tmp/habitat-not-listening',Path(db).parent,persist_generated_cave=True,archive_generated_areas=True);self.addCleanup(restored.close)
  self.assertEqual(restored.shared_cave.identity,new.identity);self.assertEqual(restored.memory.place(new.identity),place)
  self.assertIsNone(runtime.tick(restored,now=30))
 def test_large_cave_second_actor_and_second_revision_preserve_geometry(self):
  self.activate(63);rows=self.s.shared_cave._rows;place=self.s.memory.place(self.s.shared_cave.identity)
  self.plan('canon_wally',version=1);self.assertEqual(runtime.tick(self.s,now=36)['status'],'succeeded')
  self.assertEqual(self.s.shared_cave.version,11);self.assertEqual(self.s.shared_cave._rows,rows)
  self.plan('canon_rydel',species='ABRA',rate=40,version=0,now=45)
  self.assertEqual(runtime.tick(self.s,now=51)['status'],'succeeded')
  self.assertEqual(self.s.shared_cave._rows,rows);self.assertEqual(self.s.memory.place(self.s.shared_cave.identity),place)
 def test_bad_species_and_receipt_failure_do_not_change_habitat(self):
  old=self.s.shared_cave.identity;self.plan(species='NOT_A_POKEMON')
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertEqual(self.s.shared_cave.identity,old)
  self.plan(version=1);original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if step['tool']=='world.revise_habitat' and status=='succeeded':raise ValueError('injected receipt failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):self.assertEqual(runtime.tick(self.s,now=36)['status'],'blocked')
  self.assertEqual(self.s.shared_cave.identity,old)
  self.assertFalse(any(e['event']=='habitat_population_revised' for e in self.s.memory.history()['events']))
 def test_occupied_stale_and_opened_immutable_refuse_without_force(self):
  old=self.s.shared_cave.identity;self.plan()
  p=self.connect('Inside','SOCIALCAVE10');self.send(p,'CAVE GET');self.send(p,'CAVE ACK '+old)
  p['state']=[*self.s.cave_map,2,2,1,7,1];p['in_generated_cave']=True
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertEqual(self.s.shared_cave.identity,old)
  p['state']=[0,9,8,8,1,7,1];p['in_generated_cave']=False
  self.plan(version=1);self.activate(63)
  self.assertEqual(runtime.tick(self.s,now=36)['status'],'blocked')
  with self.s.db:self.s._pin_region(old)
  self.s.activate_generated_area(old)
  with self.assertRaises(ValueError):inspect(self.s,'canon_rydel',{}, {})
 def test_exact_existing_native_decoder_reads_revised_population(self):
  root=os.environ.get('EW_LINK_NATIVE_SOURCE')
  if not root:self.skipTest('requires published native cave decoder fixture')
  self.plan();runtime.tick(self.s,now=16);p=self.connect('Decoder','SOCIALCAVE10');frames=self.send(p,'CAVE GET')
  code='''#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[512];struct WorldCaveWire w={0};int r=0;
while(fgets(line,sizeof(line),stdin)){char *t[5],*save,*p;unsigned n=0;line[strcspn(line,"\\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))t[n++]=p;r=WorldCaveWire_Feed(&w,n,(const char *const*)t);if(r<0)return 2;}
return r==1 && w.version==10 && w.wildlife[0]==25 && (w.wildlife[1]+256*w.wildlife[2])==SPECIES && w.wildlife[3]==8 ? 0:3;}'''.replace('SPECIES',str(species_id('RALTS','expansion-native')))
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);root=Path(root).resolve();(d/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(d/'test.c').write_text(code)
   build=subprocess.run(['cc','-std=gnu99','-DPORTABLE','-DGENERATED_CAVE_PROFILES=1','-DGENERATED_CAVE_WILDLIFE=1','-iquote',str(d),'-iquote',str(root/'include'),str(root/'src/world/world_cave_wire.c'),str(d/'test.c'),'-o',str(d/'test')],capture_output=True,text=True)
   self.assertEqual(build.returncode,0,build.stderr)
   run=subprocess.run([str(d/'test')],input=frames,capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
