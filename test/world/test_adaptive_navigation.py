from copy import deepcopy
import json,unittest
import test_actor_navigation as fixture
from world import actor_runtime as runtime

class AdaptiveNavigationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,actor='harbor_guide',x=77,y=72,maximum=40):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id='adaptive',purpose='Reach the chosen destination around actual occupancy.',steps=[dict(id='go',tool='world.navigate_adaptively',args=dict(revision=self.f.revision,x=x,y=y,max_steps=maximum),after=[])])
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def pulse(self,index):
  if self.s.deployment:self.f.advance(index,True)
  else:self.f.advance(index)
  return runtime.tick(self.s,now=10+index*6)
 def result(self):
  return json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE step='go' AND status='succeeded'").fetchone()[0])
 def test_changing_player_blocker_halts_reroutes_and_really_arrives(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  self.assertIsNone(runtime.tick(self.s,now=16));self.f.advance(0,True)
  control=self.s.module_state['world_character_controls']['harbor_guide'];next_tile=control['walk']['path'][1]
  self.f.f.state(self.f.peer,*self.s.wilds_map,*next_tile)
  self.f.advance(1);self.assertEqual(self.s.module_state['world_character_controls']['harbor_guide']['walk']['index'],0)
  self.assertIsNone(runtime.tick(self.s,now=22));self.assertIsNotNone(self.s.deployment)
  seen=[]
  for n in range(2,90):
   result=self.pulse(n);obj=next(o for o in self.s.objects if o['id']=='harbor_guide');seen.append([obj['x'],obj['y']])
   if result and result['status']=='succeeded':break
  self.assertEqual(result['status'],'succeeded');answer=self.result()
  self.assertEqual(answer['outcome'],'authority_arrived');self.assertEqual((answer['x'],answer['y']),(77,72));self.assertGreaterEqual(answer['reroutes'],1)
  self.assertNotIn(next_tile,seen)
  self.assertTrue(all(abs(a[0]-b[0])+abs(a[1]-b[1])<=1 for a,b in zip(seen,seen[1:])))
 def test_step_budget_stops_at_actual_tile_without_false_arrival(self):
  self.plan(actor='second',x=80,y=73,maximum=2);runtime.tick(self.s,now=10)
  for n in range(1,20):
   result=self.pulse(n)
   if result and result['status']=='succeeded':break
  answer=self.result();self.assertEqual(answer['steps'],2);self.assertEqual(answer['outcome'],'navigation_step_budget_exhausted')
  obj=next(o for o in self.s.objects if o['id']=='second');self.assertEqual((obj['x'],obj['y']),(answer['x'],answer['y']));self.assertNotEqual((obj['x'],obj['y']),(80,73))
 def test_restart_between_admitted_steps_resumes_without_replay(self):
  self.plan(x=75,y=72);runtime.tick(self.s,now=10);self.pulse(1);self.pulse(2)
  self.s.close();base=self.f.f.f;base.server=base.open();self.s=base.server;self.f.s=self.s;self.f.f.server=self.s;self.f.f.candidate=self.s.candidate
  for n in range(3,70):
   result=self.pulse(n)
   if result and result['status']=='succeeded':break
  self.assertEqual(self.result()['outcome'],'authority_arrived')
 def test_unadmitted_step_never_claims_motion(self):
  self.plan();runtime.tick(self.s,now=10);runtime.tick(self.s,now=16);self.s.deployment=None
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'blocked')
  self.assertIsNone(self.s.db.execute("SELECT 1 FROM actor_tool_receipts WHERE step='go' AND status='succeeded'").fetchone())
