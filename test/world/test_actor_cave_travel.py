import hashlib,json,unittest
from copy import deepcopy
from world.mechanics import Candidate
from world import actor_runtime as runtime
from world.actor_observation import observe
import test_cave_links

class ActorTravelTests(unittest.TestCase):
 def setUp(self):
  self.f=test_cave_links.HabitatLinkTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.fx=self.f.f
  state=deepcopy(self.s.module_state)
  actor=state['world_characters']['harbor_guide'];actor.update(version=2,evidence=[self.s.memory.history()['events'][-1]['seq']])
  objects=deepcopy(self.s.objects);source="def update(context,state):\n return dict(state=state,tiles=[],objects="+repr(objects)+")\n"
  self.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.fx.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
 def plan(self,actor="harbor_guide"):
  entry=next(e for e in observe(self.s,actor,{},dict(radius=4))['entities'] if e['id']=='door')
  self.assertEqual(entry['cave_link']['destination'],self.f.habitat)
  state=deepcopy(self.s.module_state);a=state['world_characters'][actor];a['version']+=1
  a['plan']=dict(id='visit',purpose='Use an observed passage.',steps=[dict(id='cross',tool='world.traverse_link',args=dict(object='door',revision=entry['program_revision']),after=[])])
  self.fx.commit(dict(state=state,tiles=[],objects=self.s.objects))
 def deploy(self):
  _,path,_=self.s.deployment;source=path.read_text();self.s.deployment=None
  self.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());ns={};exec(source,ns)
  result=ns['update'](self.s._context(),deepcopy(self.s.module_state));self.fx.commit(result)
  self.assertIsNone(self.s.module_error)
 def test_real_departure_arrival_snapshots_identity_and_restart_receipt(self):
  a=self.f.connect('Source');b=self.f.connect('Destination')
  self.fx.state(b,0,9,8,8);self.fx.send(b,'REGION SELECT '+self.f.habitat_place);self.fx.send(b,'CAVE GET');self.fx.send(b,'CAVE ACK '+self.f.habitat);self.fx.state(b,*self.s.cave_map,8,8)
  before=deepcopy(self.s.module_state['world_characters']['harbor_guide']['team'])
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  self.assertIn('harbor_guide',self.s._snapshot(a));self.assertNotIn('harbor_guide',self.s._snapshot(b))
  self.deploy()
  self.assertNotIn('harbor_guide',self.s._snapshot(a));self.assertIn('harbor_guide',self.s._snapshot(b))
  self.assertEqual(self.s.module_state['world_characters']['harbor_guide']['team'],before)
  self.assertEqual(len([o for o in self.s.objects if o['id']=='harbor_guide']),1)
  self.s.close();self.fx.f.server=self.fx.f.open();self.s=self.fx.f.server;self.fx.server=self.s
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'succeeded')
  result=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE actor='harbor_guide'").fetchone()[0])
  self.assertEqual(result['outcome'],'authority_cave_arrival');self.assertEqual(result['destination'],self.f.habitat)
  self.assertIsNone(runtime.tick(self.s,now=30))
 def test_unadmitted_transfer_never_reports_arrival(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  self.s.deployment=None
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'blocked')
  self.assertEqual(next(o for o in self.s.objects if o['id']=='harbor_guide')['region_revision'],self.f.f.f.a)

 def test_second_actor_uses_same_link_and_keeps_first_actor_in_source(self):
  state=deepcopy(self.s.module_state);c=deepcopy(state['world_characters']['harbor_guide'])
  c.update(version=1,name='Second Visitor',object_id='visitor');state['world_characters']['visitor']=c
  original=next(o for o in self.s.objects if o['id']=='harbor_guide')
  objects=self.s.objects+[dict(original,id='visitor',x=4,y=4)]
  source="def update(context,state):\n return dict(state=state,tiles=[],objects="+repr(objects)+")\n"
  self.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.fx.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  self.plan('visitor');self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.deploy()
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'succeeded')
  self.assertEqual(next(o for o in self.s.objects if o['id']=='visitor')['region_revision'],self.f.habitat)
  self.assertEqual(next(o for o in self.s.objects if o['id']=='harbor_guide')['region_revision'],original['region_revision'])

 def test_destination_player_arriving_during_staging_prevents_transfer(self):
  b=self.f.connect('Blocker');self.fx.state(b,0,9,8,8)
  self.fx.send(b,'REGION SELECT '+self.f.habitat_place);self.fx.send(b,'CAVE GET');self.fx.send(b,'CAVE ACK '+self.f.habitat)
  self.fx.state(b,*self.s.cave_map,8,8);self.plan();runtime.tick(self.s,now=10)
  pending=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE actor='harbor_guide'").fetchone()[0])
  self.fx.state(b,*self.s.cave_map,pending['object']['x'],pending['object']['y'])
  with self.assertRaisesRegex(ValueError,'became occupied'):self.deploy()
  self.assertNotEqual(next(o for o in self.s.objects if o['id']=='harbor_guide')['region_revision'],self.f.habitat)
