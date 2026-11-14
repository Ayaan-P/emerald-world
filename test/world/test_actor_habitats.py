from copy import deepcopy
import json,os,subprocess,tempfile,unittest
from pathlib import Path
import test_actor_places as fixture
from world import actor_runtime as runtime

class HabitatTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.PlaceTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,species='RALTS'):
  self.f.plan();state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1;c['plan']['id']='habitat'
  step=c['plan']['steps'][0];step['tool']='world.create_habitat';step['args']['population']=json.dumps(dict(profile='granite',rate=25,slots=[[species,8]]*12),separators=(',',':'))
  self.f.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def connect(self,name,role):
  i=self.s.create_identity(name);p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.s._line(p,('HELLO 1 '+name+' '+i['token']+' '+role).encode());self.assertIn(b'WELCOME',p['out']);p['out'].clear()
  self.s._line(p,b'STATE 1 0 9 8 8 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb');p['out'].clear();return p
 def send(self,p,line):
  p['out'].clear();self.s._line(p,line.encode());return p['out'].decode()
 def create(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');return self.f.result()
 def test_actual_native_population_transfer_old_client_refusal_and_restart(self):
  old=self.s.shared_cave.identity;r=self.create();a=self.connect('Native','SOCIALCAVE10REGION1');b=self.connect('Legacy','SOCIALCAVEREGION1')
  self.assertIn(r['place_id'],self.send(a,'REGION LIST 0'));self.assertNotIn(r['place_id'],self.send(b,'REGION LIST 0'))
  self.assertEqual(self.send(b,'REGION SELECT '+r['place_id']),'REGION REFUSED\n')
  self.assertIn('REGION SELECTED',self.send(a,'REGION SELECT '+r['place_id']))
  frames=self.send(a,'CAVE GET');self.assertIn('CAVE WILD '+r['revision'],frames)
  self.assertTrue(frames.startswith('CAVE BEGIN '+r['revision']+' 0 10\n'))
  self.assertIn('CAVE OK',self.send(a,'CAVE ACK '+r['revision']))
  self.send(a,'STATE 2 %s %s 1 1 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb'%self.s.cave_map)
  self.assertFalse(a['closing']);self.assertEqual(self.s._region_scope(a),r['revision']);self.assertEqual(self.s.shared_cave.identity,old)
  self.s.close();base=self.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.db.execute('SELECT revision FROM world_region_revisions WHERE place_id=?',(r['place_id'],)).fetchone()[0],r['revision'])
 def test_disabled_or_unknown_species_never_creates_habitat(self):
  before=self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0]
  self.plan('NOT_A_POKEMON');self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],before)
 def test_exact_paired_native_decoder_consumes_authored_population(self):
  root=os.environ.get('EW_NATIVE_SOURCE')
  if not root:self.skipTest('requires exact paired native source')
  root=Path(root).resolve();r=self.create();a=self.connect('Decoder','SOCIALCAVE10REGION1');self.send(a,'REGION SELECT '+r['place_id']);frames=self.send(a,'CAVE GET')
  from world.species_cohort import species_id
  expected=species_id('RALTS','expansion-native')
  code='''#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[512];struct WorldCaveWire w={0};int r=0;
while(fgets(line,sizeof(line),stdin)){char *t[5],*save,*p;unsigned n=0;line[strcspn(line,"\\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))t[n++]=p;r=WorldCaveWire_Feed(&w,n,(const char *const*)t);if(r<0)return 2;}
return r==1 && w.version==10 && w.wildlife[0]==25 && (w.wildlife[1]+256*w.wildlife[2])==SPECIES && w.wildlife[3]==8 ? 0:3;}'''.replace('SPECIES',str(expected))
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);(d/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(d/'test.c').write_text(code)
   p=subprocess.run(['cc','-std=gnu99','-DPORTABLE','-DGENERATED_CAVE_PROFILES=1','-DGENERATED_CAVE_WILDLIFE=1','-iquote',str(d),'-iquote',str(root/'include'),str(root/'src/world/world_cave_wire.c'),str(d/'test.c'),'-o',str(d/'test')],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
   p=subprocess.run([str(d/'test')],input=frames,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
