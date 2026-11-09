from copy import deepcopy
import hashlib,json,unittest
import test_actor_places as fixture
from world import actor_runtime as runtime
from world.mechanics import Candidate
from world.actor_observation import observe

class PopulationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.PlaceTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def define(self,identity='researcher',kind='character'):
  d=dict(id=identity,kind=kind,x=5,y=5,gfx=7 if kind=='character' else 0,text='Hello there.')
  if kind=='character':d.update(name='Neri',role='An independent researcher.',goals=['Study this place.'],team=[dict(species=280,level=8)])
  else:d['portable']=True
  return d
 def plan(self,definition=None):
  self.f.plan();state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1;c['plan']['id']='create_and_populate'
  c['plan']['steps'].append(dict(id='populate',tool='world.populate',args=dict(revision=dict(result='create',key='revision'),definition=json.dumps(definition or self.define(),separators=(',',':'))),after=['create']))
  self.f.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def admit(self):
  _,path,_=self.s.deployment;self.s.deployment=None;source=path.read_text();candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());ns={};exec(source,ns)
  self.f.f.f.f.f.f.candidate=candidate
  self.f.f.f.f.f.f.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)))
  self.assertIsNone(self.s.module_error)
 def test_create_populate_observe_and_restart(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending')
  self.assertNotIn('researcher',self.s.module_state['world_characters']);self.admit()
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
  observed=observe(self.s,'researcher',{},dict(radius=2));self.assertEqual((observed['x'],observed['y']),(5,5))
  revision=observed['revision'];self.assertEqual(revision,self.f.result()['revision'])
  client=self.f.connect('Visitor');client.select_region(self.f.result()['place_id']);peer=client.sock.conn
  peer['character_capable']=peer['character_region_capable']=True
  client.send_state(peer['seq']+1,*self.s.cave_map,5,4,1,7,1,'a'*16,'b'*16)
  snapshot=self.s._snapshot(peer);self.assertIn('REGION_OBJECT '+revision+' researcher ',snapshot);self.assertIn('CHARACTER researcher 1',snapshot)
  self.s.close();base=self.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(observe(self.s,'researcher',{},dict(radius=1))['revision'],revision)
  self.assertIsNone(runtime.tick(self.s,now=30))
 def test_prop_uses_real_prop_wire_not_character(self):
  self.plan(self.define('marker','prop'));runtime.tick(self.s,now=10);self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending');self.admit()
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded');self.assertNotIn('marker',self.s.module_state['world_characters'])
  self.assertTrue(next(o for o in self.s.objects if o['id']=='marker')['portable'])
  token=self.s.create_identity('PropViewer')['token'];peer=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  def send(line):
   peer['out'].clear();self.s._line(peer,line.encode());return peer['out'].decode()
  self.assertIn('WELCOME',send('HELLO 1 PropViewer '+token+' SOCIALCAVE16REGION1CHAR1CHARREG1WORLDOBJ1'))
  send('STATE 1 0 9 8 8 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb')
  result=self.f.result();self.assertIn('REGION SELECTED',send('REGION SELECT '+result['place_id']))
  send('CAVE GET');self.assertIn('CAVE OK',send('CAVE ACK '+result['revision']))
  send('STATE 2 %s %s 5 4 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb'%self.s.cave_map)
  snapshot=self.s._snapshot(peer);self.assertIn('REGION_PROP '+result['revision']+' marker ',snapshot);self.assertNotIn('CHARACTER marker ',snapshot)

 def test_invalid_placement_and_canonical_copy_rejected(self):
  d=self.define();d.update(x=1,y=1);self.plan(d);runtime.tick(self.s,now=10)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertIsNone(self.s.deployment)
 def test_unadmitted_source_never_claims_population(self):
  self.plan();runtime.tick(self.s,now=10);runtime.tick(self.s,now=16);self.s.deployment=None
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'blocked');self.assertNotIn('researcher',self.s.module_state['world_characters'])
 def test_canonical_copy_is_not_a_generic_spawn(self):
  d=self.define();d['name']='Steven';self.plan(d);runtime.tick(self.s,now=10)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertIsNone(self.s.deployment)
 def test_new_character_can_execute_its_own_navigation_plan(self):
  self.plan();runtime.tick(self.s,now=10);runtime.tick(self.s,now=16);self.admit();runtime.tick(self.s,now=22)
  state=deepcopy(self.s.module_state);c=state['world_characters']['researcher'];c['version']+=1
  revision=next(o['region_revision'] for o in self.s.objects if o['id']=='researcher')
  c['plan']=dict(id='explore',purpose='Inspect another part of this room.',steps=[dict(id='walk',tool='world.navigate',args=dict(revision=revision,x=6,y=5),after=[]),dict(id='look',tool='world.observe',args=dict(radius=1),after=['walk'])])
  self.f.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'pending');self.admit()
  for tick in range(1,10):
   self.s.tick=tick;ns={};exec(self.s.candidate.source,ns)
   self.f.f.f.f.f.f.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)))
   self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=40)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=46)['status'],'succeeded')
  self.assertEqual(observe(self.s,'researcher',{},dict(radius=1))['x'],6)
