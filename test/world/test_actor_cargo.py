import hashlib,json,unittest
from copy import deepcopy
from unittest.mock import patch
import test_actor_cave_travel
from world import actor_runtime as runtime
from world.actor_objects import digest
from world.mechanics import Candidate

class CargoTests(unittest.TestCase):
 def setUp(self):
  self.f=test_actor_cave_travel.ActorTravelTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  actor=next(o for o in self.s.objects if o['id']=='harbor_guide')
  cargo=dict(actor,id='cargo',kind='prop',portable=True,gfx=0,x=3,y=4,text='Survey equipment.')
  objects=self.s.objects+[cargo]
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
  self.f.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.fx.commit(dict(state=self.s.module_state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  self.plan('take','world.take_prop',dict(object='cargo',object_revision=digest(cargo)))
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
 def plan(self,id,tool,args):
  state=deepcopy(self.s.module_state);row=state['world_characters']['harbor_guide'];row['version']+=1
  row['plan']=dict(id=id,purpose='Transport an existing object across real places.',steps=[dict(id='act',tool=tool,args=args,after=[])])
  self.f.fx.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def travel(self):
  self.f.plan();self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending');self.f.deploy();self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
 def test_carried_identity_crosses_actual_link_then_places_and_survives_old_source_restart(self):
  self.travel()
  inv=self.s.inspect()['actor_runtime']['carried_props'][0]
  self.assertEqual((inv['object'],inv['owner'],inv['revision'],inv['version']),('cargo','harbor_guide',self.f.f.habitat,2))
  self.assertNotIn('cargo',[o['id'] for o in self.s.objects])
  a=next(o for o in self.s.objects if o['id']=='harbor_guide')
  self.plan('drop','world.place_prop',dict(object='cargo',version=2,x=a['x']+1,y=a['y']))
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded')
  prop=next(o for o in self.s.objects if o['id']=='cargo');self.assertEqual(prop['region_revision'],self.f.f.habitat)
  # Normal old source still contains its source-region prop; projection preserves destination.
  ns={};exec(self.s.candidate.source,ns);self.f.fx.candidate=self.s.candidate
  result=ns['update'](self.s._context(),deepcopy(self.s.module_state))
  result['state']=deepcopy(self.s.module_state) # Test fixture plans are injected, not source-authored.
  result['objects']=[next(o for o in self.s.objects if o['id']==v['id']) if v['id']!='cargo' else v for v in result['objects']]
  self.f.fx.commit(result);self.assertIsNone(self.s.module_error)
  self.assertEqual([o for o in self.s.objects if o['id']=='cargo'],[prop])
  self.s.close();self.f.fx.f.server=self.f.fx.f.open();self.s=self.f.fx.f.server
  self.assertEqual([o for o in self.s.objects if o['id']=='cargo'],[prop])
  self.assertEqual(self.s.db.execute('SELECT committed FROM actor_cargo_transfers').fetchone()[0],1)
 def test_failed_admission_rolls_back_cargo_and_actor_together(self):
  before=self.s.inspect()['actor_runtime']['carried_props'];objects=deepcopy(self.s.objects)
  self.f.plan();self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending')
  from world import actor_cargo
  original=actor_cargo.commit
  def fail(*args):original(*args);raise ValueError('Injected failure after cargo update')
  with patch.object(actor_cargo,'commit',side_effect=fail):
   with self.assertRaises(AssertionError):self.f.deploy()
  self.assertEqual(self.s.inspect()['actor_runtime']['carried_props'],before)
  self.assertEqual(self.s.objects,objects)
  self.assertEqual(self.s.db.execute('SELECT committed FROM actor_cargo_transfers').fetchone()[0],0)
