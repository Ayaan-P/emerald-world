import unittest
from copy import deepcopy
import test_actor_observation as fixture
from world import actor_runtime as runtime
from world.actor_watch import poll

class WatchTests(unittest.TestCase):
 def test_real_local_change_and_relocation_guard(self):
  import test_actor_population as population
  f=population.PopulationTests();f.setUp();self.addCleanup(f.doCleanups)
  f.plan();runtime.tick(f.s,now=10);runtime.tick(f.s,now=16);f.admit();runtime.tick(f.s,now=22)
  from world.actor_observation import observe
  original=observe(f.s,'researcher',{},dict(radius=2))
  # An actual object is present in authoritative state, not a claimed encounter.
  obj=dict(next(o for o in f.s.objects if o['id']=='researcher'),id='marker',x=6,gfx=0,kind='prop');f.s.objects.append(obj)
  baseline=observe(f.s,'researcher',{},dict(radius=2));prior=baseline['entities'][0]
  pending=dict(target='marker',condition='changed',prior=deepcopy(prior),radius=2,revision=baseline['revision'],x=5,y=5)
  self.assertIsNone(poll(f.s,'researcher',{},pending))
  obj['x']=7;result=poll(f.s,'researcher',{},pending);self.assertEqual(result['entity']['x'],7)
  obj['x']=15;self.assertIsNone(poll(f.s,'researcher',{},pending))
  next(o for o in f.s.objects if o['id']=='researcher')['x']=6
  with self.assertRaisesRegex(ValueError,'Observer moved'):poll(f.s,'researcher',{},pending)
 def test_plan_observe_wait_restart_and_actual_condition_receipt(self):
  import test_actor_population as population
  from world.mechanics import Candidate
  import hashlib
  f=population.PopulationTests();f.setUp();self.addCleanup(f.doCleanups)
  f.plan();runtime.tick(f.s,now=10);runtime.tick(f.s,now=16);f.admit();runtime.tick(f.s,now=22)
  s=f.s;objects=deepcopy(s.objects);objects.append(dict(next(o for o in objects if o['id']=='researcher'),id='marker',kind='prop',gfx=0,x=6))
  state=deepcopy(s.module_state);c=state['world_characters']['researcher'];c['version']+=1
  c['plan']=dict(id='watch_neighbor',purpose='Wait for a local condition.',steps=[dict(id='look',tool='world.observe',args=dict(radius=2),after=[]),dict(id='wait',tool='world.await_entity',args=dict(observation=dict(result='look',key='tool_receipt'),target='marker',condition='changed'),after=['look'])])
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
  fixture=f.f.f.f.f.f.f;fixture.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());fixture.commit(dict(state=state,objects=objects,tiles=[]));self.assertIsNone(s.module_error)
  self.assertEqual(runtime.tick(s,now=28)['status'],'succeeded');self.assertEqual(runtime.tick(s,now=34)['status'],'pending');self.assertIsNone(runtime.tick(s,now=40))
  s.close();base=fixture.f;base.server=base.open();s=base.server
  self.assertIsNone(runtime.tick(s,now=46))
  next(o for o in s.objects if o['id']=='marker')['x']=7
  result=runtime.tick(s,now=52);self.assertEqual(result['status'],'succeeded');self.assertEqual(result['step'],'wait')
